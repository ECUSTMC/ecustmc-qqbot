"""AI相关处理器"""
from openai import OpenAI
from botpy import BotAPI
from botpy.ext.command_util import Commands
from botpy.message import GroupMessage
from config import MODEL_CONFIGS


def _extract_user_id(message) -> str:
    """安全提取 message 中的用户唯一标识符，兼容群消息和私聊消息对象差异"""
    try:
        author = getattr(message, 'author', None)
        if not author:
            return None
        
        # 群消息用 member_openid，私聊用 user_openid
        if hasattr(author, 'member_openid') and author.member_openid:
            return str(author.member_openid)
        elif hasattr(author, 'user_openid') and author.user_openid:
            return str(author.user_openid)
        elif hasattr(author, 'id') and author.id:
            return str(author.id)
    except Exception as e:
        pass
    
    return None

def _check_sensitive_input(user_input: str) -> bool:
    """检查用户输入是否包含敏感关键词（秘钥、密码等）"""
    sensitive_keywords = [
        '密码', 'password', 'passwd',
        '秘钥', 'secret', 'key',
        'token', 'api', 'cat',
        'mysql', 'mongodb', 'redis',
        '.env', 'config', 'rcon',
        '私钥', 'private',
        '认证', 'auth', 'credential'
    ]
    
    input_lower = user_input.lower()
    for keyword in sensitive_keywords:
        if keyword in input_lower:
            return True
    return False


async def _ai_safety_check(text_to_check: str) -> bool:
    """使用AI模型检查模型生成的输出是否泄露秘钥/密码/凭证等敏感信息

    Returns:
        False表示检测到敏感信息泄露（应阻止发送），True表示未检测到或无法判断
    """
    try:
        config = MODEL_CONFIGS.get("auto", {})
        api_key = config.get("api_key")
        base_url = config.get("base_url")

        if not api_key or not base_url:
            # 如果配置缺失，默认通过（不阻止）
            return True

        client = OpenAI(api_key=api_key, base_url=base_url)

        safety_prompt = f"""你是一个敏感信息检测器。请判断下面的文本是否包含明文或可识别形式的秘钥、密码、API Key、token、私钥、凭证或其他能用于认证/访问的敏感信息：

    文本："{text_to_check}"

    判断目标（仅用于参考）：
    1. 明文密码或带有 'password'、'passwd' 等提示的字符串
    2. API Key、token、secret、access_key、secret_key 等形式的凭证
    3. 私钥片段（如以 -----BEGIN PRIVATE KEY----- 开头或包含长序列的 base64）
    4. 其它可用来认证/访问的凭证信息

    请仅回复“泄露”或“没有泄露”。如果文本中包含任何上述敏感信息，回复“泄露”。"""

        response = client.chat.completions.create(
            model="auto",
            messages=[{"role": "user", "content": safety_prompt}],
            stream=False,
            temperature=0.3,
        )

        result = response.choices[0].message.content.strip().lower()

        # 将包含“没有泄露”含义的模型判断视为安全
        if "没有泄露" in result:
            return True
        else:
            return False

    except Exception as e:
        print(f"[WARNING] AI safety check error: {e}")
        return False


def _replace_domains(text: str) -> str:
    """替换文本中的域名后缀以避免QQ API限制"""
    # 定义白名单URL前缀（QQ白名单，不需要替换）
    whitelist_prefixes = [
        'https://mcskin.ecustvr.top/auth/',
    ]
    
    # 定义要替换的域名后缀及其对应的替换字符串
    domain_replacements = {
        '.com.cn': '-com-cn',
        '.edu.cn': '-edu-cn',
        '.gov.cn': '-gov-cn',
        '.net.cn': '-net-cn',
        '.org.cn': '-org-cn',
        '.cn': '-cn',
        '.com': '-com',
        '.org': '-org',
        '.net': '-net',
        '.edu': '-edu',
        '.gov': '-gov',
        '.top': '-top',
        '.cc': '-cc',
        '.me': '-me',
        '.tv': '-tv',
        '.info': '-info',
        '.biz': '-biz',
        '.name': '-name',
        '.mobi': '-mobi',
        '.club': '-club',
        '.store': '-store',
        '.app': '-app',
        '.tech': '-tech',
        '.ai': '-ai',
        '.ink': '-ink',
        '.live': '-live',
        '.wiki': '-wiki',
        '.ltd': '-ltd',
        '.site': '-site',
        '.online': '-online',
        '.space': '-space',
        '.website': '-website',
        '.cloud': '-cloud',
        '.md': '-md',
        '.io': '-io',
        '.py': '-py',
        # 可以继续添加其他需要替换的域名后缀
    }

    # 先用占位符替换白名单URL，避免被替换
    placeholders = {}
    import re
    for i, prefix in enumerate(whitelist_prefixes):
        # 匹配以prefix开头的完整URL，只包含有效的URL字符
        pattern = re.compile(rf'{re.escape(prefix)}[a-zA-Z0-9\-./?=&%]+')
        matches = pattern.findall(text)
        for j, match in enumerate(matches):
            placeholder = f"__WHITELIST_URL_{i}_{j}__"
            placeholders[placeholder] = match
            text = text.replace(match, placeholder)
    
    # 进行替换
    for old, new in domain_replacements.items():
        text = text.replace(old, new)
    
    # 恢复白名单URL
    for placeholder, url in placeholders.items():
        text = text.replace(placeholder, url)
    
    return text


async def _call_ai_model(model_name: str, user_input: str, message: GroupMessage, include_reasoning: bool = False, user_id: str = None, audit_output: bool = True):
    """调用AI模型的通用函数"""
    try:
        # 获取模型配置
        config = MODEL_CONFIGS.get(model_name, {})
        api_key = config.get("api_key")
        base_url = config.get("base_url")
        
        if not api_key or not base_url:
            await message.reply(content=f"模型 {model_name} 的API配置不完整")
            return
        
        # 使用配置的API设置初始化客户端
        client = OpenAI(api_key=api_key, base_url=base_url)

        # 调用大模型；仅当显式传入 user_id 时才包含 user 字段
        call_kwargs = {
            "model": model_name,
            "messages": [
                {
                    "role": "user",
                    "content": user_input,
                },
            ],
            "temperature": 1.0,
        }
        if user_id:
            call_kwargs["user"] = user_id

        completion = client.chat.completions.create(**call_kwargs)

        
        # 添加提示信息
        replace_text = "\n\n⚠️由于QQAPI限制，服务器地址中间的\"-\"请自行换成\".\"！"

        # 提取模型响应并在发送前进行输出审查
        if include_reasoning:
            message_obj = completion.choices[0].message

            # 安全获取推理内容，如果不存在则使用默认值
            model_reasoning_content = getattr(message_obj, 'reasoning_content', None)
            model_response = getattr(message_obj, 'content', '')

            # 先对原始内容进行审查（未替换域名），仅当模型为 clawdbot 且 audit_output 为 True 时进行审查
            unsafe = False
            if audit_output and model_name == "clawdbot":
                if model_reasoning_content:
                    if not await _ai_safety_check(model_reasoning_content):
                        unsafe = True
                if not unsafe and model_response:
                    if not await _ai_safety_check(model_response):
                        unsafe = True

            if unsafe:
                await message.reply(content="🚫 模型生成的内容被检测为不安全，已阻止发送。")
                return

            # 对推理内容和回复内容中的网址进行替换并发送
            if model_reasoning_content:
                model_reasoning_content = _replace_domains(model_reasoning_content)
            model_response = _replace_domains(model_response)

            if model_reasoning_content:
                await message.reply(content=f"{model_name}:\n推理：\n{model_reasoning_content}\n\n回复：\n{model_response}{replace_text}")
            else:
                await message.reply(content=f"{model_name}:\n{model_response}{replace_text}")
        else:
            model_response = completion.choices[0].message.content

            # 输出审查：仅针对 clawdbot 执行审查
            if audit_output and model_name == "clawdbot":
                if not await _ai_safety_check(model_response):
                    await message.reply(content="🚫 模型生成的内容被检测为不安全，已阻止发送。")
                    return

            # 对回复内容中的网址进行替换
            model_response = _replace_domains(model_response)

            await message.reply(content=f"{model_name}:\n{model_response}{replace_text}")

    except Exception as e:
        # 错误处理
        await message.reply(content=f"调用 {model_name} 模型时出错: {str(e)}")


@Commands("/dsr")
async def query_deepseek_r1(api: BotAPI, message: GroupMessage, params=None):
    user_input = "".join(params) if params else "你好"
    await _call_ai_model("deepseek-reasoner", user_input, message, include_reasoning=True)
    return True


@Commands("/dsc")
async def query_deepseek_chat(api: BotAPI, message: GroupMessage, params=None):
    user_input = "".join(params) if params else "你好"
    await _call_ai_model("deepseek-chat", user_input, message, include_reasoning=False)
    return True


async def group_chat_with_clawdbot(api: BotAPI, message: GroupMessage):
    """群组调用 clawdbot 模型"""
    user_input = message.content.strip() if hasattr(message, 'content') else "你好"
    
    # 检查敏感关键词
    if _check_sensitive_input(user_input):
        await message.reply(content="🚫 对不起，我不能回答关于密码、秘钥或其他敏感信息的问题。请出于安全考虑避免询问此类内容。")
        return True
    
    # NOTE: 将 AI 审查从输入改为输出，输出审查将在模型调用后进行
    
    user_id = _extract_user_id(message)
    await _call_ai_model("clawdbot", user_input, message, include_reasoning=False, user_id=user_id)
    return True


async def direct_chat_with_clawdbot(api: BotAPI, message: GroupMessage):
    """私聊调用 clawdbot 模型"""
    user_input = message.content.strip() if hasattr(message, 'content') else "你好"
    
    # # 检查敏感关键词
    # if _check_sensitive_input(user_input):
    #     await message.reply(content="🚫 对不起，我不能回答关于密码、秘钥或其他敏感信息的问题。请出于安全考虑避免询问此类内容。")
    #     return True
    
    user_id = _extract_user_id(message)
    # 私聊暂时不审查模型输出，通过 audit_output 开关控制
    await _call_ai_model("clawdbot", user_input, message, include_reasoning=False, user_id=user_id, audit_output=False)
    return True


@Commands("/chat")
async def chat_with_clawdbot(api: BotAPI, message: GroupMessage, params=None):
    """使用 clawdbot 模型回复，不带思考，传入最终用户唯一标识符"""
    if params:
        user_input = "".join(params)
    
    # 检查敏感关键词
    if _check_sensitive_input(user_input):
        await message.reply(content="🚫 对不起，我不能回答关于密码、秘钥或其他敏感信息的问题。请出于安全考虑避免询问此类内容。")
        return True
    
    else:
        # 如果没有 params，尝试从 message.content 中提取
        user_input = message.content.strip() if hasattr(message, 'content') else "你好"
    # 对于 /chat 明确传入最终用户唯一标识符 user
    user_id = f"{message.author.member_openid}"
    await _call_ai_model("clawdbot", user_input, message, include_reasoning=False, user_id=user_id)
    return True

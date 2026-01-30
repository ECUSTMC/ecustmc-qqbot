"""AI相关处理器"""
from openai import OpenAI
from botpy import BotAPI
from botpy.ext.command_util import Commands
from botpy.message import GroupMessage
from config import MODEL_CONFIGS


def _replace_domains(text: str) -> str:
    """替换文本中的域名后缀以避免QQ API限制"""
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
        # 可以继续添加其他需要替换的域名后缀
    }

    # 进行替换
    for old, new in domain_replacements.items():
        text = text.replace(old, new)
    
    return text


async def _call_ai_model(model_name: str, user_input: str, message: GroupMessage, include_reasoning: bool = False, user_id: str = None):
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

        # 提取模型响应
        if include_reasoning:
            message_obj = completion.choices[0].message
            
            # 安全获取推理内容，如果不存在则使用默认值
            model_reasoning_content = getattr(message_obj, 'reasoning_content', None)
            model_response = getattr(message_obj, 'content', '')
            
            if model_reasoning_content:
                # 对推理内容和回复内容中的网址进行替换
                model_reasoning_content = _replace_domains(model_reasoning_content)
                model_response = _replace_domains(model_response)
                
                await message.reply(content=f"{model_name}:\n推理：\n{model_reasoning_content}\n\n回复：\n{model_response}{replace_text}")
            else:
                # 如果没有推理内容，只返回回复
                model_response = _replace_domains(model_response)
                await message.reply(content=f"{model_name}:\n{model_response}{replace_text}")
        else:
            model_response = completion.choices[0].message.content
            
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
    user_id = f"{message.author.member_openid}"
    await _call_ai_model("clawdbot", user_input, message, include_reasoning=False)
    return True

async def direct_chat_with_clawdbot(api: BotAPI, message: GroupMessage):
    """私聊调用 clawdbot 模型"""
    user_input = message.content.strip() if hasattr(message, 'content') else "你好"
    user_id = f"{message.author.member_openid}"
    await _call_ai_model("clawdbot", user_input, message, include_reasoning=False, user_id=user_id)
    return True


@Commands("/chat")
async def chat_with_clawdbot(api: BotAPI, message: GroupMessage, params=None):
    """使用 clawdbot 模型回复，不带思考，传入最终用户唯一标识符"""
    if params:
        user_input = "".join(params)
    else:
        # 如果没有 params，尝试从 message.content 中提取
        user_input = message.content.strip() if hasattr(message, 'content') else "你好"
    # 对于 /chat 明确传入最终用户唯一标识符 user
    user_id = f"{message.author.member_openid}"
    await _call_ai_model("clawdbot", user_input, message, include_reasoning=False, user_id=user_id)
    return True

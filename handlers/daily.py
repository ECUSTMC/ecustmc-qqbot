"""每日内容处理器"""
import time
import aiohttp
from botpy import BotAPI
from botpy.ext.command_util import Commands
from botpy.message import GroupMessage
from botpy.types.message import MarkdownPayload
from config import API_APP_ID, API_APP_SECRET, MODEL_CONFIGS
from openai import OpenAI

async def ai_content_review(content: str) -> bool:
    """
    使用AI模型进行内容安全审核
    返回True表示内容安全，False表示内容不安全
    """
    # 构建审核提示词
    review_prompt = f"""请对以下内容进行安全审核，判断是否包含敏感、不适宜或违规内容：

内容："{content}"

请严格审核以下方面：
1. 政治敏感内容（政治、政府、国家、领导人等）
2. 暴力内容（暴力、杀戮、伤害等）
3. 色情内容（色情、成人、性相关等）
4. 违法内容（毒品、赌博、犯罪等）
5. 敏感话题（宗教、民族、分裂等）
6. 其他违规内容（仇恨言论、诽谤、攻击等）

请只回答"安全"或"不安全"，不要给出其他解释。"""

    try:
        # 获取auto模型配置
        config = MODEL_CONFIGS.get("auto", {})
        api_key = config.get("api_key")
        base_url = config.get("base_url")
        
        if not api_key or not base_url:
            # 如果配置不完整，使用备用审核机制
            return False
        
        # 直接调用AI API进行审核
        client = OpenAI(api_key=api_key, base_url=base_url)
        
        completion = client.chat.completions.create(
            model="auto",
            messages=[
                {
                    "role": "user",
                    "content": review_prompt,
                },
            ],
            temperature=0.1,
        )
        
        # 获取AI响应
        ai_response = completion.choices[0].message.content

        # 解析AI响应
        if "不安全" in ai_response:
            return False
        
        # 默认安全
        return True
        
    except Exception as e:
        # 如果AI审核失败，默认不安全
        return False

@Commands("/一言")
async def daily_word(api: BotAPI, message: GroupMessage, params=None):
    daily_word = f"https://v1.hitokoto.cn/"
    async with aiohttp.ClientSession() as session:
        async with session.post(daily_word) as res:
            result = await res.json()
            if res.ok:
                content = result['hitokoto']
                author_from = result['from']
                author = result['from_who']

                # 使用AI模型进行内容安全审核
                is_safe = await ai_content_review(content)
                
                if not is_safe:
                    # 如果内容不安全，返回默认安全内容
                    reply_content = (
                        f"🍃 微风吹过，思绪飘远...\n\n"
                        f"——今日份小确幸"
                    )
                else:
                    # 内容安全，正常显示
                    if author != author_from and author != None:
                        author_from = f"{author}《{author_from}》"
                    reply_content = (
                        f"> {content}\n\n"
                        f"——{author_from}"
                    )

                markdown = MarkdownPayload(content=reply_content)
                await message.reply(markdown=markdown, msg_type=2)
            else:
                error_content = (
                    f"获取一言失败"
                )
                await message.reply(content=error_content)
            return True


@Commands("/今日黄历")
async def daily_huangli(api: BotAPI, message: GroupMessage, params=None):
    # 获取当前日期
    current_date = time.strftime("%Y%m%d", time.localtime())
    
    # 构建 API 请求 URL
    daily_huangli = f"https://www.mxnzp.com/api/holiday/single/{current_date}?ignoreHoliday=false&app_id={API_APP_ID}&app_secret={API_APP_SECRET}"
    
    # 发送请求
    async with aiohttp.ClientSession() as session:
        async with session.get(daily_huangli) as res:
            # 解析响应 JSON 数据
            result = await res.json()

            if res.ok and result['code'] == 1:  # 检查响应是否成功
                # 获取所需的黄历内容
                data = result['data']
                date = data.get('date', '未知')
                type_des = data.get('typeDes', '未知')
                chinese_zodiac = data.get('chineseZodiac', '未知')
                lunar_calendar = data.get('lunarCalendar', '未知')
                suit = data.get('suit', '无宜')
                avoid = data.get('avoid', '无忌')
                constellation = data.get('constellation', '未知')
                solar_terms = data.get('solarTerms', '未知')

                # 拼接黄历内容
                reply_content = (
                    f"## 📅 今日黄历\n\n"
                    f"- 日期：**{date}**\n"
                    f"- 农历：**{lunar_calendar}**\n"
                    f"- 星座：**{constellation}**\n"
                    f"- 节气：**{solar_terms}**\n"
                    f"- 生肖：**{chinese_zodiac}**\n"
                    f"- 类型：**{type_des}**\n\n"
                    f"✅ 宜：{suit}\n\n"
                    f"❌ 忌：{avoid}"
                )

                # 发送回复
                markdown = MarkdownPayload(content=reply_content)
                await message.reply(markdown=markdown, msg_type=2)
            else:
                # 错误处理
                await message.reply(content="获取黄历失败")
                
    return True


@Commands("/通知")
async def daily_notice(api: BotAPI, message: GroupMessage, params=None):
    notice_url = "https://news.bestzyq.cn/news.json"
    async with aiohttp.ClientSession() as session:
        async with session.get(notice_url) as res:
            result = await res.json()
            if res.ok:
                notices = result
                if not notices:
                    await message.reply(content="今日无新通知")
                    return True
                reply_content = "## 📢 今日通知\n\n"
                for notice in notices:
                    clean_url = notice['link'].replace("https://", "").replace("http://", "")
                    new_url = f"https://mcskin.ecustvr.top/auth/qqbot/{clean_url}"
                    reply_content += (
                        f"### {notice['title']}\n\n"
                        f"- 📅 {notice['date']}\n"
                        f"- 🏛️ {notice['source']}\n"
                        f"- 🔗 [点击查看]({new_url})\n\n"
                    )
                markdown = MarkdownPayload(content=reply_content)
                await message.reply(markdown=markdown, msg_type=2)
            else:
                await message.reply(content="获取通知失败")
    return True
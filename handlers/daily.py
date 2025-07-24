"""每日内容处理器"""
import time
import aiohttp
from botpy import BotAPI
from botpy.ext.command_util import Commands
from botpy.message import GroupMessage
from config import API_APP_ID, API_APP_SECRET


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
                if author != author_from and author != None:
                    author_from = f"{author}《{author_from}》"
                reply_content = (
                    f"\n"
                    f"{content}"
                    f"\n"
                    f"——{author_from}"
                )

                await message.reply(content=reply_content)
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
                    f"\n"
                    f"📅 日期: {date}\n"
                    f"🀄 农历: {lunar_calendar}\n"
                    f"💫 星座: {constellation}\n"
                    f"🌞 节气: {solar_terms}\n"
                    f"🐉 生肖: {chinese_zodiac}\n"
                    f"📌 类型: {type_des}\n"
                    f"✅ 宜: {suit}\n"
                    f"❌ 忌: {avoid}\n"
                )

                # 发送回复
                await message.reply(content=reply_content)
            else:
                # 错误处理
                await message.reply(content="获取黄历失败")
                
    return True
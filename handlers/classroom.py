"""空教室查询处理器"""
import aiohttp
from bs4 import BeautifulSoup
from botpy import BotAPI
from botpy.ext.command_util import Commands
from botpy.message import GroupMessage


@Commands("/空教室")
async def query_empty_classroom(api: BotAPI, message: GroupMessage, params=None):
    """查询空教室"""
    try:
        help_text = (
            "📘 **空教室查询帮助**\n"
            "用法：/空教室 [教学楼] [楼层] [时间段]\n\n"
            "🏫 教学楼：A B C D E 信息楼 体育馆 大活 实验二楼 实验六楼 四 七\n"
            "🏢 楼层：0(全部) 或 1–5\n"
            "⏰ 时间段：\n"
            "1️⃣ 08:00～09:40\n"
            "2️⃣ 09:55～11:35\n"
            "3️⃣ 13:30～15:10\n"
            "4️⃣ 15:25～17:10\n"
            "5️⃣ 18:00～19:30\n"
            "6️⃣ 19:35～20:35\n\n"
            "💡 示例：\n"
            "/空教室 A 2 3  → 查询A楼2层第3节的空教室\n"
            "/空教室 D 0 4  → 查询D楼所有楼层第4节的空教室"
        )

        # 无参数或帮助请求
        if not params or params.strip() in ["帮助", "help", "-h", "--help"]:
            await message.reply(content=help_text)
            return True

        args = params.strip().split()

        # 参数不足则报错
        if len(args) < 3:
            await message.reply(content="❌ 参数不足，请使用 `/空教室 帮助` 查看正确格式。")
            return True

        building, floor, time_slot = args[0], args[1], args[2]

        async with aiohttp.ClientSession() as session:
            # 获取默认学年、周次、星期
            async with session.get("https://class.ecust.icu/empty") as resp:
                html = await resp.text()
            soup = BeautifulSoup(html, "html.parser")

            year = soup.select_one('select[name="year"] option[selected]')
            week = soup.select_one('input[name="week"]')
            weekday = soup.select_one('select[name="weekday"] option[selected]')
            year_val = year["value"] if year else "2025-2026-1"
            week_val = week["value"] if week else "1"
            weekday_val = weekday["value"] if weekday else "1"

            # POST 查询
            payload = {
                "year": year_val,
                "week": week_val,
                "weekday": weekday_val,
                "building": building,
                "floor": floor,
                "time_slot": time_slot,
            }
            async with session.post("https://class.ecust.icu/empty", data=payload) as resp:
                result_html = await resp.text()

        # 解析HTML结果
        soup = BeautifulSoup(result_html, "html.parser")
        alert_div = soup.select_one(".alert.alert-info.mb-3")

        if alert_div:
            result_text = alert_div.get_text(strip=True)
            await message.reply(content=f"🏫 空教室查询结果：\n\n{result_text}")
        else:
            await message.reply(content="未查询到结果，请检查参数是否正确。")

    except Exception as e:
        await message.reply(content=f"查询空教室时发生错误：{str(e)}")

    return True

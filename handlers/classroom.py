"""空教室查询处理器"""
import aiohttp
from botpy import BotAPI
from botpy.ext.command_util import Commands
from botpy.message import GroupMessage
from botpy.types.message import MarkdownPayload
import config
import datetime


@Commands("/空教室")
async def query_empty_classroom(api: BotAPI, message: GroupMessage, params=None):
    """查询空教室"""
    try:
        help_text = (
            "## 📘 空教室查询帮助\n\n"
            "用法：`/空教室 [教学楼] [楼层] [时间段]`\n\n"
            "### 🏫 教学楼\n"
            "A B C D E 信息楼 体育馆 大活 实验二楼 实验六楼 四 七 研 八 实验十九楼 商学院 实验11楼 晨园\n\n"
            "### 🏢 楼层\n"
            "0(全部) 或 1–5\n\n"
            "### ⏰ 时间段\n"
            "1️⃣ 08:00～09:40\n"
            "2️⃣ 09:55～11:35\n"
            "3️⃣ 13:30～15:10\n"
            "4️⃣ 15:25～17:10\n"
            "5️⃣ 18:00～19:30\n"
            "6️⃣ 19:35～20:35\n\n"
            "### 💡 示例\n"
            "- `/空教室 A 2 3` → 查询A楼2层第3节的空教室\n"
            "- `/空教室 D 0 4` → 查询D楼所有楼层第4节的空教室\n\n"
            "***\n"
            "Powered by Eric"
        )
        
        # 添加教学楼对应值的说明
        building_info = (
            "\n\n### 📘 教学楼对应值说明\n\n"
            "- A楼 → `A`\n"
            "- B楼 → `B`\n"
            "- C楼 → `C`\n"
            "- D楼 → `D`\n"
            "- E楼 → `E`\n"
            "- 信息楼 → `信息楼`\n"
            "- 体育馆 → `体育馆`\n"
            "- 大学生活动中心 → `大活`\n"
            "- 实验二楼 → `实验二楼`\n"
            "- 实验六楼 → `实验六楼`\n"
            "- 第四教学楼 → `四`\n"
            "- 第七教学楼 → `七`\n"
            "- 研究生楼 → `研`\n"
            "- 第八教学楼 → `八`\n"
            "- 实验十九楼 → `实验十九楼`\n"
            "- 商学院 → `商学院`\n"
            "- 实验十一楼 → `实验11楼`\n"
            "- 晨园 → `晨园`"
        )
        help_text += building_info

        # 无参数或帮助请求
        if not params or params.strip() in ["帮助", "help", "-h", "--help"]:
            markdown = MarkdownPayload(content=help_text)
            await message.reply(markdown=markdown, msg_type=2)
            return True

        args = params.strip().split()

        # 参数不足则报错
        if len(args) < 3:
            await message.reply(content="❌ 参数不足，请使用 `/空教室 帮助` 查看正确格式。")
            return True

        building, floor, time_slot = args[0], args[1], args[2]

        # 获取app_key
        app_key = config.CLASS_API_KEY
        if not app_key:
            await message.reply(content="❌ 未配置API密钥，请联系管理员。")
            return True

        async with aiohttp.ClientSession() as session:
            # 获取当前学期和周次
            base_params = {"appkey": app_key}
            
            # 获取当前学期
            async with session.get("https://class.ecust.icu/api/get_current_term", params=base_params) as resp:
                term_data = await resp.json()
                term = term_data.get("data", "2025-2026-1")
                
            # 获取当前周次
            async with session.get("https://class.ecust.icu/api/get_current_week", params=base_params) as resp:
                week_data = await resp.json()
                week = week_data.get("data", 1)
                
            # 动态获取当前星期几 (1-7, 周一为1)
            weekday = datetime.datetime.now().isoweekday()

            # 构造查询参数
            query_params = {
                "appkey": app_key,
                "term": term,
                "week": week,
                "weekday": weekday,
                "building": building,
                "level": floor,
                "during_ids": time_slot
            }
            
            # 发送查询请求
            async with session.get(
                "https://class.ecust.icu/api/find_raw_rooms",
                params=query_params
            ) as resp:
                result = await resp.json()

        # 解析结果
        if result.get("code") == 2000 and result.get("data"):
            classrooms = result["data"]
            if isinstance(classrooms, list):
                classroom_list = "\n".join([f"- 🏫 {room}" for room in classrooms])
                response_text = f"### 📚 查询结果\n\n共 **{len(classrooms)}** 间空教室\n\n{classroom_list}"
            else:
                response_text = f"### 📚 查询结果\n\n{classrooms}"
                
            response_text += "\n\n***\nPowered by Eric"
            markdown = MarkdownPayload(content=response_text)
            await message.reply(markdown=markdown, msg_type=2)
        else:
            error_msg = result.get("message", "未知错误")
            await message.reply(content=f"❌ 查询失败：{error_msg}")

    except Exception as e:
        await message.reply(content=f"查询空教室时发生错误：{str(e)}")

    return True
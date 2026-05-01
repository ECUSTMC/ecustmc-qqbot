"""Minecraft相关处理器"""
import asyncio
from mcrcon import MCRcon
from botpy import BotAPI
from botpy.ext.command_util import Commands
from botpy.message import GroupMessage
from botpy.types.message import MarkdownPayload, KeyboardPayload
from config import MC_RCON_PASSWORD, MC_SERVER, MC_RCON_PORT


# MC按钮回调data到命令的映射
MC_BUTTON_ACTIONS = {
    "mc_list": "list",
    "mc_永昼机": "永昼机",
    "mc_关闭永昼机": "关闭永昼机",
}


async def execute_mc_command(api: BotAPI, mc_command: str):
    """执行MC命令并返回Markdown格式的回复内容，出错返回None"""
    rcon_password = MC_RCON_PASSWORD
    rcon_host = MC_SERVER
    rcon_port = MC_RCON_PORT

    if mc_command == "永昼机":
        try:
            with MCRcon(rcon_host, rcon_password, port=rcon_port) as mcr:
                mcr.command("player bot_sleep spawn at -3200 55 9370 facing -90 0 in minecraft:overworld")
            await asyncio.sleep(1)
            with MCRcon(rcon_host, rcon_password, port=rcon_port) as mcr:
                mcr.command("player bot_sleep use interval 20")
            return "## ☀️ 永昼机\n\n**永昼机已启动**"
        except Exception as e:
            return f"❌ 连接 Minecraft 服务器时发生错误: {str(e)}"

    if mc_command == "关闭永昼机":
        try:
            with MCRcon(rcon_host, rcon_password, port=rcon_port) as mcr:
                mcr.command("player bot_sleep kill")
            return "## 🌙 永昼机\n\n**永昼机已关闭**"
        except Exception as e:
            return f"❌ 连接 Minecraft 服务器时发生错误: {str(e)}"

    try:
        with MCRcon(rcon_host, rcon_password, port=rcon_port) as mcr:
            response = mcr.command(mc_command)
        return f"## ⛏️ MC 命令执行\n\n**命令：**`{mc_command}`\n\n> {response}"
    except Exception as e:
        return f"❌ 连接 Minecraft 服务器时发生错误: {str(e)}"


@Commands("/mc")
async def query_mc_command(api: BotAPI, message: GroupMessage, params=None):
    if not params:
        markdown = MarkdownPayload(content="## ⛏️ MC 服务器命令\n\n请选择要执行的命令：")
        keyboard = KeyboardPayload(content={
            "rows": [
                {
                    "buttons": [
                        {
                            "id": "list",
                            "render_data": {"label": "📋 在线列表", "visited_label": "📋 在线列表", "style": 1},
                            "action": {"type": 1, "permission": {"type": 2}, "data": "mc_list", "unsupport_tips": "暂不支持"}
                        },
                        {
                            "id": "say",
                            "render_data": {"label": "💬 说话", "visited_label": "💬 说话", "style": 1},
                            "action": {"type": 2, "permission": {"type": 2}, "data": "/mc say ", "reply": False, "enter": False, "unsupport_tips": "暂不支持"}
                        }
                    ]
                },
                {
                    "buttons": [
                        {
                            "id": "永昼机",
                            "render_data": {"label": "☀️ 永昼机", "visited_label": "☀️ 永昼机", "style": 1},
                            "action": {"type": 1, "permission": {"type": 2}, "data": "mc_永昼机", "unsupport_tips": "暂不支持"}
                        },
                        {
                            "id": "关闭永昼机",
                            "render_data": {"label": "🌙 关闭永昼机", "visited_label": "🌙 关闭永昼机", "style": 1},
                            "action": {"type": 1, "permission": {"type": 2}, "data": "mc_关闭永昼机", "unsupport_tips": "暂不支持"}
                        }
                    ]
                },
                {
                    "buttons": [
                        {
                            "id": "vote_list",
                            "render_data": {"label": "📋 投票列表", "visited_label": "📋 投票列表", "style": 1},
                            "action": {"type": 1, "permission": {"type": 2}, "data": "vote_page_1", "unsupport_tips": "暂不支持"}
                        },
                        {
                            "id": "vote_add",
                            "render_data": {"label": "➕ 添加投票", "visited_label": "➕ 添加投票", "style": 1},
                            "action": {"type": 2, "permission": {"type": 2}, "data": "/vote add ", "reply": False, "enter": False, "unsupport_tips": "暂不支持"}
                        }
                    ]
                }
            ]
        })
        await message.reply(markdown=markdown, keyboard=keyboard, msg_type=2)
    else:
        mc_command = params

        if mc_command not in {"list", "永昼机", "关闭永昼机"} and not any(mc_command.startswith(prefix) for prefix in ["say", "tp"]):
            await message.reply(content="请提供合法的 Minecraft 服务器命令（say/list/永昼机/关闭永昼机）")
        else:
            reply_content = await execute_mc_command(api, mc_command)
            markdown = MarkdownPayload(content=reply_content)
            await message.reply(markdown=markdown, msg_type=2)
    return True
"""Minecraft相关处理器"""
from mcrcon import MCRcon
from botpy import BotAPI
from botpy.ext.command_util import Commands
from botpy.message import GroupMessage
from botpy.types.message import MarkdownPayload
from config import MC_RCON_PASSWORD, MC_SERVER, MC_RCON_PORT
import time


@Commands("/mc")
async def query_mc_command(api: BotAPI, message: GroupMessage, params=None):
    # 通过配置获取 RCON 信息
    rcon_password = MC_RCON_PASSWORD
    rcon_host = MC_SERVER
    rcon_port = MC_RCON_PORT

    if not params:
        await message.reply(content="请提供 Minecraft 服务器命令（say/list/永昼机/关闭永昼机）")
    else:
        # 直接使用 params 作为 Minecraft 命令
        mc_command = params

        if mc_command == "永昼机":
            # 特殊处理命令为"永昼机"的情况
            try:
                with MCRcon(rcon_host, rcon_password, port=rcon_port) as mcr:
                    # 执行多个命令
                    mcr.command("player bot_sleep spawn at -3200 55 9370 facing -90 0 in minecraft:overworld")
                    time.sleep(1)  # 添加1000毫秒延迟
                    mcr.command("player bot_sleep use interval 20")
                    reply_content = "## ☀️ 永昼机\n\n**永昼机已启动**"
                    markdown = MarkdownPayload(content=reply_content)
                    await message.reply(markdown=markdown, msg_type=2)
            except Exception as e:
                await message.reply(content=f"连接 Minecraft 服务器时发生错误: {str(e)}")
            return True

        if mc_command == "关闭永昼机":
            # 特殊处理命令为"关闭永昼机"的情况
            try:
                with MCRcon(rcon_host, rcon_password, port=rcon_port) as mcr:
                    # 执行多个命令
                    mcr.command("player bot_sleep kill")
                    reply_content = "## 🌙 永昼机\n\n**永昼机已关闭**"
                    markdown = MarkdownPayload(content=reply_content)
                    await message.reply(markdown=markdown, msg_type=2)
            except Exception as e:
                await message.reply(content=f"连接 Minecraft 服务器时发生错误: {str(e)}")
            return True

        if mc_command not in {"list"} and not any(mc_command.startswith(prefix) for prefix in ["say", "tp"]):
            await message.reply(content="请提供合法的 Minecraft 服务器命令（say/list/永昼机/关闭永昼机）")
        else:
            try:
                # 连接到 RCON 服务器
                with MCRcon(rcon_host, rcon_password, port=rcon_port) as mcr:
                    # 发送命令并获取响应
                    response = mcr.command(mc_command)
                    # 回复命令执行的结果
                    reply_content = f"## ⛏️ MC 命令执行\n\n**命令：**`{mc_command}`\n\n> {response}"
                    markdown = MarkdownPayload(content=reply_content)
                    await message.reply(markdown=markdown, msg_type=2)
            except Exception as e:
                await message.reply(content=f"连接 Minecraft 服务器时发生错误: {str(e)}")
    return True
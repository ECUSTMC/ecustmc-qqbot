"""帮助和工具处理器"""
import urllib.parse
from botpy import BotAPI
from botpy.ext.command_util import Commands
from botpy.message import GroupMessage
from botpy.types.message import MarkdownPayload


@Commands("/帮助")
async def help(api: BotAPI, message: GroupMessage, params=None):
    help_content = (
        "## 👋 欢迎新人！\n\n"
        "为了享受更好的游戏体验，请先注册皮肤站账号。\n\n"
        "🔗 [注册皮肤站](https://mcskin.ecustvr.top/auth/register)\n\n"
        "通过这个站点，你可以自定义和上传你的皮肤，使用联合认证账号登录游戏，便可进入使用 Union 联合认证的其他高校的 Minecraft 服务器游玩，或登录到支持 Union OAuth 登录的网站。\n\n"
        "***\n\n"
        "- 🔗 [萌新指南](https://mc.ecustvr.top/tutorial)：游戏、启动器及账号配置\n"
        "- 🔗 [QQBot帮助](https://mc.ecustvr.top/qqbot)：bot指令帮助\n\n"
        "祝游戏愉快！"
    )
    
    markdown = MarkdownPayload(content=help_content)
    await message.reply(markdown=markdown, msg_type=2)
    return True


@Commands("/wiki")
async def wiki(api: BotAPI, message: GroupMessage, params=None):
    if params:
        # 获取指令后的关键字
        query = ''.join(params)
        # 对查询关键词进行URL编码
        encoded_query = urllib.parse.quote(query)
        # 生成Wiki链接
        wiki_link = f"https://mc.ecustvr.top/wiki/{encoded_query}"
        
        reply_content = f"## 📚 Wiki 查询\n\n[点击访问Wiki]({wiki_link})"
        
        markdown = MarkdownPayload(content=reply_content)
        await message.reply(markdown=markdown, msg_type=2)
    else:
        await message.reply(content="⚠️ 请提供要查询的Wiki页面关键字！例如 /wiki 门")
    
    return True
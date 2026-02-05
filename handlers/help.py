"""帮助和工具处理器"""
import urllib.parse
from botpy import BotAPI
from botpy.ext.command_util import Commands
from botpy.message import GroupMessage


@Commands("/帮助")
async def help(api: BotAPI, message: GroupMessage, params=None):
    help_content = (
        "\n👋 欢迎新人！\n"
        "为了享受更好的游戏体验，请先注册皮肤站账号。\n"
        "🔗 访问链接： https://mcskin.ecustvr.top/auth/register\n"
        "通过这个站点，你可以自定义和上传你的皮肤，使用联合认证账号登录游戏，便可进入使用 Union 联合认证的其他高校的 Minecraft 服务器游玩，或登录到支持 Union OAuth 登录的网站。\n"
        "更多关于游戏、启动器及账号配置等，欢迎访问 🔗萌新指南：https://mc.ecustvr.top/tutorial\n"
        "更多关于bot指令的帮助，欢迎访问 🔗QQBot：https://mc.ecustvr.top/qqbot，祝游戏愉快！"
    )
    
    await message.reply(content=help_content)
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
        
        reply_content = f"\n📚 你可以查看相关信息： \n🔗点击访问Wiki：{wiki_link}"
        
        await message.reply(content=reply_content)
    else:
        await message.reply(content="⚠️ 请提供要查询的Wiki页面关键字！例如 /wiki 门")
    
    return True
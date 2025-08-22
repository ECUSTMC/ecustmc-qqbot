"""机器人客户端"""
import asyncio
import aiohttp
import botpy
from botpy import BotAPI
from botpy.manage import GroupManageEvent
from botpy.message import GroupMessage

# 导入所有处理器
from handlers.weather import query_weather
from handlers.server import query_ecustmc_server, add_server, remove_server, query_server_status
from handlers.daily import daily_word, daily_huangli, daily_notice
from handlers.fortune import jrys, jrrp, query_tarot, query_divinatory_symbol
from handlers.help import help, wiki
from handlers.entertainment import query_vv
from handlers.ai import query_deepseek_r1, query_deepseek_chat
from handlers.network_tools import query_ip_info, query_domain_info, ping_info
from handlers.minecraft import query_mc_command
from handlers.group_management import find_group, internal_find_group

from config import APPID, SECRET

_log = botpy.logging.get_logger()

# 全局会话对象
session: aiohttp.ClientSession


async def on_ecustmc_backend_error(message: GroupMessage):
    """后端错误处理"""
    await message.reply(content=f"服务无响应，请稍后再试，若此问题依然存在，请联系机器人管理员")


# 所有处理器列表
handlers = [
    query_weather,
    query_ecustmc_server,
    daily_word,
    daily_huangli,
    daily_notice,
    jrrp,
    jrys,
    help,
    wiki,
    add_server,
    remove_server,
    query_tarot,
    query_vv,
    query_deepseek_r1,
    query_deepseek_chat,
    query_divinatory_symbol,
    query_ip_info,
    query_domain_info,
    query_mc_command,
    ping_info,
    query_server_status,
    find_group
]


class EcustmcClient(botpy.Client):
    """ECUST Minecraft QQ机器人客户端"""
    
    async def on_ready(self):
        """机器人就绪事件"""
        _log.info(f"robot[{self.robot.name}] is ready.")

    async def on_group_at_message_create(self, message: GroupMessage):
        """群组@消息处理"""
        for handler in handlers:
            if await handler(api=self.api, message=message):
                return
        
        # 如果没有处理器处理，尝试群组查找
        user_input = message.content.strip().replace("群", "")
        if user_input:
            try:
                await internal_find_group(api=self.api, message=message, search_key=user_input)
                return
            except Exception as e:
                # 错误处理，防止群组查找失败时崩溃
                await message.reply(content=f"调用出错: {str(e)}")
        else:
            # 如果用户没有输入内容
            await message.reply(content=f"不明白你在说什么哦(๑• . •๑)")

    async def on_group_add_robot(self, message: GroupManageEvent):
        """机器人被添加到群组事件"""
        await self.api.post_group_message(
            group_openid=message.group_openid, 
            content="欢迎使用ECUST-Minecraft QQ Bot服务"
        )

    async def on_group_del_robot(self, event: GroupManageEvent):
        """机器人被移出群组事件"""
        _log.info(f"robot[{self.robot.name}] left group ${event.group_openid}")


async def main():
    """主函数"""
    global session
    session = aiohttp.ClientSession()
    
    intents = botpy.Intents(public_messages=True)
    client = EcustmcClient(intents=intents, is_sandbox=False, log_level=30, timeout=60)
    
    try:
        await client.start(appid=APPID, secret=SECRET)
    finally:
        await session.close()


if __name__ == "__main__":
    asyncio.run(main())
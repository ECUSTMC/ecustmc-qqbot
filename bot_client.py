"""机器人客户端"""
import asyncio
import aiohttp
import botpy
from botpy import BotAPI
from botpy.manage import GroupManageEvent
from botpy.message import GroupMessage, DirectMessage
from botpy.types.message import MarkdownPayload, KeyboardPayload

# 导入所有处理器
from handlers.weather import query_weather
from handlers.server import query_ecustmc_server, add_server, remove_server, query_server_status
from handlers.daily import daily_word, daily_huangli, daily_notice
from handlers.fortune import jrys, jrrp, query_tarot, query_divinatory_symbol
from handlers.help import help, wiki
from handlers.entertainment import query_vv, query_deltaforce_password
from handlers.ai import chat_with_deepseek, switch_model, list_models, direct_chat_with_clawdbot, group_chat_with_clawdbot
from handlers.network_tools import query_ip_info, query_domain_info, ping_info
from handlers.minecraft import query_mc_command, MC_BUTTON_ACTIONS, execute_mc_command
from handlers.vote import query_vote, handle_vote_interaction
from handlers.group_management import find_group, internal_find_group
from handlers.bus import query_bus
from handlers.classroom import query_empty_classroom

from config import APPID, SECRET, AI_GROUP_ENABLED, AI_DIRECT_ENABLED
import config

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
    query_divinatory_symbol,
    query_empty_classroom,
    query_ip_info,
    query_domain_info,
    query_mc_command,
    ping_info,
    query_server_status,
    find_group,
    query_bus,
    query_deltaforce_password,
    chat_with_deepseek,
    list_models,
    switch_model,
    query_vote
]


class EcustmcClient(botpy.Client):
    """ECUST Minecraft QQ机器人客户端"""
    
    async def on_ready(self):
        """机器人就绪事件"""
        _log.info(f"robot[{self.robot.name}] is ready.")

    async def on_c2c_message_create(self, message: DirectMessage):
        """私聊消息处理"""
        # 私聊与群聊使用相同的处理器和AI逻辑
        for handler in handlers:
            if await handler(api=self.api, message=message):
                return
        
        if AI_DIRECT_ENABLED:
            try:
                if await direct_chat_with_clawdbot(api=self.api, message=message):
                    return
            except Exception as e:
                _log.error(f"私聊AI调用失败: {str(e)}")
                user_input = message.content.strip().replace("群", "")
                if user_input:
                    try:
                        await internal_find_group(api=self.api, message=message, search_key=user_input)
                        return
                    except Exception as find_error:
                        await message.reply(content=f"调用出错: {str(find_error)}")
                else:
                    await message.reply(content=f"调用出错: {str(e)}")
        else:
            user_input = message.content.strip().replace("群", "")
            if user_input:
                try:
                    await internal_find_group(api=self.api, message=message, search_key=user_input)
                    return
                except Exception as e:
                    await message.reply(content=f"调用出错: {str(e)}")
            else:
                await message.reply(content=f"不明白你在说什么哦(๑• . •๑)")

    async def on_group_at_message_create(self, message: GroupMessage):
        """群组@消息处理"""
        for handler in handlers:
            if await handler(api=self.api, message=message):
                return
        
        if AI_GROUP_ENABLED:
            try:
                if await group_chat_with_clawdbot(api=self.api, message=message):
                    return
            except Exception as e:
                _log.error(f"群聊AI调用失败: {str(e)}")
                user_input = message.content.strip().replace("群", "")
                if user_input:
                    try:
                        await internal_find_group(api=self.api, message=message, search_key=user_input)
                        return
                    except Exception as find_error:
                        await message.reply(content=f"调用出错: {str(find_error)}")
                else:
                    await message.reply(content=f"调用出错: {str(e)}")
        else:
            user_input = message.content.strip().replace("群", "")
            if user_input:
                try:
                    await internal_find_group(api=self.api, message=message, search_key=user_input)
                    return
                except Exception as e:
                    await message.reply(content=f"调用出错: {str(e)}")
            else:
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

    async def on_interaction_create(self, interaction):
        """处理消息按钮交互事件（INTERACTION_CREATE）"""
        try:
            interaction_id = interaction.id       # 交互ID，用于on_interaction_result
            msg_event_id = interaction.event_id   # WebSocket事件ID，用于post_group_message/post_c2c_message的被动回复
            button_data = interaction.data.resolved.button_data if interaction.data and interaction.data.resolved else None
            group_openid = interaction.group_openid

            if not button_data:
                await self.api.on_interaction_result(interaction_id=interaction_id, code=1)
                return

            # 处理MC按钮回调
            if button_data in MC_BUTTON_ACTIONS:
                mc_command = MC_BUTTON_ACTIONS[button_data]
                reply_content = await execute_mc_command(self.api, mc_command)
                markdown = MarkdownPayload(content=reply_content)
                # 先回应交互事件成功
                await self.api.on_interaction_result(interaction_id=interaction_id, code=0)
                # 根据群聊/私聊选择对应的被动回复接口
                if group_openid:
                    # 群聊：用event_id发送被动回复消息，不算主动消息
                    await self.api.post_group_message(
                        group_openid=group_openid,
                        markdown=markdown,
                        msg_type=2,
                        event_id=msg_event_id
                    )
                else:
                    # 私聊：用event_id发送被动回复消息
                    user_openid = interaction.user_openid
                    await self.api.post_c2c_message(
                        openid=user_openid,
                        markdown=markdown,
                        msg_type=2,
                        event_id=msg_event_id
                    )
            elif button_data and button_data.startswith("vote_"):
                if not config.MCVOTE_API_URL or not config.MCVOTE_API_TOKEN:
                    await self.api.on_interaction_result(interaction_id=interaction_id, code=1)
                    return
                voter_id = getattr(interaction, 'group_member_openid', None) or getattr(interaction, 'user_openid', None) or ''
                reply = await handle_vote_interaction(self.api, button_data, voter_id)
                if reply:
                    await self.api.on_interaction_result(interaction_id=interaction_id, code=0)
                    if isinstance(reply, dict):
                        if "content" in reply:
                            send_kwargs = {"content": reply["content"], "msg_type": 0, "event_id": msg_event_id}
                            if group_openid:
                                await self.api.post_group_message(group_openid=group_openid, **send_kwargs)
                            else:
                                await self.api.post_c2c_message(openid=voter_id, **send_kwargs)
                        else:
                            md = MarkdownPayload(content=reply["markdown"])
                            kb = reply.get("keyboard")
                            send_kwargs = {"markdown": md, "msg_type": 2, "event_id": msg_event_id}
                            if kb:
                                send_kwargs["keyboard"] = KeyboardPayload(content={"rows": kb})
                            if group_openid:
                                await self.api.post_group_message(group_openid=group_openid, **send_kwargs)
                            else:
                                await self.api.post_c2c_message(openid=voter_id, **send_kwargs)
                    else:
                        send_kwargs = {"content": reply, "msg_type": 0, "event_id": msg_event_id}
                        if group_openid:
                            await self.api.post_group_message(group_openid=group_openid, **send_kwargs)
                        else:
                            await self.api.post_c2c_message(openid=voter_id, **send_kwargs)
                else:
                    await self.api.on_interaction_result(interaction_id=interaction_id, code=1)
            else:
                # 未知按钮data，回应失败
                await self.api.on_interaction_result(interaction_id=interaction_id, code=1)

        except Exception as e:
            _log.error(f"处理交互事件失败: {str(e)}")
            try:
                await self.api.on_interaction_result(interaction_id=interaction.id, code=1)
            except Exception:
                pass


async def main():
    """主函数"""
    global session
    session = aiohttp.ClientSession()
    
    intents = botpy.Intents(
        direct_message=True,
        public_messages=True,
        interaction=True
    )
    client = EcustmcClient(intents=intents, is_sandbox=False, log_level=30, timeout=60)
    
    try:
        await client.start(appid=APPID, secret=SECRET)
    finally:
        await session.close()


if __name__ == "__main__":
    asyncio.run(main())
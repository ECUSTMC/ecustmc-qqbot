"""机器人客户端"""
import asyncio
import aiohttp
import botpy
from botpy.manage import GroupManageEvent
from botpy.message import GroupMessage, DirectMessage
from botpy.types.message import MarkdownPayload

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
from handlers.vote import query_vote
from handlers.group_management import find_group, internal_find_group
from handlers.bus import query_bus
from handlers.classroom import query_empty_classroom
from handlers.peek_detect import peek_detect

# 应用「群消息全量模式」SDK 补丁（必须在 Client 实例化之前导入）
from utils.group_message_patch import apply_group_message_patch
# 应用「回复 msg_seq 自动递增」补丁，根治 40054005「消息被去重」
from utils.reply_seq import apply_reply_seq_patch
from utils.reply import safe_reply
from utils import group_trigger
from utils.group_trigger import is_triggerable, deduper, describe_message

from handlers.authorize import authorize_group

from config import APPID, SECRET, AI_GROUP_ENABLED, AI_DIRECT_ENABLED, FULL_MESSAGE_DEBUG
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
    query_vote,
    peek_detect,
    authorize_group
]


class EcustmcClient(botpy.Client):
    """ECUST Minecraft QQ机器人客户端"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 机器人自己的 openid：全量模式下判断消息里有没有 @ 机器人
        self.robot_id = None

    async def on_ready(self):
        """机器人就绪事件"""
        self.robot_id = getattr(self.robot, "id", None)
        _log.info(f"robot[{self.robot.name}] is ready. robot_id={self.robot_id}")

    @staticmethod
    def _normalize_content(message):
        """content 为空（图片/卡片消息）时补成空串

        botpy 的 ``Commands`` 装饰器会做 ``command in message.content``，
        content 为 None 会直接 TypeError 打断整条处理链。
        """
        if getattr(message, "content", None) is None:
            try:
                message.content = ""
            except AttributeError:  # __slots__ 限制时忽略
                pass

    async def on_c2c_message_create(self, message: DirectMessage):
        """私聊消息处理"""
        self._normalize_content(message)
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
                        _log.error(f"兜底找群失败: {str(find_error)}")
                        await safe_reply(message, content=f"调用出错: {str(find_error)}")
                else:
                    await safe_reply(message, content=f"调用出错: {str(e)}")
        else:
            user_input = message.content.strip().replace("群", "")
            if user_input:
                try:
                    await internal_find_group(api=self.api, message=message, search_key=user_input)
                    return
                except Exception as e:
                    _log.error(f"兜底找群失败: {str(e)}")
                    await safe_reply(message, content=f"调用出错: {str(e)}")
            else:
                await safe_reply(message, content="不明白你在说什么哦(๑• . •๑)")

    async def on_group_at_message_create(self, message: GroupMessage):
        """群组 @机器人 消息处理（保持原有行为）"""
        return await self._handle_group(message, group_full_message=False)

    async def on_group_message_create(self, message: GroupMessage):
        """群消息「全量模式」处理

        机器人被群主授权「接收所有消息」后，群里每条消息都会推送此事件。
        与 @ 事件字段完全一致，因此复用同一个处理入口，
        区别在于：必须是显式命令（/ 前缀）、白名单关键词或明确 @ 了机器人
        的消息才会响应，其余静默丢弃。
        """
        return await self._handle_group(message, group_full_message=True)

    async def _handle_group(self, message: GroupMessage, group_full_message: bool = False):
        """群聊消息统一处理入口

        :param group_full_message: 是否来自全量模式事件（GROUP_MESSAGE_CREATE）
        """
        self._normalize_content(message)

        # 全量模式下先做触发判定，避免「群里聊到 vv」之类被误触发。
        # 注意「判定」必须在「去重」之前：被丢弃的全量消息不能占用 msg_id，
        # 否则同一条消息紧接着以 @事件 到达时会被误判成重复消息直接丢掉，
        # 表现就是「群里 @机器人 反而没反应」。
        if group_full_message and not is_triggerable(
            message, group_full_message=True, bot_id=self.robot_id
        ):
            # 平台会把「@机器人」前缀从 content 里去掉，所以 @ 了机器人
            # 却带不出命令的消息只能靠 mentions 判断，这里把关键信息打出来，
            # 方便排查「@了没反应」。
            if FULL_MESSAGE_DEBUG or group_trigger.has_mentions(message):
                _log.warning(
                    f"[全量消息] 已忽略（非指令 / 未@机器人）: {describe_message(message)}"
                )
            else:
                _log.debug(f"[全量消息] 非触发内容，静默忽略: {describe_message(message)}")
            return

        # 官方提示同一 msg_id 可能重复推送（同一消息也可能同时以
        # GROUP_AT_MESSAGE_CREATE 与 GROUP_MESSAGE_CREATE 到达），按 msg_id 去重
        if deduper.is_duplicate(getattr(message, "id", None)):
            _log.info(f"[全量消息] 重复消息，已忽略 msg_id={getattr(message, 'id', None)}")
            return

        return await self._dispatch_group_handlers(message, group_full_message)

    async def _dispatch_group_handlers(self, message: GroupMessage, group_full_message: bool = False):
        """分发到各处理器；全量模式下禁用「兜底找群 / 兜底 AI」"""
        for handler in handlers:
            if await handler(api=self.api, message=message):
                return

        # 全量模式下绝不走兜底逻辑：
        # 否则群里每一句话都会被 internal_find_group / AI 扫一遍，既误报又限频
        if group_full_message:
            _log.debug(f"[全量消息] 未命中指令，静默忽略: {describe_message(message)}")
            return

        # 兜底回复一律走 safe_reply：即使平台报错（去重 / 限频 / 内容违规）
        # 也只记日志，不再向上抛异常刷 traceback
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
                        _log.error(f"兜底找群失败: {str(find_error)}")
                        await safe_reply(message, content=f"调用出错: {str(find_error)}")
                else:
                    await safe_reply(message, content=f"调用出错: {str(e)}")
        else:
            user_input = message.content.strip().replace("群", "")
            if user_input:
                try:
                    await internal_find_group(api=self.api, message=message, search_key=user_input)
                    return
                except Exception as e:
                    _log.error(f"兜底找群失败: {str(e)}")
                    await safe_reply(message, content=f"调用出错: {str(e)}")
            else:
                await safe_reply(message, content="不明白你在说什么哦(๑• . •๑)")

    async def on_group_add_robot(self, message: GroupManageEvent):
        """机器人被添加到群组事件"""
        try:
            # GROUP_ADD_ROBOT 支持用 event_id 做被动回复（不占主动消息额度）
            await self.api.post_group_message(
                group_openid=message.group_openid,
                content="欢迎使用ECUST-Minecraft QQ Bot服务",
                event_id=getattr(message, "event_id", None),
            )
        except Exception as e:
            _log.error(f"[入群] 群 {message.group_openid} 发送欢迎语失败: {e}")

    async def on_group_del_robot(self, event: GroupManageEvent):
        """机器人被移出群组事件"""
        _log.info(f"robot[{self.robot.name}] left group ${event.group_openid}")

    async def on_group_msg_receive(self, event: GroupManageEvent):
        """群管理员开启「接收所有消息」事件

        收到后该群即开始推送 GROUP_MESSAGE_CREATE（全量消息）。
        """
        _log.info(f"[授权] 群 {event.group_openid} 已开启「接收所有消息」")
        try:
            await self.api.post_group_message(
                group_openid=event.group_openid,
                content=(
                    "✅ 已开启「接收所有消息」授权\n"
                    "现在机器人可以看到本群的全部消息了。\n\n"
                    "为免打扰，机器人只在消息以 / 开头、或明确 @我 时才会响应哦～\n"
                    "试试发送 /帮助 查看可用指令。"
                ),
                event_id=event.event_id,
            )
        except Exception as e:
            _log.error(f"[授权] 群 {event.group_openid} 发送授权成功提示失败: {e}")

    async def on_group_msg_reject(self, event: GroupManageEvent):
        """群管理员关闭「接收所有消息」事件"""
        _log.info(f"[授权] 群 {event.group_openid} 已关闭「接收所有消息」")
        try:
            await self.api.post_group_message(
                group_openid=event.group_openid,
                content="已关闭「接收所有消息」授权，机器人不会再看到未 @ 它的消息。",
                event_id=event.event_id,
            )
        except Exception as e:
            _log.error(f"[授权] 群 {event.group_openid} 发送授权关闭提示失败: {e}")

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

    # 必须在 Client 实例化之前打补丁，否则 ConnectionState.parsers 已构建完毕
    apply_group_message_patch()
    # 回复 msg_seq 自动递增，避免 40054005「消息被去重」
    apply_reply_seq_patch()

    # 以下 INFO 在 Client 实例化（log_level=30）之前打印，是启动时可见的
    group_trigger.FULL_MESSAGE_DEBUG = FULL_MESSAGE_DEBUG
    _log.info(
        "群聊触发规则: 全量消息响应「/ 前缀指令」「白名单关键词 %s」「@机器人」；"
        "@事件 保持原有行为（未命中指令时走兜底）",
        "/".join(sorted(group_trigger.BARE_COMMANDS)) or "(无)",
    )
    if FULL_MESSAGE_DEBUG:
        _log.info("FULL_MESSAGE_DEBUG=true：被忽略的全量消息将以 WARNING 级别输出")

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
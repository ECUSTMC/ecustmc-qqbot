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
# 校园问答（乐享知识库）+ 默认 @ 的兜底路由：先搜群，再由大模型决定发群 or 查知识库
from handlers.kb_qa import handle_default_reply, kb_qa_command

# 应用「群消息全量模式」SDK 补丁（必须在 Client 实例化之前导入）
from utils.group_message_patch import apply_group_message_patch
# 应用「回复 msg_seq 自动递增」补丁，根治 40054005「消息被去重」
from utils.reply_seq import apply_reply_seq_patch
from utils.reply import safe_reply
from utils import group_trigger
from utils import intent
from utils.group_trigger import is_triggerable, deduper, describe_message

from handlers.authorize import authorize_group

from config import APPID, SECRET, AI_GROUP_ENABLED, AI_DIRECT_ENABLED, FULL_MESSAGE_DEBUG
from config import CAMPUS_QA_ENABLED, CAMPUS_QA_REQUESTED
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
    kb_qa_command,
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
        """规范化 content 后再分发给处理器

        - content 为 None（图片/卡片消息）时补成空串：botpy 的 ``Commands``
          装饰器会做 ``command in message.content``，None 会直接 TypeError
          打断整条处理链；
        - 剥掉开头的 ``<@openid>`` 占位符：全量模式下平台不会去掉「@机器人」
          前缀，原样下发 ``"<@93C3B65B...> /通知 "``，不剥掉的话
          ``Commands["/通知"]`` 虽然仍能子串命中，但兜底找群的关键字、
          AI 输入里都会混进这段占位符。
        """
        raw = getattr(message, "content", None)
        if raw is None:
            raw = ""
        try:
            message.content = group_trigger.strip_leading_mentions(raw)
        except AttributeError:  # __slots__ 限制时忽略
            pass

    async def on_c2c_message_create(self, message: DirectMessage):
        """私聊消息处理"""
        self._normalize_content(message)
        # 私聊与群聊使用相同的处理器和AI逻辑
        for handler in handlers:
            if await handler(api=self.api, message=message):
                return

        # 兜底：先判断是不是找群，不是就用知识库回答学校相关问题
        ai_chat = direct_chat_with_clawdbot if AI_DIRECT_ENABLED else None
        if await handle_default_reply(api=self.api, message=message, ai_chat=ai_chat):
            return

        if not (message.content or "").strip():
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
        # 不响应任何机器人（含自己）发的消息：全量模式下机器人自己的消息也会推送，
        # 若其内容恰好以 / 开头（转述指令、回显等）就会形成自问自答的死循环
        if getattr(getattr(message, "author", None), "bot", None) is True:
            _log.debug(f"[群消息] 忽略机器人发的消息: {describe_message(message)}")
            return

        # 全量模式下先做触发判定，避免「群里聊到 vv」之类被误触发。
        # 注意「判定」必须在「去重」之前：被丢弃的全量消息不能占用 msg_id，
        # 否则同一条消息紧接着以 @事件 到达时会被误判成重复消息直接丢掉，
        # 表现就是「群里 @机器人 反而没反应」。
        # 另外这里用**原始 content** 判定/打日志（平台会下发 "@机器人 <@openid>"
        # 前缀），剥离占位符放到分发之前做。
        if group_full_message and not is_triggerable(
            message, group_full_message=True, bot_ids=(self.robot_id,)
        ):
            # 全量模式下平台**不会**去掉「@机器人」前缀，content 形如
            # "<@93C3B65B...> /通知"，被忽略时打出来便于排查「@了没反应」
            if FULL_MESSAGE_DEBUG or group_trigger.has_mentions(message):
                _log.warning(f"[全量消息] 已忽略（非指令 / 未@机器人）: {describe_message(message)}")
            else:
                _log.debug(f"[全量消息] 非触发内容，静默忽略: {describe_message(message)}")
            return

        # 官方提示同一 msg_id 可能重复推送（同一消息也可能同时以
        # GROUP_AT_MESSAGE_CREATE 与 GROUP_MESSAGE_CREATE 到达），按 msg_id 去重
        if deduper.is_duplicate(getattr(message, "id", None)):
            _log.info(f"[全量消息] 重复消息，已忽略 msg_id={getattr(message, 'id', None)}")
            return

        # 交给处理器之前再规范化 content（剥掉开头的 <@openid> 占位符）
        self._normalize_content(message)

        return await self._dispatch_group_handlers(message, group_full_message)

    async def _dispatch_group_handlers(self, message: GroupMessage, group_full_message: bool = False):
        """分发到各处理器；未命中时走「找群 / 校园问答」兜底

        **全量消息模式（群里每条消息都能看到）只做零成本响应**：
        只有明确在找群的说法（``有没有XX群`` / ``找XX群`` / ``拉我进群`` / ``群号``）
        才去搜一次群并回复，其余一律静默 —— 全量模式下一旦调用大模型或知识库，
        账单和限频都会爆炸。

        @ 事件（``GROUP_AT_MESSAGE_CREATE``）与私聊不受此限制，走完整的
        找群 / 校园问答流程。
        """
        for handler in handlers:
            if await handler(api=self.api, message=message):
                return

        if group_full_message:
            text = (getattr(message, "content", "") or "").strip()
            if not intent.is_explicit_group_search(text):
                _log.debug(f"[全量消息] 未命中指令，静默忽略: {describe_message(message)}")
                return
            keyword = intent.extract_group_keyword(text) or text
            _log.info(f"[全量消息] 明确找群 keyword={keyword!r}，只搜群不调用知识库")
            try:
                await internal_find_group(api=self.api, message=message, search_key=keyword)
            except Exception as e:  # noqa: BLE001 - 兜底不允许把异常抛回消息循环
                _log.error(f"全量消息找群失败: {e}")
                await safe_reply(message, content=f"调用出错: {e}")
            return

        # 兜底：先搜一遍群表，再由大模型判断「发群结果」还是「查知识库」；
        # 回复一律走 safe_reply，失败只记日志不抛异常
        ai_chat = group_chat_with_clawdbot if AI_GROUP_ENABLED else None
        try:
            if await handle_default_reply(api=self.api, message=message, ai_chat=ai_chat):
                return
        except Exception as e:  # noqa: BLE001 - 兜底不允许把异常抛回消息循环
            _log.error(f"兜底回复失败: {e}")
            await safe_reply(message, content=f"调用出错: {e}")
            return

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
        "群聊触发规则: 全量消息响应「指令前缀 / ／」「白名单关键词 %s」「@机器人」"
        "「明确的找群句式：有没有XX群 / 找XX群 / 拉我进群 / 群号」"
        "（平台下发的 content 形如 '<@openid> /通知'，开头占位符会被自动剥离）；"
        "@事件 保持原有行为（未命中指令时走完整兜底：先搜群，再决定发群或查知识库）",
        "/".join(sorted(group_trigger.BARE_COMMANDS)) or "(无)",
    )
    if FULL_MESSAGE_DEBUG:
        _log.info("FULL_MESSAGE_DEBUG=true：被忽略的全量消息将以 WARNING 级别输出")

    # 默认 @ 的兜底规则：先搜群 → 大模型判断 → 发群结果 / 查知识库 / 走 AI 对话
    if CAMPUS_QA_ENABLED:
        _log.info(
            "默认回复规则: @我 → ①先搜一遍飞书群表（明确找群直接答复，只发可信群）→ "
            "②由 %s 判断（send_group / query_kb）→ ③发群结果 和/或 查知识库"
            "（知识库回答里的插图按 QQ markdown 语法内嵌在同一条卡片里），"
            "都不是则交给已有的 AI 对话（AI_GROUP_ENABLED=%s）；知识范围=%s, qa_mode=%s；"
            "路由入口=%s；全量消息模式只响应明确的找群句式（不调用大模型/知识库）",
            config.ROUTER_MODEL or "(未配置，走规则)",
            AI_GROUP_ENABLED,
            config.LEXIANG_TARGETS or "全站知识",
            config.LEXIANG_QA_MODE,
            config.ROUTER_URL or "(未配置)",
        )
        try:
            from utils.lexiang_client import LexiangClient

            async with LexiangClient() as _client:
                verified = await _client.verify_targets()
            if verified["ok"] and verified["spaces"]:
                for space in verified["spaces"]:
                    _log.info(
                        "校园问答知识库已核实: %s（space id=%s，团队=%s）",
                        space["name"] or "(未知)",
                        space["id"],
                        space["team_id"] or "-",
                    )
            else:
                _log.warning("校园问答知识库核实失败: %s", verified.get("error") or "无 space 目标")
        except Exception as e:  # noqa: BLE001 - 启动自检失败不影响运行
            _log.warning("校园问答知识库核实异常: %s", e)
    elif CAMPUS_QA_REQUESTED:
        _log.warning(
            "CAMPUS_QA_ENABLED=true 但缺少 LEXIANG_APP_KEY / LEXIANG_APP_SECRET，"
            "校园问答已自动关闭，默认回复会退回旧逻辑（找群）"
        )
    else:
        _log.info("校园问答未启用（CAMPUS_QA_ENABLED=false），默认回复保持旧逻辑（找群）")

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
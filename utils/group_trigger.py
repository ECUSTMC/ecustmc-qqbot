"""群聊消息触发判定与去重

接入「群消息全量模式」后，群里每一条消息都会推送过来，
必须严格限定「什么消息才值得响应」，否则：
1. botpy.ext.command_util.Commands 是子串匹配（`if command in content`），
   群里聊到「vv」「找群」就会误触发；
2. 兜底逻辑（internal_find_group / AI）会把每句话都扫一遍，触发限频；
3. 被动回复有 5 分钟 / 每条消息 5 次的限制，滥回会被风控。

本模块提供：
- is_triggerable(): 判断消息是否允许机器人响应
  （命令前缀 / 白名单关键词 / 全量模式下 @了机器人）
- MessageDeduper: 按 msg_id 去重（官方提示相同 msg_id 可能重复推送）
- describe_message(): 打印消息关键信息，便于排查「为什么没反应」
"""

import time
from collections import OrderedDict

# 允许无前缀、纯关键词触发的指令白名单（仅在 @机器人 时生效）
BARE_COMMANDS = {"vv"}

# 群聊中只有带这些前缀的消息才会被响应（避免误触发）
COMMAND_PREFIXES = ("/", "／")

# 去重缓存容量与过期时间
_DEDUP_MAX_SIZE = 4096
_DEDUP_TTL = 300  # 秒

# 是否把被忽略的全量消息也打成 WARNING（排查「@了没反应」时打开）
FULL_MESSAGE_DEBUG = False


def _content_of(message) -> str:
    content = getattr(message, "content", None) or ""
    return content.strip()


def is_command(content: str) -> bool:
    """是否以命令前缀开头"""
    return bool(content) and content.startswith(COMMAND_PREFIXES)


def is_bare_command(content: str) -> bool:
    """是否命中无前缀关键词指令（如 vv）"""
    return content.strip().lower() in BARE_COMMANDS


def _mention_ids(message) -> list:
    """取出消息里 @ 到的用户 id 列表"""
    ids = []
    for user in getattr(message, "mentions", None) or []:
        for attr in ("id", "member_openid", "union_openid"):
            value = getattr(user, attr, None)
            if value:
                ids.append(str(value))
                break
    return ids


def has_mentions(message) -> bool:
    """消息是否 @ 了任何人"""
    return bool(_mention_ids(message))


def mentions_bot(message, bot_id=None) -> bool:
    """消息是否 @ 了机器人自己

    全量模式（GROUP_MESSAGE_CREATE）下平台会把「@机器人」前缀从 content 里
    去掉，所以只能靠 mentions 判断；拿不到机器人 id 时保守返回 False。
    """
    if not bot_id:
        return False
    return str(bot_id) in _mention_ids(message)


def is_triggerable(message, group_full_message: bool = False, bot_id=None) -> bool:
    """判断群聊消息是否允许机器人响应

    - @机器人 事件（GROUP_AT_MESSAGE_CREATE）：保持原有行为，全部交给 handler
    - 全量消息（GROUP_MESSAGE_CREATE）：只响应
      ① 命令前缀开头 ② 白名单关键词 ③ 明确 @ 了机器人的消息，其余静默丢弃
    """
    if not group_full_message:
        return True

    content = _content_of(message)
    if not content:
        # 图片 / 卡片 / 引用消息：全量模式下不主动响应，避免噪音
        return False

    if is_command(content) or is_bare_command(content):
        return True

    # 「@机器人 你好」这种没有命令前缀的消息：content 里的 @ 已被平台去掉，
    # 只能通过 mentions 里有没有机器人自己来判断
    return mentions_bot(message, bot_id)


def describe_message(message) -> str:
    """给日志用的一句话描述（content 截断、mentions 只留前 8 位）"""
    content = (getattr(message, "content", None) or "").replace("\n", " ")
    mentions = [mid[:8] for mid in _mention_ids(message)]
    author = getattr(message, "author", None)
    author_id = getattr(author, "member_openid", None) or getattr(author, "id", None)
    return (
        f"content={content[:40]!r} "
        f"type={getattr(message, 'message_type', None)} "
        f"author={str(author_id)[:8]} "
        f"mentions={mentions}"
    )


class MessageDeduper:
    """按 msg_id 去重（同一 msg_id 可能被重复推送）"""

    def __init__(self, max_size: int = _DEDUP_MAX_SIZE, ttl: int = _DEDUP_TTL):
        self._seen = OrderedDict()
        self._max_size = max_size
        self._ttl = ttl

    def is_duplicate(self, msg_id: str) -> bool:
        """返回 True 表示该消息已处理过"""
        if not msg_id:
            return False

        now = time.time()
        # 清理过期项
        while self._seen:
            key, ts = next(iter(self._seen.items()))
            if now - ts > self._ttl or len(self._seen) > self._max_size:
                self._seen.popitem(last=False)
            else:
                break

        if msg_id in self._seen:
            self._seen[msg_id] = now
            self._seen.move_to_end(msg_id)
            return True

        self._seen[msg_id] = now
        return False


# 全局去重器
deduper = MessageDeduper()

"""被动回复 msg_seq 自动递增补丁（根治 40054005「消息被去重」）

官方规则（开放平台文档「消息收发概述 / 消息去重」）::

    相同 msg_id 可能多次推送，请结合 msg_seq 去重。
    被动回复时，相同的 msg_id + msg_seq 重复发送会失败，
    可递增 msg_seq 实现对同一消息的多次回复。

而 ``qq-botpy 1.2.1`` 把 ``msg_seq`` 写死成默认值 ``1``
（``botpy/api.py: post_group_message(..., msg_seq: int = 1)``），
并且 ``GroupMessage.reply()`` / ``C2CMessage.reply()`` 也不会带上序号，于是：

* 对同一条消息回复第二次（错误兜底、先发回执再撤回、多段消息、图片+文字…）
  平台直接返回 ``40054005 消息被去重，请检查请求msgseq``；
* 主动消息（没有 ``msg_id``）用固定 ``msg_seq=1`` 连发也会被判重。

本模块在 ``BotAPI`` 上包一层：

* 调用方**没有**显式传 ``msg_seq`` 时，按「同一个 ``msg_id`` / ``event_id`` /
  同一个会话（群、单聊）」自动分配递增序号；
* 调用方显式传了 ``msg_seq``（例如 peek_detect 的第二条消息用 2）就以调用方的
  为准，并同步内部计数，避免后续自动分配撞号。

补丁幂等，重复调用不会重复包装。
"""

import time
from collections import OrderedDict

import botpy
from botpy.api import BotAPI

_log = botpy.logging.get_logger()

_PATCH_FLAG = "_ecustmc_reply_seq_patched"

# 被动回复有效期 5 分钟，多留 1 分钟余量
_SEQ_TTL = 6 * 60
_SEQ_MAX_SIZE = 4096


class _SeqStore:
    """按 key 分配递增 msg_seq（带 TTL / 容量清理）"""

    def __init__(self, ttl: int = _SEQ_TTL, max_size: int = _SEQ_MAX_SIZE):
        self._seqs = OrderedDict()
        self._ttl = ttl
        self._max_size = max_size

    def _gc(self, now: float) -> None:
        while self._seqs:
            key, (_seq, ts) = next(iter(self._seqs.items()))
            if now - ts > self._ttl or len(self._seqs) > self._max_size:
                self._seqs.popitem(last=False)
            else:
                break

    def next(self, key) -> int:
        """取下一个可用序号"""
        now = time.time()
        self._gc(now)
        seq, _ = self._seqs.get(key, (0, now))
        seq += 1
        self._seqs[key] = (seq, now)
        self._seqs.move_to_end(key)
        return seq

    def observe(self, key, seq: int) -> None:
        """记录调用方显式使用的序号，后续自动分配不会撞号"""
        now = time.time()
        self._gc(now)
        old, _ = self._seqs.get(key, (0, now))
        self._seqs[key] = (max(old, int(seq)), now)
        self._seqs.move_to_end(key)


_seq_store = _SeqStore()


def _seq_key(msg_id, event_id, conv_key):
    """被动回复按 msg_id/event_id 计数；主动消息按会话计数"""
    if msg_id:
        return ("msg_id", msg_id)
    if event_id:
        return ("event_id", event_id)
    return ("active", conv_key)


def _resolve_seq(msg_id, event_id, conv_key, msg_seq) -> int:
    key = _seq_key(msg_id, event_id, conv_key)
    if msg_seq is None:
        return _seq_store.next(key)
    try:
        seq = int(msg_seq)
    except (TypeError, ValueError):
        return _seq_store.next(key)
    if seq < 1:
        seq = 1
    _seq_store.observe(key, seq)
    return seq


_orig_post_group_message = None
_orig_post_c2c_message = None


async def _post_group_message(
    self,
    group_openid,
    msg_type: int = 0,
    content: str = None,
    embed=None,
    ark=None,
    message_reference=None,
    media=None,
    msg_id: str = None,
    msg_seq=None,
    event_id: str = None,
    markdown=None,
    keyboard=None,
):
    msg_seq = _resolve_seq(msg_id, event_id, group_openid, msg_seq)
    return await _orig_post_group_message(
        self,
        group_openid=group_openid,
        msg_type=msg_type,
        content=content,
        embed=embed,
        ark=ark,
        message_reference=message_reference,
        media=media,
        msg_id=msg_id,
        msg_seq=msg_seq,
        event_id=event_id,
        markdown=markdown,
        keyboard=keyboard,
    )


async def _post_c2c_message(
    self,
    openid,
    msg_type: int = 0,
    content: str = None,
    embed=None,
    ark=None,
    message_reference=None,
    media=None,
    msg_id: str = None,
    msg_seq=None,
    event_id: str = None,
    markdown=None,
    keyboard=None,
):
    msg_seq = _resolve_seq(msg_id, event_id, openid, msg_seq)
    return await _orig_post_c2c_message(
        self,
        openid=openid,
        msg_type=msg_type,
        content=content,
        embed=embed,
        ark=ark,
        message_reference=message_reference,
        media=media,
        msg_id=msg_id,
        msg_seq=msg_seq,
        event_id=event_id,
        markdown=markdown,
        keyboard=keyboard,
    )


def apply_reply_seq_patch() -> None:
    """应用补丁（在 Client 实例化之前调用即可，之后调用也生效）"""
    global _orig_post_group_message, _orig_post_c2c_message

    if getattr(BotAPI, _PATCH_FLAG, False):
        return

    _orig_post_group_message = BotAPI.post_group_message
    _orig_post_c2c_message = BotAPI.post_c2c_message
    BotAPI.post_group_message = _post_group_message
    BotAPI.post_c2c_message = _post_c2c_message
    setattr(BotAPI, _PATCH_FLAG, True)
    _log.info("已应用「回复 msg_seq 自动递增」SDK 补丁 (去重 40054005)")

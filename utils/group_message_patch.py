"""QQ 群消息「全量模式」SDK 补丁

背景
----
QQ 开放平台在机器人开启「接收所有消息」后，会下发 ``GROUP_MESSAGE_CREATE``
事件（群内每条消息，不限于 @机器人）。该事件与 ``GROUP_AT_MESSAGE_CREATE``
共用 Intent ``GROUP_AND_C2C_EVENT (1 << 25)``，字段结构完全一致。

但 qq-botpy 1.2.1（2024-03）之后未再更新：

* ``botpy/connection.py`` 的 parsers 中没有 ``group_message_create``，
  网关收到该事件只打一行 ``_parser unknown event`` 日志后被静默丢弃；
* ``botpy/message.py`` 的 ``GroupMessage`` / ``_User`` 没有解析
  ``member_role`` / ``message_type`` / ``message_scene`` / ``msg_elements``
  / ``ark_data`` 等新字段，导致群主鉴权、引用回复、卡片消息都拿不到数据。

本模块在导入 bot_client 时（实例化 Client 之前）打补丁，做两件事：

1. 注册 ``group_message_create`` 解析器 → 触发 ``on_group_message_create``
2. 用继承 ``GroupMessage`` 的子类替换 ``botpy.message.GroupMessage``，
   补齐新字段的解析

之所以用「子类替换」而不是直接改 ``__slots__``：``GroupMessage`` 是纯
``__slots__`` 类，运行时修改 ``__slots__`` 不会重建 slot 描述符，赋值仍会
抛 ``AttributeError``。

补丁幂等，重复导入不会重复包装。
"""

import botpy
from botpy.connection import ConnectionState
from botpy.message import GroupMessage as _OriginalGroupMessage, BaseMessage

_log = botpy.logging.get_logger()

_PATCH_FLAG = "_ecustmc_full_message_patched"

# GROUP_MESSAGE_CREATE / GROUP_AT_MESSAGE_CREATE 的新增字段
_EXTRA_SLOTS = (
    "message_type",
    "message_scene",
    "msg_elements",
    "ark_data",
    "msg_idx",
    "auth_token",
)


def _parse_scene_ext(message, key):
    """从 message_scene.ext 中取指定 key 的值

    ``ext`` 形如 ``["msg_idx=REFIDX_xxx==", "auth_token=xxx"]``。
    """
    scene = getattr(message, "message_scene", None) or {}
    for item in scene.get("ext", []) or []:
        if isinstance(item, str) and item.startswith(f"{key}="):
            return item[len(key) + 1:]
    return None


def _build_group_message_class():
    """构造一个解析了新字段的 GroupMessage 子类"""

    class _FullGroupMessage(_OriginalGroupMessage):
        __slots__ = _EXTRA_SLOTS

        def __init__(self, api, event_id, data):
            super().__init__(api, event_id, data)
            self.message_type = data.get("message_type", None)
            self.message_scene = data.get("message_scene", {}) or {}
            self.msg_elements = data.get("msg_elements", []) or []
            self.ark_data = data.get("ark_data", None)
            self.msg_idx = _parse_scene_ext(self, "msg_idx")
            self.auth_token = _parse_scene_ext(self, "auth_token")

        class _User(_OriginalGroupMessage._User):
            __slots__ = ("id", "username", "bot", "union_openid", "member_role")

            def __init__(self, data):
                super().__init__(data)
                self.id = data.get("id", None)
                self.username = data.get("username", None)
                self.bot = data.get("bot", None)
                self.union_openid = data.get("union_openid", None)
                # member=普通成员, admin=管理员, owner=群主
                self.member_role = data.get("member_role", None)

    _FullGroupMessage.__name__ = "GroupMessage"
    _FullGroupMessage.__qualname__ = "GroupMessage"
    return _FullGroupMessage


def _patch_attachments():
    """给附件补充语音 / ASR 字段（子类方式，同上）"""
    if getattr(BaseMessage, _PATCH_FLAG, False):
        return
    original = BaseMessage._Attachments

    class _FullAttachments(original):
        __slots__ = ("voice_wav_url", "asr_refer_text")

        def __init__(self, data):
            super().__init__(data)
            self.voice_wav_url = data.get("voice_wav_url", None)
            self.asr_refer_text = data.get("asr_refer_text", None)

    _FullAttachments.__name__ = original.__name__
    BaseMessage._Attachments = _FullAttachments
    setattr(BaseMessage, _PATCH_FLAG, True)


def _register_full_message_parser(message_cls):
    """注册 group_message_create 解析器（幂等）"""
    if getattr(ConnectionState, _PATCH_FLAG, False):
        return

    def parse_group_message_create(self, payload):
        _message = message_cls(self.api, payload.get("id", None), payload.get("d", {}))
        self._dispatch("group_message_create", _message)

    # 同时替换 group_at_message_create，让 @ 消息也带上新字段
    def parse_group_at_message_create(self, payload):
        _message = message_cls(self.api, payload.get("id", None), payload.get("d", {}))
        self._dispatch("group_at_message_create", _message)

    ConnectionState.parse_group_message_create = parse_group_message_create
    ConnectionState.parse_group_at_message_create = parse_group_at_message_create
    # ConnectionState.__init__ 会遍历 parse_ 前缀方法生成 parsers 字典，
    # 只要在实例化之前挂上这些方法就会自动注册，无需手动改 parsers。
    setattr(ConnectionState, _PATCH_FLAG, True)


def apply_group_message_patch():
    """应用全部补丁（必须在 Client 实例化之前调用）"""
    import botpy.message as _botpy_message

    if not getattr(_botpy_message, _PATCH_FLAG, False):
        message_cls = _build_group_message_class()
        _patch_attachments()
        _botpy_message.GroupMessage = message_cls
        setattr(_botpy_message, _PATCH_FLAG, True)
    else:
        message_cls = _botpy_message.GroupMessage

    _register_full_message_parser(message_cls)
    _log.info("已应用「群消息全量模式」SDK 补丁 (GROUP_MESSAGE_CREATE)")


# 供外部直接取用
PatchedGroupMessage = None

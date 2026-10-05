"""指令权限：限制「谁能用哪些指令」

两套身份判定：

* **机器人管理员（owner）**：``.env`` 里 ``ADMIN_OPENIDS`` 列出的 openid
  （逗号分隔）。给 ``/model``、``/models`` 这类全局性指令用。
  匹配时会把消息作者身上的 openid 都拿出来比一遍（大小写不敏感）：
  群消息的 ``member_openid`` **按群隔离**（同一个人在不同群里值不同）、
  私聊是 ``user_openid``、平台下发 ``union_openid`` 时它跨群稳定。
  第一次配置：先用 ``/我的id`` 查看自己的 openid，填进 ``ADMIN_OPENIDS`` 后重启。
* **群主 / 管理员（group admin）**：平台的 ``message.author.member_role``
  （``owner`` / ``admin`` / ``member``）。给 ``/添加服务器``、``/移除服务器``
  这类会改配置的指令用。取不到身份时按**无权限**处理（fail closed）并打 WARNING，
  避免平台改字段后权限静默失效。

用法（放在 handler 最前面；拒绝时 ``return True`` 终止分发，
否则会继续走默认回复，用户会收到第二句莫名其妙的话）::

    @Commands("/model")
    async def switch_model(api, message, params=None):
        if not await require_owner(message, "/model"):
            return True
        ...
"""

import botpy

import config
from utils.reply import safe_reply

_log = botpy.logging.get_logger()

# 平台下发的群成员身份 → 有管理权限
ADMIN_ROLES = ("owner", "admin")

# 取作者各字段时按这个顺序（union_openid 跨群稳定，优先展示）
_ID_ATTRS = ("union_openid", "member_openid", "user_openid", "id")

OWNER_HINT = (
    "🔒 这个指令只有机器人管理员能用。\n"
    "管理员请先用 `/我的id` 查看自己的 openid，"
    "填进 `.env` 的 `ADMIN_OPENIDS`（逗号分隔）并重启机器人后生效。"
)
GROUP_ADMIN_HINT = "🔒 这个指令只有本群群主 / 管理员能用。"


def identity_ids(message) -> list:
    """消息作者身上所有可用的身份标识（去重、保持原样）"""
    author = getattr(message, "author", None)
    if not author:
        return []
    ids = []
    for attr in _ID_ATTRS:
        value = getattr(author, attr, None)
        if value and str(value) not in ids:
            ids.append(str(value))
    return ids


def member_role(message) -> str:
    """群成员身份：``owner`` / ``admin`` / ``member``；取不到返回空串"""
    value = getattr(getattr(message, "author", None), "member_role", None)
    return str(value).lower() if value else ""


def is_owner_configured() -> bool:
    """是否配置了 ``ADMIN_OPENIDS``（没配等于谁都不是管理员）"""
    return bool(config.ADMIN_OPENIDS)


def is_owner(message) -> bool:
    """是否是 ``ADMIN_OPENIDS`` 白名单里的机器人管理员"""
    allowed = {str(x).upper() for x in (config.ADMIN_OPENIDS or []) if str(x).strip()}
    if not allowed:
        return False
    return any(value.upper() in allowed for value in identity_ids(message))


def is_group_admin(message) -> bool:
    """是否是本群群主 / 管理员（私聊消息取不到身份 → False）"""
    return member_role(message) in ADMIN_ROLES


async def require_owner(message, command: str = "") -> bool:
    """有权限返回 True；否则回一句拒绝理由并返回 False"""
    if is_owner(message):
        return True
    _log.warning(
        f"[权限] 拒绝 {command or '管理员指令'}：身份={identity_ids(message)} "
        f"role={member_role(message) or '-'} 白名单={len(config.ADMIN_OPENIDS or [])} 条"
    )
    await safe_reply(message, content=OWNER_HINT)
    return False


async def require_group_admin(message, command: str = "") -> bool:
    """群主 / 管理员才有权限；取不到身份时按无权限处理"""
    if is_group_admin(message):
        return True
    _log.warning(
        f"[权限] 拒绝 {command or '群管理指令'}：身份={identity_ids(message)} "
        f"role={member_role(message) or '(平台未下发)'}"
    )
    await safe_reply(message, content=GROUP_ADMIN_HINT)
    return False


def describe_identity(message) -> str:
    """``/我的id`` 的正文：列出可用于配置白名单的 id 与群内身份"""
    author = getattr(message, "author", None)
    role = member_role(message) or "(平台未下发)"
    is_direct = getattr(message, "group_openid", None) is None
    lines = [
        "## 🪪 你的身份标识",
        "",
        f"- **场景**：{'私聊' if is_direct else '群聊'}",
        f"- **群内身份**：`{role}`"
        + ("（群主 / 管理员可用群管理指令）" if is_group_admin(message) else ""),
    ]
    for attr in _ID_ATTRS:
        value = getattr(author, attr, None)
        if value:
            lines.append(f"- **{attr}**：`{value}`")
    lines += [
        f"- **机器人管理员**：{'✅ 是' if is_owner(message) else '❌ 否'}",
        "",
        "配置方法：把上面的 `union_openid`（有就用它，跨群稳定）或 `member_openid`",
        "填进 `.env` 的 `ADMIN_OPENIDS`（多个用逗号分隔），重启机器人后生效。",
    ]
    return "\n".join(lines)

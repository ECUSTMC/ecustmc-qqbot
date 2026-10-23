"""指令权限：限制「谁能用哪些指令」

两套身份判定：

* **机器人管理员（owner）**：``.env`` 里 ``ADMIN_OPENIDS`` 列出的 openid
  （逗号分隔），或运行时用 ``/添加管理员 @某人`` 追加（会写回 ``.env`` 并立即生效）。
  给 ``/model``、``/models`` 这类全局性指令用。
  匹配时会把消息作者身上的 openid 都拿出来比一遍（大小写不敏感）：
  群消息的 ``member_openid`` **按群隔离**（同一个人在不同群里值不同）、
  私聊是 ``user_openid``、平台下发 ``union_openid`` 时它跨群稳定。
  第一次配置（**必须手工**）：先用 ``/我的id`` 查看自己的 openid，填进
  ``ADMIN_OPENIDS`` 后重启 —— 白名单为空时没有任何人有权限，
  ``/添加管理员`` 也就无人可用（刻意 fail closed，防止随便谁先来认领）。
* **群主 / 管理员（group admin）**：平台的 ``message.author.member_role``
  （``owner`` / ``admin`` / ``member``）。给 ``/添加服务器``、``/移除服务器``
  这类会改配置的指令用；这两条是**两级放行**（:func:`require_owner_or_group_admin`）：
  机器人管理员在哪个群（甚至私聊）都能用，本群群主 / 管理员在本群也能用。
  取不到身份时按**无权限**处理（fail closed）并打 WARNING，
  避免平台改字段后权限静默失效。

用法（放在 handler 最前面；拒绝时 ``return True`` 终止分发，
否则会继续走默认回复，用户会收到第二句莫名其妙的话）::

    @Commands("/model")
    async def switch_model(api, message, params=None):
        if not await require_owner(message, "/model"):
            return True
        ...
"""

import re

import botpy

import config
import r
from utils.reply import safe_reply

_log = botpy.logging.get_logger()

# 管理员白名单在 .env 里的键名（运行时增删会写回这里）
ENV_KEY_ADMIN_OPENIDS = "ADMIN_OPENIDS"

# 正文里的 @ 占位符，形如 "<@01A2B3C4>"
_MENTION_PLACEHOLDER_RE = re.compile(r"<@!?([^>\s]+)>")

# 平台下发的群成员身份 → 有管理权限
ADMIN_ROLES = ("owner", "admin")

# 取作者各字段时按这个顺序（union_openid 跨群稳定，优先展示）
_ID_ATTRS = ("union_openid", "member_openid", "user_openid", "id")

OWNER_HINT = (
    "🔒 这个指令只有机器人管理员能用。\n"
    "已有管理员可以 @我 发 `/添加管理员 @你` 把你加进去；"
    "还没有任何管理员时，请先用 `/我的id` 查看自己的 openid，"
    "填进 `.env` 的 `ADMIN_OPENIDS`（逗号分隔）并重启机器人。"
)
GROUP_ADMIN_HINT = "🔒 这个指令只有本群群主 / 管理员能用。"
OWNER_OR_GROUP_ADMIN_HINT = (
    "🔒 这个指令只有机器人管理员、或本群群主 / 管理员能用。"
)


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


# ---------------------------------------------------------------------------
# 管理员白名单的运行时维护（/添加管理员、/移除管理员）
#
# 白名单的「源头」仍是 .env 的 ADMIN_OPENIDS：改完写回 .env 并同步
# config.ADMIN_OPENIDS，因此**立即生效**且重启后依然有效，不必手工编辑文件。
# ---------------------------------------------------------------------------


def owner_ids() -> list:
    """当前机器人管理员 id 列表（去空白，保持原样／原大小写）"""
    return [str(x).strip() for x in (config.ADMIN_OPENIDS or []) if str(x).strip()]


def _owner_key(value) -> str:
    """比较用的归一化 key（大小写不敏感，和 :func:`is_owner` 一致）"""
    return str(value).strip().upper()


def _save_owner_ids(ids: list) -> tuple:
    """把白名单写回 ``.env`` 并同步内存配置；返回 ``(是否成功, 错误信息)``

    写 `.env` 失败（只读文件系统、没有 `.env`…）时**内存仍然生效**，
    只是重启后会丢，调用方负责把这件事告诉用户。
    """
    ids = [str(x).strip() for x in ids if str(x).strip()]
    config.ADMIN_OPENIDS = list(ids)
    try:
        r.update_env_variable(ENV_KEY_ADMIN_OPENIDS, ",".join(ids))
    except Exception as e:  # noqa: BLE001 - 持久化失败不该打断指令本身
        _log.error(f"[权限] 写回 {ENV_KEY_ADMIN_OPENIDS} 失败: {e}")
        return False, str(e)
    return True, ""


def add_owner_ids(values) -> dict:
    """把一批 openid 加入管理员白名单（已存在的不重复加）

    :return: ``{"added": [...], "existed": [...], "owners": [...],
              "persisted": bool, "error": str}``
    """
    current = owner_ids()
    keys = {_owner_key(x) for x in current}
    added, existed = [], []
    for value in values or ():
        value = str(value).strip()
        if not value:
            continue
        if _owner_key(value) in keys:
            existed.append(value)
            continue
        current.append(value)
        keys.add(_owner_key(value))
        added.append(value)

    persisted, error = (True, "")
    if added:
        persisted, error = _save_owner_ids(current)
    return {
        "added": added,
        "existed": existed,
        "owners": current,
        "persisted": persisted,
        "error": error,
    }


def remove_owner_ids(values) -> dict:
    """把一批 openid 从管理员白名单里删掉（不存在的忽略）

    :return: ``{"removed": [...], "missing": [...], "owners": [...],
              "persisted": bool, "error": str}``
    """
    current = owner_ids()
    targets = {_owner_key(x) for x in (values or []) if str(x).strip()}
    removed = [x for x in current if _owner_key(x) in targets]
    missing = [str(x).strip() for x in (values or ())
               if str(x).strip() and _owner_key(x) not in {_owner_key(y) for y in current}]
    remaining = [x for x in current if _owner_key(x) not in targets]

    persisted, error = (True, "")
    if removed:
        persisted, error = _save_owner_ids(remaining)
    return {
        "removed": removed,
        "missing": missing,
        "owners": remaining,
        "persisted": persisted,
        "error": error,
    }


def would_remove_all(values) -> bool:
    """把 ``values`` 删掉后白名单会不会变成空的（防止把自己锁在门外）"""
    targets = {_owner_key(x) for x in (values or ()) if str(x).strip()}
    return bool(targets) and not [
        x for x in owner_ids() if _owner_key(x) not in targets
    ]


def _looks_like_bot(value) -> bool:
    """平台对「@ 的是机器人」给的 ``bot`` 标记（布尔，个别情况下可能是字符串）"""
    return value is True or str(value).lower() == "true"


def mentioned_identities(message) -> list:
    """消息里 @ 到的人（**排除机器人自己**）

    返回 ``[{"id": 首选的 openid, "ids": [该用户所有可用 id], "name": 昵称}]``。
    ``id`` 按 ``union_openid → member_openid → user_openid → id`` 取第一个，
    —— ``union_openid`` 跨群稳定，是写进白名单的首选；写一条就够，别把
    一个人的三个 id 都塞进 ``ADMIN_OPENIDS``（列表会变得没法读）。

    正常走平台下发的 ``message.mentions``（``bot=true`` 的条目跳过，那是机器人自己）；
    全部是机器人 / 平台没下发 mentions 时，退回解析正文里的 ``<@openid>`` 占位符。

    注意 ``botpy`` 原版 ``GroupMessage`` 的 mention 对象只有 ``member_openid``，
    ``union_openid`` / ``bot`` 是 ``utils/group_message_patch.py`` 补上的；
    所以这里全部用 ``getattr`` 兜底，拿不到就只用现有字段。
    """
    people, seen = [], set()
    author_keys = {_owner_key(x) for x in identity_ids(message)}
    for user in getattr(message, "mentions", None) or []:
        if _looks_like_bot(getattr(user, "bot", None)):
            continue
        ids = []
        for attr in _ID_ATTRS:
            value = getattr(user, attr, None)
            if value and str(value) not in ids:
                ids.append(str(value))
        if not ids:
            continue
        keys = {_owner_key(x) for x in ids}
        # @ 自己（已经在白名单里了）没有意义，跳过
        if keys <= author_keys or keys & seen:
            continue
        seen |= keys
        name = (
            getattr(user, "username", None)
            or getattr(user, "nick", None)
            or getattr(user, "nickname", None)
            or ""
        )
        people.append({"id": ids[0], "ids": ids, "name": str(name)})

    if people:
        return people

    # 兜底：平台没给 mentions（或 @ 的全是机器人），从正文占位符里捞
    # （开头那个「@机器人」占位符已被 bot_client._normalize_content 剥掉）
    content = getattr(message, "content", "") or ""
    for raw in _MENTION_PLACEHOLDER_RE.findall(content):
        value = raw.strip()
        if not value or value.lower() == "all":  # <@all> = @全体成员，不是某个人
            continue
        if _owner_key(value) in author_keys or _owner_key(value) in seen:
            continue
        seen.add(_owner_key(value))
        people.append({"id": value, "ids": [value], "name": ""})
    return people


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


async def require_owner_or_group_admin(message, command: str = "") -> bool:
    """两级放行：机器人管理员（任何场景）**或**本群群主 / 管理员

    给 ``/添加服务器``、``/移除服务器`` 这类群内配置指令用：机器人管理员不必是
    每个群的群主（私聊也能改），本群群主 / 管理员自己也能维护。
    """
    if is_owner(message) or is_group_admin(message):
        return True
    _log.warning(
        f"[权限] 拒绝 {command or '群管理指令'}：身份={identity_ids(message)} "
        f"role={member_role(message) or '(平台未下发)'} "
        f"白名单={len(config.ADMIN_OPENIDS or [])} 条"
    )
    await safe_reply(message, content=OWNER_OR_GROUP_ADMIN_HINT)
    return False


def describe_identity(message) -> str:
    """``/我的id`` 的正文：列出可用于配置白名单的 id 与群内身份

    同一用户的几个字段常常是**同一个值**（实测 ``union_openid`` /
    ``member_openid`` / ``id`` / 私聊 ``user_openid`` 一致），所以按值归并成一行，
    免得输出三行完全一样的 id。
    """
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

    grouped = {}  # 值 → 带这个值的字段名，按出现顺序
    for attr in _ID_ATTRS:
        value = getattr(author, attr, None)
        if value:
            grouped.setdefault(str(value), []).append(attr)
    for value, attrs in grouped.items():
        label = attrs[0] if len(attrs) == 1 else f"{' / '.join(attrs)}（同值）"
        lines.append(f"- **{label}**：`{value}`")

    lines += [
        f"- **机器人管理员**：{'✅ 是' if is_owner(message) else '❌ 否'}",
        "",
        "添加管理员：让已有的管理员 @你 发 `/添加管理员 @你`（立即生效，无需重启）；"
        "还没有任何管理员时，才需要把这行 id 填进 `.env` 的 `ADMIN_OPENIDS` 并重启。",
        "几个字段通常同值，填一个就够；若哪天出现不同值（平台按群隔离），"
        "用 `union_openid`（跨群稳定），或把用到的 id 都列上。",
    ]
    return "\n".join(lines)

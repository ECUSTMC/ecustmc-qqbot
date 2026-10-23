"""身份 / 管理员相关指令"""
import re

from botpy import BotAPI
from botpy.ext.command_util import Commands
from botpy.message import GroupMessage

from utils.permissions import (
    add_owner_ids,
    describe_identity,
    is_group_admin,
    is_owner,
    mentioned_identities,
    owner_ids,
    remove_owner_ids,
    require_owner,
    would_remove_all,
)
from utils.reply import safe_reply

# 直接给 id 时的分隔符（空格 / 中英文逗号 / 顿号 / 分号）
_ID_SPLIT_RE = re.compile(r"[\s,，、;；]+")
# 正文里的 @ 占位符（botpy 不会把 @ 从 content 里删掉）
_PLACEHOLDER_RE = re.compile(r"<@!?([^>\s]+)>")
# 一个像 openid 的 token：字母数字/下划线/短横线，至少 8 位
_ID_TOKEN_RE = re.compile(r"^[0-9A-Za-z_-]{8,}$")

_NO_TARGET_HINT = (
    "⚠️ 请用 `@` 选中对象，例如：\n"
    "- 群聊：`@机器人 /添加管理员 @某某`\n"
    "- 直接给 openid：`/添加管理员 01A2B3C4...`（让对方发 `/我的id` 查）"
)


def _mask(value: str, keep: int = 6) -> str:
    """openid 只露头尾，避免刷屏/泄露完整值"""
    value = str(value)
    return value if len(value) <= keep + 4 else f"{value[:keep]}…{value[-4:]}"


def _explicit_ids(params) -> list:
    """从指令参数里取 openid

    两种写法都收：``<@01A2B3C4>``（客户端把 @ 渲染成占位符）与裸 id
    ``01A2B3C4``（空格 / 逗号分隔多个）。**注意别把占位符原样当成 id**：
    ``params`` 里带着 ``<@...>``，直接 split 会把 ``"<@01X>"`` 写进白名单。
    """
    text = params if isinstance(params, str) else "".join(params or [])
    text = text or ""
    ids = [m.strip() for m in _PLACEHOLDER_RE.findall(text) if m.strip()]
    rest = _PLACEHOLDER_RE.sub(" ", text)
    ids += [t for t in _ID_SPLIT_RE.split(rest.strip()) if _ID_TOKEN_RE.match(t)]
    return list(dict.fromkeys(ids))


def _target_ids(message, params) -> list:
    """本次要操作的对象 id：优先取 @ 到的人，其次取参数里直接写的 openid

    **@ 到人时不再从 params 里再解析一遍**：params 里那个 ``<@openid>`` 就是同一次
    @ 的另一种渲染，两个都取会把同一个人按「union_openid + id」加两遍。
    """
    people = mentioned_identities(message)
    if people:
        return list(dict.fromkeys(p["id"] for p in people))
    return _explicit_ids(params)


def _persist_note(result: dict) -> str:
    if result["persisted"]:
        return ""
    return f"\n\n⚠️ 已立即生效，但写回 `.env` 失败，重启后会丢失：{result['error']}"


@Commands("/我的id")
async def my_id(api: BotAPI, message: GroupMessage, params=None):
    """查看自己的 openid 与群内身份（用于配置 ADMIN_OPENIDS 白名单）"""
    await safe_reply(message, content=describe_identity(message))
    return True


@Commands("/添加管理员")
async def add_admin(api: BotAPI, message: GroupMessage, params=None):
    """把 @ 到的人加入机器人管理员白名单（仅机器人管理员可用）

    会写回 ``.env`` 的 ``ADMIN_OPENIDS`` 并同步内存配置，**立即生效、重启不丢**。
    """
    if not await require_owner(message, "/添加管理员"):
        return True

    ids = _target_ids(message, params)
    if not ids:
        await safe_reply(message, content=_NO_TARGET_HINT)
        return True

    result = add_owner_ids(ids)
    if not result["added"]:
        await safe_reply(
            message,
            content=(
                "这些 id 已经在管理员列表里了，无需重复添加：\n"
                + "\n".join(f"- `{_mask(x)}`" for x in result["existed"])
                + f"\n\n当前共 {len(result['owners'])} 位管理员。"
            ),
        )
        return True

    lines = ["## ✅ 已添加机器人管理员", ""]
    lines += [f"- 新增：`{_mask(x)}`" for x in result["added"]]
    if result["existed"]:
        lines += [f"- 已存在（跳过）：`{_mask(x)}`" for x in result["existed"]]
    lines += ["", f"当前共 {len(result['owners'])} 位管理员，立即生效，无需重启。"]
    await safe_reply(message, content="\n".join(lines) + _persist_note(result))
    return True


@Commands("/移除管理员")
async def remove_admin(api: BotAPI, message: GroupMessage, params=None):
    """把 @ 到的人移出机器人管理员白名单（仅机器人管理员可用）"""
    if not await require_owner(message, "/移除管理员"):
        return True

    ids = _target_ids(message, params)
    if not ids:
        await safe_reply(message, content=_NO_TARGET_HINT.replace("添加", "移除"))
        return True

    # 防止把自己（或最后一个人）删掉后无人能再用管理员指令
    if would_remove_all(ids):
        await safe_reply(
            message,
            content=(
                "⚠️ 这样会把管理员列表清空，导致**谁也用不了管理员指令**，已拒绝。\n\n"
                "当前管理员：\n" + "\n".join(f"- `{_mask(x)}`" for x in owner_ids()) + "\n\n"
                "要彻底清空请直接改 `.env` 的 `ADMIN_OPENIDS`。"
            ),
        )
        return True

    result = remove_owner_ids(ids)
    if not result["removed"]:
        await safe_reply(
            message,
            content=(
                "这些 id 不在管理员列表里：\n"
                + "\n".join(f"- `{_mask(x)}`" for x in result["missing"])
                + f"\n\n当前共 {len(result['owners'])} 位管理员。"
            ),
        )
        return True

    lines = ["## ✅ 已移除机器人管理员", ""]
    lines += [f"- 移除：`{_mask(x)}`" for x in result["removed"]]
    if result["missing"]:
        lines += [f"- 不在列表 / 已忽略：`{_mask(x)}`" for x in result["missing"]]
    lines += [
        "",
        f"当前共 {len(result['owners'])} 位管理员，立即生效，无需重启。",
    ]
    await safe_reply(message, content="\n".join(lines) + _persist_note(result))
    return True


@Commands("/管理员列表")
async def list_admins(api: BotAPI, message: GroupMessage, params=None):
    """列出机器人管理员白名单（仅机器人管理员可用）"""
    if not await require_owner(message, "/管理员列表"):
        return True

    owners = owner_ids()
    lines = ["## 🔑 机器人管理员", f"（共 {len(owners)} 位，id 只露头尾）", ""]
    lines += [f"{index}. `{_mask(value)}`" for index, value in enumerate(owners, 1)]
    lines += [
        "",
        "增删用 `/添加管理员 @某人` / `/移除管理员 @某人`（会写回 `.env`）。",
        "完整的 id 在 `.env` 的 `ADMIN_OPENIDS` 里；自己那份用 `/我的id` 查。",
    ]
    await safe_reply(message, content="\n".join(lines))
    return True


@Commands("/权限")
async def show_permissions(api: BotAPI, message: GroupMessage, params=None):
    """查看本机器人当前的指令权限状态"""
    lines = [
        "## 🔐 指令权限",
        "",
        "- `/model`、`/models`：仅**机器人管理员**（`.env` 的 `ADMIN_OPENIDS`）",
        "- `/添加管理员`、`/移除管理员`、`/管理员列表`：仅**机器人管理员**"
        "（改完立即生效，无需重启）",
        "- `/添加服务器`、`/移除服务器`：**机器人管理员**或**本群群主 / 管理员**",
        "- `/mc`（RCON 命令）与「永昼机」按钮：任何人都能用（当前如此，未加限制）",
        "",
        f"- 你的身份：{'机器人管理员 ✅' if is_owner(message) else '非机器人管理员'} / "
        f"{'群主或管理员 ✅' if is_group_admin(message) else '普通成员（或平台未下发身份）'}",
        "",
        f"- 当前管理员：**{len(owner_ids())}** 位",
        "",
        "用 `/我的id` 查看自己的 openid；管理员白名单为空时，所有人都无法使用管理员指令"
        "（安全默认：宁可锁死，也不放开）。",
    ]
    await safe_reply(message, content="\n".join(lines))
    return True

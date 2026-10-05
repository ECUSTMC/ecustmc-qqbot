"""身份 / 管理员相关指令"""
from botpy import BotAPI
from botpy.ext.command_util import Commands
from botpy.message import GroupMessage

from utils.permissions import describe_identity, is_group_admin, is_owner
from utils.reply import safe_reply


@Commands("/我的id")
async def my_id(api: BotAPI, message: GroupMessage, params=None):
    """查看自己的 openid 与群内身份（用于配置 ADMIN_OPENIDS 白名单）"""
    await safe_reply(message, content=describe_identity(message))
    return True


@Commands("/权限")
async def show_permissions(api: BotAPI, message: GroupMessage, params=None):
    """查看本机器人当前的指令权限状态"""
    lines = [
        "## 🔐 指令权限",
        "",
        "- `/model`、`/models`：仅**机器人管理员**（`.env` 的 `ADMIN_OPENIDS`）",
        "- `/添加服务器`、`/移除服务器`：**机器人管理员**或**本群群主 / 管理员**",
        "- `/mc`（RCON 命令）与「永昼机」按钮：任何人都能用（当前如此，未加限制）",
        "",
        f"- 你的身份：{'机器人管理员 ✅' if is_owner(message) else '非机器人管理员'} / "
        f"{'群主或管理员 ✅' if is_group_admin(message) else '普通成员（或平台未下发身份）'}",
        "",
        "用 `/我的id` 查看自己的 openid；管理员白名单为空时，所有人都无法使用管理员指令"
        "（安全默认：宁可锁死，也不放开）。",
    ]
    await safe_reply(message, content="\n".join(lines))
    return True

"""群主授权引导处理器

「接收所有消息」（全量模式）是 QQ 开放平台侧的按群开关：
需要群主 / 管理员在 QQ 客户端手动同意，机器人无法自行开启。

授权结果会通过两个事件回调：
- GROUP_MSG_RECEIVE 群管理员开启通知 → 该群开始推送 GROUP_MESSAGE_CREATE
- GROUP_MSG_REJECT  群管理员关闭通知 → 该群停止推送

本处理器负责在群里给出「怎么授权」的操作指引。
"""

from botpy import BotAPI
from botpy.ext.command_util import Commands
from botpy.message import GroupMessage
from botpy.types.message import MarkdownPayload

# 已授权的群（进程内缓存，重启后由事件重新填充；持久化可后续接数据库）
AUTHORIZED_GROUPS = set()

AUTH_GUIDE_MD = """## 🔐 开启「接收所有消息」授权

机器人默认只能看到 **@它** 的消息。想让它在群里看到全部消息，需要 **群主 / 管理员** 手动授权。

### 授权步骤

1. 在该群聊窗口中，点击右上角「☰ / 三横」打开群设置
2. 进入「**群机器人**」（或直接点击机器人头像 → 资料页）
3. 找到本机器人 **{bot_name}**
4. 打开「**接收所有消息**」/「**允许查看全部消息**」开关
5. 群主在弹出的确认卡片中点击「**同意**」

授权成功后，机器人会收到平台的开启通知事件，并自动在群里提示 ✅

### 说明

- 授权是 **按群独立** 的，每个群都要单独开一次
- 只有 **群主 / 管理员** 能操作，普通成员看不到该开关
- 随时可在同一入口关闭，关闭后机器人立即停止接收全量消息
- 授权后 **无需重启机器人**，也不用改代码

> 找不到开关？可能是平台还未对该机器人开放此能力（部分机器人需要企业主体认证）。
"""


@Commands("/授权")
async def authorize_group(api: BotAPI, message: GroupMessage, params=None):
    """输出群主授权操作指引"""
    bot_name = "本机器人"
    try:
        info = await api.me()
        bot_name = getattr(info, "username", None) or bot_name
    except Exception:
        pass

    markdown = MarkdownPayload(content=AUTH_GUIDE_MD.format(bot_name=bot_name))

    if getattr(message, "group_openid", None):
        await message.reply(markdown=markdown, msg_type=2)
    else:
        await message.reply(markdown=markdown, msg_type=2)

    return True

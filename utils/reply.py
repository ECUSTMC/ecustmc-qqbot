"""安全的被动回复封装

各处理器与兜底逻辑里到处是 ``await message.reply(...)``；
一旦平台侧报错（去重、超时、限频、内容不合规…），异常会一路向上抛：

* 处理器内部的 except 再回一次 → 再报错 → 最终在 ``botpy _run_event`` 里
  打印一大段 traceback，用户端则完全收不到回复；
* 处理器已经回复过、却又返回假值继续走兜底 → 相同 ``msg_id`` 再回一次。

``safe_reply`` 让「回复」这一动作永不抛异常：失败只记日志，由调用方决定
后续流程。
"""

import botpy

_log = botpy.logging.get_logger()


def _brief(kwargs: dict, limit: int = 60) -> str:
    """截取回复内容做日志，避免 markdown 刷屏"""
    text = kwargs.get("content")
    if text is None:
        markdown = kwargs.get("markdown")
        text = getattr(markdown, "content", None) or str(markdown)
    text = str(text).replace("\n", " ")
    return text[:limit]


async def safe_reply(message, **kwargs) -> bool:
    """发送被动回复；失败返回 False 并记日志，不抛异常

    :return: True 表示发送成功
    """
    try:
        await message.reply(**kwargs)
        return True
    except Exception as e:  # noqa: BLE001 - 兜底回复不允许再抛异常
        _log.error(
            f"[回复失败] msg_id={getattr(message, 'id', None)} "
            f"内容={_brief(kwargs)!r} 原因={e}"
        )
        return False

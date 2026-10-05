"""给 QQ 消息做「地址脱敏」显示：把点号换成短横线（可逆）

QQ 会把消息里的域名当链接做风控，所以机器人展示服务器地址时把 ``.`` 换成 ``-``。
问题是地址本身可能就带 ``-``（``my-server.example.com``），直接换完就分不清
哪个 ``-`` 原本是 ``.``。所以这里用**可逆转义**：

1. 先把原有的 ``-`` 逐个翻倍成 ``--``；
2. 再把 ``.`` 换成 ``-``。

于是显示串里：单个 ``-`` 一定来自 ``.``、``--`` 一定来自原本的 ``-``，
:func:`qq_address` 能无损还原。管理员也可以直接把显示串复制给
``/添加服务器`` / ``/移除服务器``，由机器人负责还原。

例：``mc.ecustvr.top`` → ``mc-ecustvr-top``；
    ``my-server.example.com`` → ``my--server-example-com``。
"""


def qq_display(address: str) -> str:
    """真实地址 → 可发到 QQ 的显示串（``-`` 翻倍，``.`` → ``-``）"""
    if not address:
        return address or ""
    return str(address).replace("-", "--").replace(".", "-")


def qq_address(text: str) -> str:
    """显示串 → 真实地址（``--`` → ``-``，单个 ``-`` → ``.``）

    只对「来自 :func:`qq_display` 的串」保证无损；对普通地址（本来就带 ``.`` 的
    输入）也会照做替换，所以调用方应当**先用原文精确匹配一次**，匹配不上再用
    这个还原结果去匹配（见 ``handlers/server.py::remove_server``）。
    """
    if not text:
        return text or ""
    text = str(text)
    out = []
    i = 0
    while i < len(text):
        if text[i] == "-":
            if i + 1 < len(text) and text[i + 1] == "-":
                out.append("-")
                i += 2
            else:
                out.append(".")
                i += 1
        else:
            out.append(text[i])
            i += 1
    return "".join(out)

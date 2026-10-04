"""校园问答（腾讯乐享知识库）与「默认 @」的兜底路由

机器人被 **@**（或私聊）但没命中任何指令时，处理流程是：

1. **先拿用户的话去飞书群表搜一遍**（只搜「是否可信 = true」的群）——
   历史惯性：群友往往只丢一个 ``王者荣耀`` / ``三角洲`` / ``原神``，
   而不是完整的「找XX群」；
2. 明确在找群（``有没有XX群`` 之类）→ 直接把结果发给用户（有就发群，没有就说没找到），
   不再花大模型调用；
3. 其余交给路由大模型（``ROUTER_*``，见 ``utils/router.py``），
   它根据「用户输入 + 找群结果」决定：
   * ``send_group``：把搜到的群发出去（用户要的就是这些群）
   * ``query_kb``：去查华理知识库（学校的事）
   * 两个都 false：既不是找群也不是校园问题 → **用已有的 ``/ai`` 对话回复**
4. 大模型不可用时（代理挂了 / 超时 / 返回不是 JSON）自动退化为规则判断；
5. 知识库没收录 / 接口异常时，也优先交给已有的 AI 对话，实在没有才提示用户。

乐享的回答是 markdown，正文里的插图按 QQ 的 ``![说明 #宽px #高px](url)`` 语法内嵌
（和 ``/塔罗牌`` 一样的发法，开放平台会把图下载转存）。

为什么用乐享而不是 ima：ima 的 OpenAPI 只有知识库/笔记的增删查改
（``get_knowledge_list`` / ``get_media_info`` …），**没有问答接口**，
要用它就得自己下载原文、解析 PDF/DOCX、分块、做检索再喂给大模型；
乐享的 ``/cgi-bin/v1/ai/qa`` 直接返回基于知识库的答案 + 引用来源，
而且扫描件/图片也由乐享侧完成解析。详见 ADVANCED.md「校园问答」一节。
"""

import asyncio
import re
import struct

import aiohttp
import botpy
from botpy import BotAPI
from botpy.ext.command_util import Commands
from botpy.message import GroupMessage
from botpy.types.message import MarkdownPayload

from config import CAMPUS_QA_ENABLED
from handlers import group_management as gm
from utils import intent, router
from utils.lexiang_client import LexiangClient, LexiangError
from utils.reply import safe_reply

_log = botpy.logging.get_logger()

# QQ 侧安全网：乐享回答一般 200~1000 字，超过这个长度才截断（不是可配置项）
MAX_REPLY_CHARS = 2000

# 一条回复里最多内嵌几张知识库插图（乐享的签名图床 url 很长，一张约 500 字）
MAX_IMAGES = 3
# 内嵌图片的显示宽度上限（QQ markdown 语法：`![说明 #宽px #高px](url)`）
IMAGE_MAX_WIDTH = 600

# 乐享答案正文里的 markdown 图片：![说明](https://image-ai.lexiang-asset.com/…)
# QQ markdown 支持图片（官方文档：`![text #208px #320px](url)`，开放平台会下载转存），
# 所以这些图直接内嵌在卡片里，按 /塔罗牌 那种方式一条 markdown 消息发出去。
_IMAGE_MD_RE = re.compile(r"!\[(?P<alt>[^\]]*)\]\s*\(\s*(?P<url>https?://[^)\s]+)\s*\)")
# 正文里剩下的裸链接去掉（QQ 里显示成纯文本也不好看，图床链接尤其长）
# 注意：`![说明](url)` / `[文字](url)` 里的链接前面是 `](`，不能动（否则图片标记会被截断）
_BARE_URL_RE = re.compile(r"(?<!\]\()https?://[^\s\)\]<>，。；、]+")
# 兜底：乐享偶尔用 [IMAGE]…[/IMAGE] 包图（正常是 markdown 图片）
_IMAGE_BLOCK_RE = re.compile(r"\[IMAGE\].*?\[/IMAGE\]", re.S)

# 乐享的答案里偶尔夹 LaTeX（``$90\text{cm}\times39\text{cm}$``），QQ markdown 不认公式，
# 直接显示会是 `$90\text{cm}\times39\text{cm}$` 这种乱码，所以转成纯文本
_MATH_RE = re.compile(r"\${1,2}([^$\n]+?)\${1,2}")
_TEXT_CMD_RE = re.compile(r"\\(?:text|mathrm|mathbf|operatorname|mbox|textrm)\{([^{}]*)\}")
_SUPERSCRIPT = {"0": "⁰", "1": "¹", "2": "²", "3": "³", "4": "⁴",
                "5": "⁵", "6": "⁶", "7": "⁷", "8": "⁸", "9": "⁹"}
_SUP_RE = re.compile(r"\^\{?(\d)\}?")
_FRAC_RE = re.compile(r"\\frac\{([^{}]*)\}\{([^{}]*)\}")
_SQRT_RE = re.compile(r"\\sqrt\{([^{}]*)\}")
_LATEX_REPLACE = (
    ("\\times", "×"), ("\\div", "÷"), ("\\pm", "±"), ("\\leq", "≤"), ("\\le", "≤"),
    ("\\geq", "≥"), ("\\ge", "≥"), ("\\neq", "≠"), ("\\approx", "≈"), ("\\sim", "≈"),
    ("\\rightarrow", "→"), ("\\to", "→"), ("\\cdots", "…"), ("\\ldots", "…"),
    ("\\quad", " "), ("\\qquad", " "), ("\\,", " "), ("\\;", " "), ("\\!", ""),
    ("\\%", "%"), ("\\&", "&"), ("\\_", "_"), ("\\#", "#"), ("\\$", "$"),
)

NO_ANSWER_REPLY = (
    "这个问题我在知识库里没有找到答案 😥\n\n"
    "可以换个说法再问一次，或者：\n"
    "- @我 说出想找的群名，例：`计算机群`\n"
    "- 发送 `/帮助` 查看全部指令"
)

# 既不是找群、也不是校园问题，而且没有可用的 AI 对话时的兜底话术
FALLBACK_REPLY = (
    "这个问题我暂时接不上话 😥\n\n"
    "试试：\n"
    "- 想加群：说「有没有XX群」，例：`有没有王者荣耀群`\n"
    "- 问学校的事：`/问答 转专业怎么申请`\n"
    "- 发送 `/帮助` 查看全部指令"
)


def extract_images(content: str, limit: int = MAX_IMAGES) -> list:
    """抽出乐享答案正文里的插图（按出现顺序去重）

    :return: ``[{"url": str, "alt": str}]``
    """
    if not content:
        return []
    images, seen = [], set()
    for match in _IMAGE_MD_RE.finditer(content):
        url = match.group("url")
        if url in seen:
            continue
        seen.add(url)
        images.append({"url": url, "alt": (match.group("alt") or "").strip()})
        if len(images) >= limit:
            break
    return images


def parse_image_size(data: bytes) -> tuple | None:
    """从图片头部字节里读宽高（PNG / JPEG / GIF），读不出来返回 None"""
    if len(data) >= 24 and data[:8] == b"\x89PNG\r\n\x1a\n":
        width, height = struct.unpack(">II", data[16:24])
        return (width, height) if width and height else None
    if len(data) >= 10 and data[:3] == b"GIF":
        width, height = struct.unpack("<HH", data[6:10])
        return (width, height) if width and height else None
    if len(data) >= 4 and data[:2] == b"\xff\xd8":  # JPEG：扫 SOF 段
        offset = 2
        while offset + 9 < len(data):
            if data[offset] != 0xFF:
                offset += 1
                continue
            marker = data[offset + 1]
            if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
                offset += 2
                continue
            seg_len = int.from_bytes(data[offset + 2 : offset + 4], "big")
            if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
                          0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                height = int.from_bytes(data[offset + 5 : offset + 7], "big")
                width = int.from_bytes(data[offset + 7 : offset + 9], "big")
                return (width, height) if width and height else None
            if seg_len <= 0:
                return None
            offset += 2 + seg_len
    return None


def size_hint(size: tuple | None, max_width: int = IMAGE_MAX_WIDTH) -> str:
    """生成 QQ markdown 的尺寸提示，如 ``" #600px #450px"``（等比缩放到 max_width 以内）"""
    if not size:
        return ""
    width, height = size
    if width <= 0 or height <= 0:
        return ""
    if width > max_width:
        height = max(1, round(height * max_width / width))
        width = max_width
    return f" #{width}px #{height}px"


async def resolve_images(content: str, limit: int = MAX_IMAGES) -> list:
    """抽出插图并补上尺寸提示（只取图片头部 4KB 读宽高，失败就不带尺寸）"""
    images = extract_images(content, limit=limit)
    if not images:
        return []
    timeout = aiohttp.ClientTimeout(total=6)
    headers = {"Range": "bytes=0-4095", "User-Agent": "Mozilla/5.0"}

    async def fill(session, image):
        try:
            async with session.get(image["url"], headers=headers) as resp:
                data = await resp.content.read(4096)
            image["hint"] = size_hint(parse_image_size(data))
        except Exception as e:  # noqa: BLE001 - 没尺寸提示也能正常显示
            _log.debug(f"[校园问答] 读取图片尺寸失败: {type(e).__name__}: {e}")
            image["hint"] = ""
        return image

    async with aiohttp.ClientSession(timeout=timeout) as session:
        return list(await asyncio.gather(*(fill(session, image) for image in images)))


def apply_images(content: str, images: list) -> str:
    """把正文里的插图改成带尺寸提示的 markdown；超出 MAX_IMAGES 的图删掉"""
    hints = {image["url"]: image.get("hint") or "" for image in images or []}
    counter = {"n": 0}

    def repl(match):
        url = match.group("url")
        counter["n"] += 1
        if url not in hints or counter["n"] > MAX_IMAGES:
            return ""  # 多余/未解析的图：去掉
        # 说明文字里不能出现 ] # 等会破坏语法的字符
        alt = re.sub(r"[\[\]#\r\n]+", " ", match.group("alt")).strip()[:20] or "知识库配图"
        return f"![{alt}{hints[url]}]({url})"

    return _IMAGE_MD_RE.sub(repl, content)


def clean_answer(text: str, limit: int = MAX_REPLY_CHARS) -> str:
    """清洗乐享返回的答案：去图片、去链接、压缩空行、超长截断"""
    if not text:
        return ""
    text = _IMAGE_MD_RE.sub("", text)
    text = _BARE_URL_RE.sub("", text)
    return _squeeze(text, limit)


def latex_to_text(text: str) -> str:
    """把乐享返回的 ``$…$`` 公式/数字转成纯文本（QQ markdown 不渲染公式）

    实测乐享不只包公式，连时间、分数都包：``$11:00-23:00$``、``$2-14$`` 次、
    ``$90\\text{cm}\\times39\\text{cm}$``、``$-0.5$`` 分。
    这些 ``$`` 直接落到 QQ 里就是乱码，所以统一拆掉定界符并映射常见命令：
    ``$90\\text{cm}\\times39\\text{cm}$`` → ``90cm×39cm``，``$23:00$`` → ``23:00``。
    """
    if "$" not in text:
        return text

    def repl(match):
        body = _TEXT_CMD_RE.sub(r"\1", match.group(1))
        body = _FRAC_RE.sub(r"\1/\2", body)
        body = _SQRT_RE.sub(r"√\1", body)
        for source, target in _LATEX_REPLACE:
            body = body.replace(source, target)
        body = _SUP_RE.sub(lambda m: _SUPERSCRIPT.get(m.group(1), "^" + m.group(1)), body)
        return body.replace("\\", "").replace("{", "").replace("}", "").strip()

    return _MATH_RE.sub(repl, text)


def _split_by_images(text: str) -> tuple:
    """按图片标记把正文切成「文字段」与「图片标记」

    :return: ``(segments, marks)``，满足 ``segments[0] + marks[0] + segments[1] + …`` 等于原文。
        注意不能用 ``re.split``：这个正则带**捕获组**（``alt`` / ``url``），
        split 会把捕获到的 alt、url 也当成独立片段混进结果，正文里会多出一堆碎片。
    """
    segments, marks, position = [], [], 0
    for match in _IMAGE_MD_RE.finditer(text):
        segments.append(text[position:match.start()])
        marks.append(match.group(0))
        position = match.end()
    segments.append(text[position:])
    return segments, marks


def _squeeze(text: str, limit: int = MAX_REPLY_CHARS) -> str:
    """压缩空白，并按**纯文字**字数截断（``![…](…)`` 图片标记永远完整保留）"""
    text = latex_to_text(text)
    text = _IMAGE_BLOCK_RE.sub("", text)
    text = re.sub(r"[ \t\u00a0]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not limit or len(text) <= limit:
        return text
    # 图文混排：按图片标记切段，累加纯文字长度，超预算就在句末收尾
    segments, marks, used, out = *_split_by_images(text), 0, []
    for index, segment in enumerate(segments):
        if used + len(segment) > limit:
            keep = max(0, limit - used)
            head = segment[:keep]
            cut = max(head.rfind("。"), head.rfind("\n"))
            if cut > keep * 0.6:
                head = head[: cut + 1]
            out.append(head.rstrip() + "\n\n…（内容较长，已截断）")
            return "".join(out)
        out.append(segment)
        used += len(segment)
        if index < len(marks):
            out.append(marks[index])
    return "".join(out)


async def ask_knowledge_base(question: str) -> dict:
    """调用乐享 AI 问答

    :return: ``{"ok": bool, "content": str, "sources": [str], "no_answer": bool,
                "error": str|None, "answer_source": str, "images": [str]}`` —— 本函数不抛异常
    """
    result = {
        "ok": False,
        "content": "",
        "sources": [],
        "no_answer": False,
        "error": None,
        "answer_source": "",
        "images": [],
    }
    client = LexiangClient()
    try:
        data = await client.ai_qa(question)
        parsed = client.extract_answer(data)
        # 正文里的插图：解析宽高，待会儿按 QQ markdown 语法内嵌进卡片
        parsed["images"] = await resolve_images(parsed.get("content") or "")
        result.update(parsed)
        result["ok"] = True
    except LexiangError as e:
        result["error"] = e.message or str(e)
        _log.error(f"[校园问答] 调用失败: {e}")
    except Exception as e:  # noqa: BLE001 - 兜底不允许把异常抛回消息循环
        result["error"] = str(e)
        _log.error(f"[校园问答] 未预期异常: {e}")
    finally:
        await client.close()
    return result


def format_answer(result: dict) -> str:
    """把问答结果拼成 QQ markdown 回复

    乐享的回答本身就是 markdown（``**加粗**``、``## 标题``、``- 列表``），
    正文里的插图按 QQ 的 ``![说明 #宽px #高px](url)`` 语法内嵌，
    所以整条回答是**一条** markdown 卡片（和 ``/塔罗牌`` 一样的发法）。
    """
    content = _BARE_URL_RE.sub("", apply_images(result.get("content") or "",
                                                result.get("images") or []))
    lines = ["## 🎓 校园问答", "", _squeeze(content)]
    sources = [s for s in dict.fromkeys(result.get("sources") or []) if s]
    if sources:
        lines += ["", "> 📚 来源：" + "、".join(f"《{s}》" for s in sources)]
    lines += ["", "> 🤖 内容由腾讯乐享知识库自动生成，仅供参考"]
    return "\n".join(lines)


async def send_group_reply(message, group_result: dict) -> bool:
    """把找群结果发给用户（没搜到时回「没有找到包含 X 的群组」）

    始终会回复一次，返回 True。
    """
    if not (group_result or {}).get("ok"):
        await safe_reply(message, content="获取群组信息失败，请稍后再试")
        return True
    markdown = MarkdownPayload(
        content=gm.format_groups_markdown(group_result["matched"], group_result["keyword"])
    )
    await safe_reply(message, markdown=markdown, msg_type=2)
    return True


async def fallback_ai_reply(api: BotAPI, message, ai_chat=None, quiet: bool = False) -> bool:
    """「既不找群、也不查知识库」时用已有的 AI 对话（``/ai`` 那套）回复

    :param quiet: 已经给用户发过消息时置 True（安静收场，不再补一条）
    """
    if ai_chat is not None:
        try:
            if await ai_chat(api=api, message=message):
                return True
        except Exception as e:  # noqa: BLE001
            _log.error(f"[默认回复] AI 对话失败: {e}")
    if not quiet:
        await safe_reply(message, content=FALLBACK_REPLY)
    return True


async def answer_school_question(
    api: BotAPI,
    message,
    question: str,
    ai_chat=None,
    quiet_on_failure: bool = False,
) -> bool:
    """用知识库回答一个校园问题；已经回复过用户时返回 True

    :param ai_chat: 可选的 AI 对话协程 ``(api, message) -> bool``，
        知识库**没收录**或接口异常时退回已有的 AI 对话
    :param quiet_on_failure: 知识库没答案/接口异常时是否安静收场
        （已经给用户发过找群结果时置 True，避免同一句话回两条）
    """
    result = await ask_knowledge_base(question)

    if result["ok"] and result["content"] and not result["no_answer"]:
        images = result.get("images") or []
        _log.info(
            f"[校园问答] 命中 来源={result['sources'][:3]} "
            f"答案长度={len(result['content'])} 内嵌配图={len(images)} 问题={question[:40]!r}"
        )
        markdown = MarkdownPayload(content=format_answer(result))
        await safe_reply(message, markdown=markdown, msg_type=2)
        return True

    if result["ok"]:
        if quiet_on_failure:
            _log.info(f"[校园问答] 知识库未收录（已发过群结果，保持安静）问题={question[:40]!r}")
            return True
        _log.info(f"[校园问答] 知识库未收录 问题={question[:40]!r}")
        if ai_chat is not None:
            # 知识库没收录 → 交给普通 AI 对话（知识库只覆盖学校的事）
            return await fallback_ai_reply(api, message, ai_chat=ai_chat)
        await safe_reply(message, content=NO_ANSWER_REPLY)
        return True

    # 接口异常：能退回旧逻辑就退回，避免用户完全收不到回应
    _log.error(f"[校园问答] 降级处理: {result['error']}")
    if quiet_on_failure:
        return await fallback_ai_reply(api, message, ai_chat=ai_chat, quiet=True)
    if ai_chat is not None:
        return await fallback_ai_reply(api, message, ai_chat=ai_chat)
    await safe_reply(message, content="❌ 校园问答暂时不可用，请稍后再试")
    return True


async def handle_default_reply(api: BotAPI, message, ai_chat=None) -> bool:
    """默认 @（及私聊）的兜底路由：先搜群，再由大模型决定发群结果还是查知识库

    :param ai_chat: 可选的 AI 兜底协程（群聊传 group_chat_fallback，
        私聊传 direct_chat_fallback，两者都用 ECUST_MODEL），
        仅在「既不发群也不查知识库」以及知识库不可用时使用
    :return: True 表示已经回复过用户（调用方不要再兜底）
    """
    text = (getattr(message, "content", "") or "").strip()
    if not text:
        return False

    # ① 先搜一遍群表：群友常常只丢一个「王者荣耀」「三角洲」
    keyword = intent.extract_group_keyword(text) or text
    group_result = await gm.search_groups(keyword)
    matched = group_result.get("matched") or []

    # ② 知识库没启用 → 保持老行为（AI 群聊 → 找群兜底）
    if not CAMPUS_QA_ENABLED:
        if ai_chat is not None:
            try:
                if await ai_chat(api=api, message=message):
                    return True
            except Exception as e:  # noqa: BLE001
                _log.error(f"[默认回复] AI 调用失败: {e}")
        await send_group_reply(message, group_result)
        return True

    # ③ 明确在找群且有结果 → 直接发群，省掉一次大模型往返
    if matched and intent.looks_like_group_search(text):
        _log.info(f"[默认回复] 明确找群 keyword={keyword!r} 命中 {len(matched)} 个群")
        await send_group_reply(message, group_result)
        return True

    # ④ 明确在找群但一个都没搜到 → 直接告诉用户没这个群（不必再麻烦大模型）
    if not matched and intent.looks_like_group_search(text):
        _log.info(f"[默认回复] 明确找群但没搜到 keyword={keyword!r}")
        await send_group_reply(message, group_result)
        return True

    # ⑤ 交给大模型判断：发群结果？查知识库？都不是就走已有的 AI 对话
    decision = await router.decide(text, group_result)
    _log.info(
        f"[默认回复] 路由({decision['source']}) send_group={decision['send_group']} "
        f"query_kb={decision['query_kb']} 命中群={len(matched)} "
        f"理由={decision['reason']!r} 原文={text[:40]!r}"
    )

    sent = False
    if decision["send_group"]:
        sent = await send_group_reply(message, group_result)

    if decision["query_kb"]:
        return await answer_school_question(
            api, message, text, ai_chat=ai_chat, quiet_on_failure=sent
        )

    # 已经发过群结果、也不必查知识库 → 「这样子就可以了」，收工
    if sent:
        return True

    # 既不发群也不查知识库 → 用已有的 AI 对话回复
    return await fallback_ai_reply(api, message, ai_chat=ai_chat)


@Commands("/问答")
async def kb_qa_command(api: BotAPI, message: GroupMessage, params=None):
    """``/问答 <问题>``：显式调用校园问答（不经过路由）"""
    question = (params or "").strip()
    if not question:
        await safe_reply(
            message,
            content=(
                "📖 用法：`/问答 你的问题`\n"
                "例：`/问答 转专业怎么申请`、`/问答 宿舍几点熄灯`\n\n"
                "直接 @我 提问也可以：机器人会先看看有没有对应的群，"
                "再决定发群还是查知识库。"
            ),
        )
        return True

    if not CAMPUS_QA_ENABLED:
        await safe_reply(message, content="❌ 校园问答未启用（管理员需在 .env 配置乐享知识库凭据）")
        return True

    await answer_school_question(api, message, question)
    return True

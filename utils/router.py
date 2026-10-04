"""消息路由：@ 机器人说了一句话，接下来该「发群结果」还是「查知识库」

流程（见 ``handlers/kb_qa.py::handle_default_reply``）：

1. 机器人**先拿用户的话去飞书群表搜一遍**（历史惯性：群友常常只丢一个
   「王者荣耀」「三角洲」，而不是「找XX群」）；
2. 把「用户输入 + 找群结果」交给大模型（复用 ``ECUST_API_Key / ECUST_URL /
   ECUST_MODEL``），让它判断：
   * 要不要把找群结果发给用户（``send_group``）
   * 要不要去查华理知识库（``query_kb``）
3. 大模型不可用（代理挂了 / 返回不是 JSON / 超时）时，退化为
   :func:`heuristic_decide` 的规则判断，保证机器人永远有确定行为。
"""

import asyncio
import json
import re
import time

import botpy
from openai import OpenAI

import config
from utils import intent

_log = botpy.logging.get_logger()

# 塞给大模型的群结果条数（够判断相关性就行，别把 token 堆满）
_MAX_GROUPS_IN_PROMPT = 8

# 路由模型连续失败时的熔断时间：代理挂了的时候，每条消息都白等一次超时
# （实测 newapi 返回 502 也要 5s 左右）是不可接受的，熔断期间直接用规则判断
_ROUTER_FAIL_COOLDOWN = 60
_router_fail_until = 0.0

_SYSTEM_PROMPT = """你在给华东理工大学 ECUSTMC 社团 QQ 机器人做消息路由。

用户 @ 了机器人说了一句话，机器人已经先在「华理 QQ 群总表」里搜过一遍，
搜索结果会附在用户输入后面。请决定接下来做什么，**只输出一个 JSON 对象**：

{"send_group": true/false, "query_kb": true/false, "reason": "20字以内的理由"}

含义：
- send_group：把搜到的群发给用户（说明这些群正是用户想要的）
- query_kb：再去查「华理校园知识库」
- 两个都 false：既不是找群、也不是校园问题（闲聊 / 天气 / 算术 / 与学校无关），
  机器人会用普通 AI 对话回应用户

分两种情况：
① 搜到了群
   - 用户只丢了一个游戏名/话题/组织名（"王者荣耀""三角洲""怪猎""妮姬""计算机"），
     而且搜到的群确实对得上 → send_group=true，一般到此为止
   - 如果用户同时还在问校园里的事（"计算机专业怎么样""计算机保研难吗"）→ 再加上 query_kb=true
   - 搜到的群明显对不上用户的问题（比如问"宿舍几点熄灯"却搜出个游戏群）→ send_group=false
② 没搜到群
   - 问的是华理校园里的事 → query_kb=true。包括：
     学业（转专业、保研、绩点、选课、考试、毕业…）、后勤（宿舍、食堂、军训、
     报到、校车、校园卡、图书馆…）、资助（奖学金、助学金、医保报销…）、
     网络与信息服务（如何上网、校园网/无线网络/宿舍网络、信息服务、信息门户、
     一站式平台、VPN、邮箱、云盘、报修…）、
     各类账号与初始密码（统一身份认证、学号、邮箱、校园网账号的初始密码/激活/
     忘记密码/重置…）
   - 其它（闲聊、天气、算术、游戏攻略、与学校无关的问题）→ 两个都 false

只输出 JSON，不要 markdown 代码块，不要解释。"""


def _model_config() -> dict:
    """路由模型配置：``ROUTER_API_KEY`` / ``ROUTER_URL`` / ``ROUTER_MODEL``

    **刻意不复用 ``MODEL_CONFIGS``**：那是 ``/ai``、``/model`` 用的，
    ``/model`` 会在运行时改写 ``ECUST_MODEL`` 与 ``MODEL_CONFIGS``，
    路由跟着变就会莫名其妙地换模型（换成推理型模型还会把额度花在思考上）。
    三个变量都不配时回退到 ``ECUST_*``，保证开箱可用。
    """
    return {
        "api_key": config.ROUTER_API_KEY,
        "base_url": config.ROUTER_URL,
        "model": config.ROUTER_MODEL,
    }


def _format_groups(matched: list) -> str:
    if not matched:
        return "（没有搜到任何匹配的群）"
    lines = []
    for i, group in enumerate(matched[:_MAX_GROUPS_IN_PROMPT], 1):
        lines.append(
            f"{i}. {group['group_name']}（群号 {group['group_id']}，"
            f"{group['member_count']}/{group['max_member_count']}人）描述：{group['description'][:40]}"
        )
    if len(matched) > _MAX_GROUPS_IN_PROMPT:
        lines.append(f"...另有 {len(matched) - _MAX_GROUPS_IN_PROMPT} 个匹配结果")
    return "\n".join(lines)


def build_prompt(user_input: str, group_result: dict) -> str:
    """把用户输入与找群结果拼成给大模型的用户消息"""
    matched = (group_result or {}).get("matched") or []
    keyword = (group_result or {}).get("keyword") or user_input
    if (group_result or {}).get("error"):
        search_state = f"（群表查询失败：{group_result['error']}）"
    elif not matched:
        search_state = f"（用关键词“{keyword}”搜过，没有匹配的群）"
    else:
        search_state = f"（用关键词“{keyword}”搜到 {len(matched)} 个群）"
    return (
        f"用户输入：{user_input}\n"
        f"群组搜索结果{search_state}：\n{_format_groups(matched)}"
    )


_JSON_RE = re.compile(r"\{.*?\}", re.S)
_BOOL_RES = {
    key: re.compile(rf'"{key}"\s*[:：]\s*(true|false)', re.I)
    for key in ("send_group", "query_kb")
}
_REASON_RE = re.compile(r'"reason"\s*[:：]\s*"([^"]{0,60})"')


def parse_decision(text: str) -> dict | None:
    """从大模型回复里抠出 JSON 决策

    容忍三种情况：

    1. 正常 JSON（含 ```` ```json ```` 包裹、前后废话）；
    2. 模型把 ``reason`` 写太长、被 ``max_tokens`` **截断**的半个 JSON
       （实测 hy3 会这样）→ 退回正则直接抓两个布尔值；
    3. 完全解析不出来 → 返回 None（调用方走规则降级，并记日志）。
    """
    if not text:
        return None
    candidates = []
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    if fence:
        candidates.append(fence.group(1))
    candidates.extend(m.group(0) for m in _JSON_RE.finditer(text))
    for raw in candidates:
        try:
            data = json.loads(raw)
        except Exception:  # noqa: BLE001
            continue
        if not isinstance(data, dict):
            continue
        send_group = data.get("send_group")
        query_kb = data.get("query_kb")
        if not isinstance(send_group, bool) and not isinstance(query_kb, bool):
            continue
        return {
            "send_group": bool(send_group),
            "query_kb": bool(query_kb),
            "reason": str(data.get("reason") or "")[:60],
        }

    # JSON 不完整时的兜底：直接抓字段（截断/散文式回答都能救回来）
    found = {}
    for key, pattern in _BOOL_RES.items():
        match = pattern.search(text)
        if match:
            found[key] = match.group(1).lower() == "true"
    if not found:
        return None
    reason = _REASON_RE.search(text)
    return {
        "send_group": found.get("send_group", False),
        "query_kb": found.get("query_kb", False),
        "reason": (reason.group(1) if reason else "解析兜底（JSON 被截断）")[:60],
    }


def heuristic_decide(user_input: str, group_result: dict) -> dict:
    """大模型不可用时的规则降级

    * 明确找群 / 裸词命中群表 → 发群结果
    * 像在提问 → 查知识库
    * 其余短词 → 两个都不做，交给已有的 AI 对话
    """
    matched = (group_result or {}).get("matched") or []
    if intent.looks_like_group_search(user_input):
        # 明确在找群：有结果就发结果；没结果也照旧回「没找到」（保持老行为）
        return {"send_group": True, "query_kb": False, "reason": "规则：找群意图"}
    if matched and intent.is_bare_keyword(user_input):
        # "王者荣耀"/"三角洲" 这类裸词：群表里有就发群，不去打扰知识库
        return {"send_group": True, "query_kb": False, "reason": "规则：裸词命中群表"}
    if intent.looks_like_question(user_input) or intent.is_campus_topic(user_input):
        # 像提问，或命中「校园事」关键词（"如何上网""信息服务""初始密码"这类
        # 没疑问词又不满 7 个字的说法）→ 查知识库
        return {"send_group": False, "query_kb": True, "reason": "规则：像是校园提问"}
    return {"send_group": False, "query_kb": False, "reason": "规则：交给 AI 对话"}


def _call_model(user_input: str, group_result: dict) -> dict | None:
    """同步调用大模型（外层用 to_thread 包，避免卡住事件循环）"""
    cfg = _model_config()
    api_key = cfg.get("api_key")
    base_url = cfg.get("base_url")
    model = cfg.get("model") or config.ECUST_MODEL
    if not api_key or not base_url or not model:
        _log.warning("路由模型未配置（ROUTER_API_KEY / ROUTER_URL / ROUTER_MODEL），改用规则判断")
        return None

    # max_retries=0：代理挂了要立刻失败并退化为规则判断，
    # 不能让默认 @ 的回复卡在重试上（OpenAI SDK 默认会重试 2 次）
    client = OpenAI(
        api_key=api_key,
        base_url=base_url,
        timeout=config.ROUTER_TIMEOUT,
        max_retries=0,
    )
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": build_prompt(user_input, group_result)},
        ],
        temperature=0,
        # 推理型模型（hy3）会把 500+ token 花在思考上，给小了会 finish_reason=length
        # 且 content 为空；非推理模型（gemini-3.5-flash-lite 之类）只会用到几十个 token，
        # 这里给足额度不影响它的耗时与花费
        max_tokens=800,
    )
    content = (resp.choices[0].message.content or "").strip()
    decision = parse_decision(content)
    if decision is None:
        # 解析不出来也要留痕，否则「路由(rule)」看起来像配置问题
        _log.warning(f"路由模型返回无法解析，改用规则判断: {content[:120]!r}")
    return decision


async def decide(user_input: str, group_result: dict) -> dict:
    """决定这次 @ 要做什么

    返回 ``{"send_group": bool, "query_kb": bool, "reason": str, "source": "ai"|"rule"}``

    大模型失败会熔断 60 秒（``_ROUTER_FAIL_COOLDOWN``），期间直接用规则判断，
    避免代理挂掉时每条消息都白等一次超时。
    """
    global _router_fail_until

    decision = None
    if time.monotonic() >= _router_fail_until:
        try:
            decision = await asyncio.to_thread(_call_model, user_input, group_result)
            if decision is not None:
                _router_fail_until = 0.0
        except Exception as e:  # noqa: BLE001 - 路由失败不能影响回复
            _router_fail_until = time.monotonic() + _ROUTER_FAIL_COOLDOWN
            _log.warning(
                f"路由模型调用失败，改用规则判断并熔断 {_ROUTER_FAIL_COOLDOWN}s: "
                f"{type(e).__name__}: {e}"
            )
    else:
        _log.debug("路由模型处于熔断期，直接用规则判断")

    if decision is None:
        decision = heuristic_decide(user_input, group_result)
        decision["source"] = "rule"
        return decision

    decision["source"] = "ai"

    matched = (group_result or {}).get("matched") or []
    group_intent = intent.looks_like_group_search(user_input)

    # 模型说要发群但压根没搜到群：除非用户本来就在找群（那就照旧回「没找到」），
    # 否则以事实为准，别发一条莫名其妙的「没找到」
    if decision["send_group"] and not matched and not group_intent:
        decision["send_group"] = False
        decision["reason"] = (decision["reason"] + "；无群结果")[:60]

    # 两个都不做 → 交给已有的 AI 对话（见 handlers/kb_qa.py），这里不用修正
    return decision

"""离线自检：验证 msg_seq 递增补丁 / 全量消息触发判定 / 兜底回复不抛异常

不需要网络与 QQ 凭据，纯本地跑；用于回归验证 40054005「消息被去重」
与「全量消息的群 @机器人 没反应」两类问题。

运行：python3 selfcheck.py
"""
import asyncio
import sys
from types import SimpleNamespace

from botpy.api import BotAPI

from utils.reply_seq import apply_reply_seq_patch
from utils import group_trigger


class FakeHTTP:
    def __init__(self):
        self.payloads = []

    async def request(self, route, **kwargs):
        self.payloads.append(kwargs.get("json"))
        return {"id": f"MSG{len(self.payloads)}"}


def make_api():
    api = BotAPI.__new__(BotAPI)
    api._http = FakeHTTP()
    return api


class FakeMsg:
    def __init__(
        self,
        msg_id="MSG_A",
        content="/帮助",
        mentions=(),
        api=None,
        group_openid="G1",
        author_bot=False,
    ):
        self.id = msg_id
        self.content = content
        self.author = SimpleNamespace(
            id="01A0B219AABBCC", member_openid="01A0B219AABBCC", bot=author_bot
        )
        self.mentions = []
        for item in mentions:
            mid, is_bot = item if isinstance(item, tuple) else (item, False)
            self.mentions.append(
                SimpleNamespace(
                    id=mid, member_openid=mid, union_openid=None, bot=is_bot or None
                )
            )
        self.message_type = 0
        self.group_openid = group_openid
        self.api = api

    async def reply(self, **kwargs):
        return await self.api.post_group_message(
            group_openid=self.group_openid, msg_id=self.id, **kwargs
        )


def fake_message(msg_id="MSG_A", content="/帮助", mentions=(), api=None, author_bot=False):
    return FakeMsg(
        msg_id=msg_id,
        content=content,
        mentions=mentions,
        api=api,
        author_bot=author_bot,
    )


async def test_msg_seq_passive_increments():
    api = make_api()
    # 模拟「同一个 msg_id 回复三次」（错误兜底 / 多段消息 / 先发后撤回）
    for _ in range(3):
        await api.post_group_message(group_openid="G1", msg_id="ROBOT1.0_A", content="x")
    seqs = [p["msg_seq"] for p in api._http.payloads]
    assert seqs == [1, 2, 3], seqs
    assert all(p["msg_id"] == "ROBOT1.0_A" for p in api._http.payloads)
    print("[OK] 同一 msg_id 多次回复 -> msg_seq =", seqs)

    # 不同 msg_id 各自从 1 开始
    api._http.payloads.clear()
    await api.post_group_message(group_openid="G1", msg_id="ROBOT1.0_B", content="x")
    await api.post_group_message(group_openid="G1", msg_id="ROBOT1.0_A", content="x")
    seqs = [(p["msg_id"], p["msg_seq"]) for p in api._http.payloads]
    assert seqs == [("ROBOT1.0_B", 1), ("ROBOT1.0_A", 4)], seqs
    print("[OK] 不同 msg_id 独立计数 ->", seqs)

    # 调用方显式传 msg_seq（peek_detect 的 msg_seq=2）会被尊重并同步计数
    api._http.payloads.clear()
    await api.post_group_message(group_openid="G1", msg_id="ROBOT1.0_C", content="first")
    await api.post_group_message(group_openid="G1", msg_id="ROBOT1.0_C", content="second", msg_seq=2)
    await api.post_group_message(group_openid="G1", msg_id="ROBOT1.0_C", content="third")
    seqs = [p["msg_seq"] for p in api._http.payloads]
    assert seqs == [1, 2, 3], seqs
    print("[OK] 显式 msg_seq 与自动递增共存 ->", seqs)

    # 主动消息（无 msg_id）也要递增，避免被平台按 msg_seq 判重
    api._http.payloads.clear()
    for _ in range(3):
        await api.post_group_message(group_openid="G2", content="active")
    seqs = [p["msg_seq"] for p in api._http.payloads]
    assert seqs == [1, 2, 3], seqs
    assert all(p["msg_id"] is None for p in api._http.payloads)
    print("[OK] 主动消息 msg_seq 递增 ->", seqs)

    # event_id 被动回复同样递增
    api._http.payloads.clear()
    await api.post_group_message(group_openid="G3", event_id="EV1", content="a")
    await api.post_group_message(group_openid="G3", event_id="EV1", content="b")
    seqs = [p["msg_seq"] for p in api._http.payloads]
    assert seqs == [1, 2], seqs
    print("[OK] event_id 回复 msg_seq 递增 ->", seqs)


async def test_c2c_msg_seq():
    api = make_api()
    await api.post_c2c_message(openid="U1", msg_id="ROBOT1.0_C2C", content="a")
    await api.post_c2c_message(openid="U1", msg_id="ROBOT1.0_C2C", content="b")
    seqs = [p["msg_seq"] for p in api._http.payloads]
    assert seqs == [1, 2], seqs
    print("[OK] 单聊多次回复 -> msg_seq =", seqs)


def test_trigger():
    bot_id = "BOT_OPENID"
    # 真实抓到的全量事件 content：平台**不会**去掉「@机器人」前缀
    real = "<@93C3B65BF2EE20F5A11FFB14EC18EF85> /通知 "
    # @事件：永远放行
    assert group_trigger.is_triggerable(fake_message(content="你好"), False, bot_ids=(bot_id,))
    # 全量：@机器人 + / 指令 -> 剥掉 <@...> 占位符后命中 / 前缀
    assert group_trigger.is_triggerable(
        fake_message(content=real, mentions=["93C3B65BF2EE20F5A11FFB14EC18EF85"]), True
    )
    assert group_trigger.strip_leading_mentions(real) == "/通知 "
    # 全量：命令前缀
    assert group_trigger.is_triggerable(fake_message(content="/帮助"), True)
    # 全量：白名单关键词
    assert group_trigger.is_triggerable(fake_message(content="vv"), True)
    # 全量：普通聊天 -> 忽略
    assert not group_trigger.is_triggerable(fake_message(content="今天天气不错"), True)
    # 全量：@机器人 且 mentions 标了 bot=true（没带命令）-> 放行
    assert group_trigger.is_triggerable(
        fake_message(content="<@93C3B65B> 你好", mentions=[("93C3B65B", True)]), True
    )
    # 全量：@的是别人 -> 忽略
    assert not group_trigger.is_triggerable(
        fake_message(content="<@AAA> 你好", mentions=[("AAA", False)]), True
    )
    # 全量：候选 id 精确命中（将来能拿到机器人 openid 时）
    assert group_trigger.is_triggerable(
        fake_message(content="<@BOT_OPENID> 你好", mentions=["BOT_OPENID"]),
        True,
        bot_ids=(bot_id,),
    )
    # 全量：图片/卡片（content 为空）-> 忽略
    assert not group_trigger.is_triggerable(fake_message(content=None), True)
    # 全量：只 @ 了机器人、没有正文 -> 忽略
    assert not group_trigger.is_triggerable(
        fake_message(content="<@BOT_OPENID> ", mentions=["BOT_OPENID"]), True, bot_ids=(bot_id,)
    )
    print("[OK] 全量消息触发判定：@机器人+/ 指令、/、vv、@机器人 放行，其余忽略")

    # 去重：同一 msg_id 第二次为重复
    d = group_trigger.MessageDeduper()
    assert d.is_duplicate("M1") is False
    assert d.is_duplicate("M1") is True
    assert d.is_duplicate(None) is False
    print("[OK] msg_id 去重")


async def test_safe_reply():
    from utils.reply import safe_reply

    class Boom:
        id = "MSG_X"
        content = "c"

        async def reply(self, **kwargs):
            raise Exception("40054005 消息被去重，请检查请求msgseq")

    assert await safe_reply(Boom(), content="hello") is False

    class Ok:
        id = "MSG_Y"
        content = "c"

        async def reply(self, **kwargs):
            return {"id": "1"}

    assert await safe_reply(Ok(), content="hello") is True
    print("[OK] safe_reply 失败只记日志、不抛异常")


async def test_internal_find_group_single_reply():
    """兜底找群：飞书不可用时只回复一次，且不再抛 TypeError / 重复回复"""
    import handlers.group_management as gm

    replies = []

    class Msg:
        id = "MSG_Z"
        content = "你好"
        group_openid = "G"

        async def reply(self, **kwargs):
            replies.append(kwargs)

    async def fake_fetch(*args, **kwargs):
        return []

    gm.clear_groups_cache()
    gm.fetch_groups_from_feishu = fake_fetch
    await gm.internal_find_group(api=None, message=Msg(), search_key="你好")
    assert len(replies) == 1, replies
    assert "content" in replies[0], replies
    print("[OK] internal_find_group 飞书失败只回复一次:", replies[0]["content"])

    replies.clear()

    async def fake_fetch2(*args, **kwargs):
        return [{
            "group_id": "123",
            "group_name": "测试群",
            "description": "desc",
            "member_count": 1,
            "max_member_count": 200,
            "url": None,
        }]

    gm.clear_groups_cache()
    gm.fetch_groups_from_feishu = fake_fetch2
    await gm.internal_find_group(api=None, message=Msg(), search_key="测试")
    assert len(replies) == 1, replies
    assert "markdown" in replies[0], replies
    print("[OK] internal_find_group 命中群组只回复一次（markdown）")

    # 群表缓存命中后不应重复拉飞书（默认 @ 每次都要先搜一遍群）
    fetch_calls = []

    async def counting_fetch(*args, **kwargs):
        fetch_calls.append(1)
        return [{
            "group_id": "123",
            "group_name": "测试群",
            "description": "desc",
            "member_count": 1,
            "max_member_count": 200,
            "url": None,
        }]

    gm.clear_groups_cache()
    gm.fetch_groups_from_feishu = counting_fetch
    await gm.search_groups("测试")
    await gm.search_groups("测试")
    assert len(fetch_calls) == 1, fetch_calls
    gm.clear_groups_cache()
    print("[OK] 群表 TTL 缓存生效：5 分钟内重复搜索只拉一次飞书")


async def test_dispatcher_no_duplicate_reply():
    """复现「处理器回复后返回假值 -> 兜底再回一条」：修复后两次回复 msg_seq 递增"""
    import bot_client
    from handlers import kb_qa
    from handlers import group_management as gm

    client = bot_client.EcustmcClient.__new__(bot_client.EcustmcClient)
    client.api = make_api()
    client.robot_id = "BOT_OPENID"

    async def handler_reply_then_false(api, message, params=None):
        # 模拟原来的 query_deltaforce_password：回了用户，却返回 False
        await message.reply(content="第一条：API 请求失败")
        return False

    async def handler_noop(api, message, params=None):
        return False

    async def fake_search(search_key):
        return {"ok": True, "matched": [], "total": 0, "keyword": search_key, "error": None}

    bot_client.handlers = [handler_reply_then_false, handler_noop]
    # 兜底里真正被调用的是 handlers.group_management.search_groups（先搜群）
    kb_qa.gm.search_groups = fake_search
    kb_qa.CAMPUS_QA_ENABLED = False  # 自检不走网络

    msg = fake_message(msg_id="ROBOT1.0_DUP", content="你好", api=client.api)
    await client._handle_group(msg, group_full_message=False)

    seqs = [p["msg_seq"] for p in client.api._http.payloads]
    assert seqs == [1, 2], seqs
    print("[OK] 处理器+兜底各回一次 -> msg_seq =", seqs, "（不会再 40054005）")

    # 兜底回复本身报错时也不允许抛出异常（原来会刷 traceback）
    class BoomMsg(FakeMsg):
        async def reply(self, **kwargs):
            raise Exception("40054005 消息被去重，请检查请求msgseq")

    async def boom_search(search_key):
        raise RuntimeError("飞书 502")

    bot_client.handlers = [handler_noop]
    kb_qa.gm.search_groups = boom_search

    boom = BoomMsg(msg_id="ROBOT1.0_BOOM", content="你好", api=client.api)
    await client._handle_group(boom, group_full_message=False)
    print("[OK] 兜底回复失败时未抛异常（不再刷 traceback）")
    kb_qa.CAMPUS_QA_ENABLED = True


async def test_full_mode_gate_does_not_eat_at_event():
    """全量事件被判定为「非触发」时不能占用 msg_id，否则随后的 @事件 会被去重吃掉"""
    import bot_client

    client = bot_client.EcustmcClient.__new__(bot_client.EcustmcClient)
    client.api = make_api()
    client.robot_id = "BOT_OPENID"

    called = []

    async def handler(api, message, params=None):
        called.append(message.id)
        await message.reply(content="收到")
        return True

    bot_client.handlers = [handler]

    # 1) 群里普通聊天（非 @）以全量事件到达 -> 静默丢弃，且不写入去重表
    plain = fake_message(msg_id="MSG_PLAIN", content="今天天气不错", api=client.api)
    await client._handle_group(plain, group_full_message=True)
    assert called == [], called

    # 2) 同一个 msg_id 随后以 @事件 到达（@机器人 但没带命令）-> 必须被处理
    await client._handle_group(plain, group_full_message=False)
    assert called == ["MSG_PLAIN"], called
    print("[OK] 全量事件被忽略后，@事件仍能正常处理（@了没反应 的坑已堵）")

    # 3) 同一 msg_id 的重复推送依然会被去重
    called.clear()
    await client._handle_group(plain, group_full_message=False)
    assert called == [], called
    print("[OK] 重复推送仍按 msg_id 去重")


async def test_at_command_in_full_mode():
    """复现线上现象：全量模式下「@ECUSTMC /帮助」没反应

    平台下发的 content 是 "<@93C3B65B...> /帮助 "（占位符不会被去掉），
    修复后应能剥掉占位符、命中 / 前缀规则并正常回复一条。
    """
    import bot_client
    from handlers.help import help as help_handler

    client = bot_client.EcustmcClient.__new__(bot_client.EcustmcClient)
    client.api = make_api()
    client.robot_id = 123456789  # botpy 的 robot.id 是数字 appid，跟 openid 对不上

    bot_client.handlers = [help_handler]

    raw = "<@93C3B65BF2EE20F5A11FFB14EC18EF85> /帮助 "
    msg = fake_message(
        msg_id="ROBOT1.0_ATCMD",
        content=raw,
        mentions=["93C3B65BF2EE20F5A11FFB14EC18EF85"],
        api=client.api,
    )
    await client._handle_group(msg, group_full_message=True)

    payloads = client.api._http.payloads
    assert len(payloads) == 1, payloads
    assert payloads[0]["msg_id"] == "ROBOT1.0_ATCMD" and payloads[0]["msg_seq"] == 1, payloads[0]
    assert msg.content == "/帮助 ", repr(msg.content)
    print("[OK] 全量模式「@机器人 /帮助」-> 正常回复一条（占位符已剥离）")

    # 同一条消息再推一次（平台可能重复推送）-> 被去重，不会重复回复
    again = fake_message(
        msg_id="ROBOT1.0_ATCMD", content=raw, mentions=["93C3B65BF2EE20F5A11FFB14EC18EF85"], api=client.api
    )
    await client._handle_group(again, group_full_message=True)
    assert len(client.api._http.payloads) == 1, client.api._http.payloads
    print("[OK] 重复推送被去重，只回复一次")

    # 机器人自己（或别的机器人）发的消息一律不响应，避免自问自答成环
    own = fake_message(
        msg_id="ROBOT1.0_SELF", content="/帮助 ", api=client.api, author_bot=True
    )
    await client._handle_group(own, group_full_message=True)
    assert len(client.api._http.payloads) == 1, client.api._http.payloads
    print("[OK] 机器人自己发的消息被忽略（不会死循环）")


def test_intent_group_detection():
    """默认 @ 的意图判定：找群 vs 校园问答（纯规则，不联网）"""
    from utils import intent

    group_cases = [
        "找群", "/找群 原神", "有没有计算机群", "求个新生群", "群号多少",
        "怎么加群", "拉我进群", "QQ群", "计算机群", "我要找计算机群",
        "篮球群有吗", "新生群", "我想加个社团群", "老乡群在哪", "mc群",
    ]
    question_cases = [
        "转专业怎么申请？", "宿舍几点熄灯", "食堂好吃吗", "军训要带什么",
        "苏群是什么", "学校有哪些社团", "今天天气怎么样", "奖学金怎么评",
        "医保怎么报销", "图书馆开放时间",
    ]
    for text in group_cases:
        assert intent.looks_like_group_search(text), f"应判为找群: {text}"
    for text in question_cases:
        assert not intent.looks_like_group_search(text), f"不应判为找群: {text}"

    assert intent.extract_group_keyword("有没有计算机群") == "计算机"
    assert intent.extract_group_keyword("/找群 原神") == "原神"
    assert intent.extract_group_keyword("我要找计算机群") == "计算机"
    assert intent.extract_group_keyword("我想加个社团群") == "社团"
    assert intent.extract_group_keyword("群号多少") == ""
    assert intent.extract_group_keyword("找群") == ""

    assert intent.is_bare_keyword("原神") and intent.is_bare_keyword("计算机")
    assert not intent.is_bare_keyword("转专业怎么申请")
    assert not intent.is_bare_keyword("宿舍几点熄灯")
    print("[OK] 找群意图判定 / 群关键词提取 / 裸关键词判定")


async def test_default_reply_routing():
    """兜底路由：先搜群 → 大模型判断 → 发群结果 / 查知识库 / 两者都做"""
    from handlers import kb_qa
    from utils import router

    class Msg:
        id = "MSG_ROUTE"
        group_openid = "G"

        def __init__(self, content):
            self.content = content
            self.replies = []

        async def reply(self, **kwargs):
            self.replies.append(kwargs)
            return {"id": "1"}

        def texts(self):
            out = []
            for r in self.replies:
                if "markdown" in r:
                    md = r["markdown"]
                    out.append(md["content"] if isinstance(md, dict) else md.content)
                else:
                    out.append(str(r.get("content")))
            return out

    calls = {"search": [], "ask": [], "decide": []}

    async def fake_ask_found(question):
        calls["ask"].append(question)
        return {
            "ok": True,
            "content": f"关于「{question}」的答案[1]\n![图](https://x.example/a.png)",
            "sources": ["华理新生指南（2026奉贤篇）", "2026学生手册"],
            "no_answer": False,
            "error": None,
            "answer_source": "internal-space",
        }

    async def fake_ask_missing(question):
        calls["ask"].append(question)
        return {
            "ok": True,
            "content": "当前问题可能因内容未收录、解析中、权限受限或命中敏感词无法解答。",
            "sources": [],
            "no_answer": True,
            "error": None,
            "answer_source": "",
        }

    def make_search(matched):
        async def fake_search(search_key):
            calls["search"].append(search_key)
            return {
                "ok": True,
                "matched": matched,
                "total": len(matched),
                "keyword": search_key,
                "error": None,
            }

        return fake_search

    GROUP = {
        "group_id": "615374518",
        "group_name": "CIC计算机信息交流协会",
        "description": "CIC计算机信息交流协会①群",
        "member_count": 1792,
        "max_member_count": 2000,
        "url": None,
    }

    original = (kb_qa.router.decide, kb_qa.ask_knowledge_base,
                kb_qa.CAMPUS_QA_ENABLED, kb_qa.gm.search_groups)
    kb_qa.CAMPUS_QA_ENABLED = True
    try:
        # ① 明确找群 + 有结果 → 直接发群，连大模型都不问（省一次往返）
        calls["decide"].clear()
        calls["search"].clear()
        kb_qa.gm.search_groups = make_search([GROUP])

        async def forbidden_decide(*a, **k):
            calls["decide"].append(a)
            raise AssertionError("明确找群不应该走大模型")

        kb_qa.router.decide = forbidden_decide
        msg = Msg("有没有计算机群")
        assert await kb_qa.handle_default_reply(api=None, message=msg)
        assert calls["search"] == ["计算机"], calls
        assert calls["decide"] == [], calls
        assert len(msg.replies) == 1 and "CIC计算机" in msg.texts()[0], msg.texts()
        print("[OK] 「有没有计算机群」→ 直接发群结果（keyword=计算机，不调用大模型）")

        # ② 校园问题 + 群表无命中 → 大模型说查知识库
        calls["search"].clear()
        calls["ask"].clear()
        kb_qa.gm.search_groups = make_search([])
        kb_qa.ask_knowledge_base = fake_ask_found

        async def decide_kb(user_input, group_result):
            calls["decide"].append(user_input)
            return {"send_group": False, "query_kb": True, "reason": "问学校", "source": "ai"}

        kb_qa.router.decide = decide_kb
        msg = Msg("转专业怎么申请")
        assert await kb_qa.handle_default_reply(api=None, message=msg)
        assert calls["decide"] == ["转专业怎么申请"], calls
        assert calls["ask"] == ["转专业怎么申请"], calls
        assert len(msg.replies) == 1 and "校园问答" in msg.texts()[0], msg.texts()
        assert "华理新生指南" in msg.texts()[0] and "http" not in msg.texts()[0]
        print("[OK] 「转专业怎么申请」→ 大模型判定查知识库（含来源，已去掉图片链接）")

        # ③ 裸词「王者荣耀」+ 群表命中 → 大模型说发群
        calls["search"].clear()
        calls["ask"].clear()
        kb_qa.gm.search_groups = make_search([GROUP])

        async def decide_group(user_input, group_result):
            calls["decide"].append(user_input)
            return {"send_group": True, "query_kb": False, "reason": "找群", "source": "ai"}

        kb_qa.router.decide = decide_group
        msg = Msg("王者荣耀")
        assert await kb_qa.handle_default_reply(api=None, message=msg)
        assert calls["search"] == ["王者荣耀"], calls
        assert calls["ask"] == [], calls
        assert len(msg.replies) == 1 and "CIC计算机" in msg.texts()[0], msg.texts()
        print("[OK] 裸词「王者荣耀」命中群表 → 发群结果，不问知识库")

        # ④ 两者都要：先发群结果，再回知识库答案（两条消息）
        calls["search"].clear()
        calls["ask"].clear()
        kb_qa.gm.search_groups = make_search([GROUP])

        async def decide_both(user_input, group_result):
            calls["decide"].append(user_input)
            return {"send_group": True, "query_kb": True, "reason": "都要", "source": "ai"}

        kb_qa.router.decide = decide_both
        msg = Msg("计算机")
        assert await kb_qa.handle_default_reply(api=None, message=msg)
        assert len(msg.replies) == 2, msg.texts()
        assert "匹配的群组" in msg.texts()[0] and "校园问答" in msg.texts()[1], msg.texts()
        print("[OK] 「计算机」→ 先发群结果再回知识库答案（两条消息）")

        # ⑤ 已经发过群结果时，知识库没收录就保持安静（不再补一条「没找到」）
        calls["ask"].clear()
        kb_qa.ask_knowledge_base = fake_ask_missing
        msg = Msg("计算机")
        assert await kb_qa.handle_default_reply(api=None, message=msg)
        assert calls["ask"] == ["计算机"], calls
        assert len(msg.replies) == 1, msg.texts()
        print("[OK] 发过群结果后知识库没收录 → 不再多回一条")

        # ⑤b 既不发群也不查知识库 → 用已有的 AI 对话回复（/ai 那套）
        calls["search"].clear()
        calls["ask"].clear()
        calls["decide"].clear()
        kb_qa.gm.search_groups = make_search([])

        async def decide_neither(user_input, group_result):
            calls["decide"].append(user_input)
            return {"send_group": False, "query_kb": False, "reason": "闲聊", "source": "ai"}

        kb_qa.router.decide = decide_neither
        ai_calls = []

        async def fake_ai_chat(api=None, message=None):
            ai_calls.append(getattr(message, "content", None))
            await message.reply(content="[AI 对话回复]")
            return True

        msg = Msg("今天天气怎么样")
        assert await kb_qa.handle_default_reply(api=None, message=msg, ai_chat=fake_ai_chat)
        assert calls["ask"] == [] and calls["decide"] == ["今天天气怎么样"], calls
        assert ai_calls == ["今天天气怎么样"], ai_calls
        assert len(msg.replies) == 1 and "AI 对话回复" in msg.texts()[0], msg.texts()
        print("[OK] 两者都不做 → 交给已有的 AI 对话（不查知识库、不发群）")

        # ⑤c 两者都不做且没配 AI 对话 → 给个能用的提示（不能让用户等到空气）
        msg = Msg("今天天气怎么样")
        assert await kb_qa.handle_default_reply(api=None, message=msg, ai_chat=None)
        assert len(msg.replies) == 1 and "接不上话" in msg.texts()[0], msg.texts()
        print("[OK] 两者都不做且未启用 AI 对话 → 回兜底提示")

        # ⑤c2 判定查知识库但知识库没收录 → 交给已有的 AI 对话（不是回「没找到」）
        kb_qa.router.decide = decide_kb
        kb_qa.ask_knowledge_base = fake_ask_missing
        msg = Msg("今天天气怎么样")
        assert await kb_qa.handle_default_reply(api=None, message=msg, ai_chat=fake_ai_chat)
        assert calls["ask"][-1] == "今天天气怎么样", calls
        assert len(msg.replies) == 1 and "AI 对话回复" in msg.texts()[0], msg.texts()
        print("[OK] 知识库没收录 → 交给已有的 AI 对话（学校的事才归知识库）")

        # ⑤d 明确找群但一个都没搜到 → 直接说没找到，不麻烦大模型
        calls["decide"].clear()
        kb_qa.router.decide = forbidden_decide
        msg = Msg("有没有羽毛球群")
        assert await kb_qa.handle_default_reply(api=None, message=msg)
        assert calls["decide"] == [], calls
        assert len(msg.replies) == 1 and "没有找到包含" in msg.texts()[0], msg.texts()
        print("[OK] 「有没有羽毛球群」搜不到 → 直接回没找到（不调用大模型）")

        # ⑥ 大模型挂了 → 规则降级：裸词命中群表发群、问题查知识库
        calls["search"].clear()
        calls["ask"].clear()
        kb_qa.ask_knowledge_base = fake_ask_found
        kb_qa.router.decide = original[0]  # 用真实 decide（内部调 _call_model）
        kb_qa.gm.search_groups = make_search([GROUP])

        def boom(*a, **k):
            raise RuntimeError("502 Bad Gateway")

        original_call = router._call_model
        router._call_model = boom
        try:
            msg = Msg("三角洲")
            assert await kb_qa.handle_default_reply(api=None, message=msg)
            assert calls["ask"] == [] and len(msg.replies) == 1, (calls, msg.texts())
            assert "匹配的群组" in msg.texts()[0], msg.texts()

            kb_qa.gm.search_groups = make_search([])
            msg = Msg("宿舍几点熄灯")
            assert await kb_qa.handle_default_reply(api=None, message=msg)
            assert calls["ask"][-1] == "宿舍几点熄灯", calls
            assert "校园问答" in msg.texts()[0], msg.texts()
        finally:
            router._call_model = original_call
        print("[OK] 大模型不可用（502）→ 规则降级：裸词发群、提问查知识库")

        # ⑦ 知识库关闭时保持旧行为：一律找群
        kb_qa.CAMPUS_QA_ENABLED = False
        calls["search"].clear()
        calls["ask"].clear()
        msg = Msg("转专业怎么申请")
        assert await kb_qa.handle_default_reply(api=None, message=msg)
        assert calls["search"] == ["转专业 申请"] and calls["ask"] == [], calls
        assert "没有找到包含" in msg.texts()[0], msg.texts()
        print("[OK] 校园问答关闭时保持旧行为（默认 @ 一律找群）")
    finally:
        (kb_qa.router.decide, kb_qa.ask_knowledge_base,
         kb_qa.CAMPUS_QA_ENABLED, kb_qa.gm.search_groups) = original


async def test_ai_fallback_uses_ecust_model():
    """AI 兜底一律用 ECUST_MODEL：clawdbot 那套已删除，失败不把原始报错甩给用户"""
    from handlers import ai, kb_qa
    from config import MODEL_CONFIGS
    import config
    import r

    class Msg:
        id = "MSG_AI_FALLBACK"
        group_openid = "G"

        def __init__(self, content):
            self.content = content
            self.replies = []

        async def reply(self, **kwargs):
            self.replies.append(kwargs)
            return {"id": "1"}

        def texts(self):
            out = []
            for r in self.replies:
                if "markdown" in r:
                    md = r["markdown"]
                    out.append(md["content"] if isinstance(md, dict) else md.content)
                else:
                    out.append(str(r.get("content")))
            return out

    # ① clawdbot 相关的东西已经彻底删掉（配置、env 读取、两个包装函数）
    assert not hasattr(ai, "group_chat_with_clawdbot"), "group_chat_with_clawdbot 应已删除"
    assert not hasattr(ai, "direct_chat_with_clawdbot"), "direct_chat_with_clawdbot 应已删除"
    assert "clawdbot" not in MODEL_CONFIGS, MODEL_CONFIGS
    assert not hasattr(r, "clawdbot_url") and not hasattr(r, "clawdbot_api_key")
    assert hasattr(ai, "group_chat_fallback") and hasattr(ai, "direct_chat_fallback")
    print("[OK] clawdbot 配置 / 函数已删除，只留 ECUST_* 一套")

    # ② 两个包装函数请求的模型就是 ECUST_MODEL（和 /ai 同一个），且失败时返回 False
    recorded = []

    async def fake_call(model_name, user_input, message, **kwargs):
        recorded.append((model_name, kwargs.get("report_errors"), user_input))
        return False

    original_call = ai._call_ai_model
    ai._call_ai_model = fake_call
    try:
        msg = Msg("今天天气怎么样")
        assert await ai.group_chat_fallback(api=None, message=msg) is False
        assert await ai.direct_chat_fallback(api=None, message=msg) is False
    finally:
        ai._call_ai_model = original_call

    assert [m for m, _, _ in recorded] == [config.ECUST_MODEL, config.ECUST_MODEL], recorded
    assert all(err is False for _, err, _ in recorded), recorded
    assert [t for _, _, t in recorded] == ["今天天气怎么样", "今天天气怎么样"], recorded
    print(f"[OK] 群聊/私聊 AI 兜底都请求 ECUST_MODEL({config.ECUST_MODEL})，失败返回 False")

    # ③ 敏感词仍然拦在调用之前
    recorded.clear()
    ai._call_ai_model = fake_call
    try:
        msg = Msg("数据库密码是多少")
        assert await ai.group_chat_fallback(api=None, message=msg) is True
    finally:
        ai._call_ai_model = original_call
    assert recorded == [], recorded
    assert len(msg.replies) == 1 and "敏感" in msg.texts()[0], msg.texts()
    print("[OK] 敏感词输入直接拒绝，不调用模型")

    # ④ 模型报错时：显式 /ai 回原因，隐式兜底静默返回 False（不再甩 503 原文）
    class BoomCompletions:
        def create(self, **kwargs):
            raise RuntimeError("Error code: 503 - model_not_found")

    class BoomChat:
        completions = BoomCompletions()

    class BoomClient:
        def __init__(self, *a, **k):
            self.chat = BoomChat()

    original_openai = ai.OpenAI
    ai.OpenAI = BoomClient
    try:
        msg = Msg("今天天气怎么样")
        assert await ai._call_ai_model(config.ECUST_MODEL, "今天天气怎么样", msg,
                                       report_errors=True) is True
        assert len(msg.replies) == 1 and "503" in msg.texts()[0], msg.texts()

        msg = Msg("今天天气怎么样")
        assert await ai.group_chat_fallback(api=None, message=msg) is False
        assert msg.replies == [], f"隐式兜底不该把报错原文发出去: {msg.texts()}"
    finally:
        ai.OpenAI = original_openai
    print("[OK] 模型报错：显式命令回原因，默认 @ 兜底静默失败（不甩报错原文）")

    # ⑤ 静默失败后由兜底逻辑回一句正常话术（而不是让用户对着空气/报错发呆）
    async def failing_ai_chat(api=None, message=None):
        return False

    msg = Msg("今天天气怎么样")
    assert await kb_qa.fallback_ai_reply(api=None, message=msg, ai_chat=failing_ai_chat)
    assert len(msg.replies) == 1 and kb_qa.FALLBACK_REPLY in msg.texts()[0], msg.texts()
    print("[OK] AI 兜底静默失败 → 回兜底话术（单条、不含原始报错）")


async def test_kb_answer_with_images():
    """知识库答案带插图：按 QQ markdown 语法内嵌进同一条卡片（/塔罗牌 那种发法）"""
    import re
    import struct

    from handlers import kb_qa

    # ① 图片头部字节 → 宽高（离线，不联网）
    png = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + struct.pack(">II", 1920, 1440) + b"rest"
    assert kb_qa.parse_image_size(png) == (1920, 1440), kb_qa.parse_image_size(png)
    gif = b"GIF89a" + struct.pack("<HH", 320, 240) + b"\x00" * 4
    assert kb_qa.parse_image_size(gif) == (320, 240)
    jpeg = (
        b"\xff\xd8"
        + b"\xff\xe0" + struct.pack(">H", 16) + b"JFIF\x00" + b"\x00" * 9   # APP0
        + b"\xff\xc0" + struct.pack(">H", 17) + b"\x08"                    # SOF0
        + struct.pack(">HH", 1080, 1920) + b"\x03" + b"\x00" * 9
    )
    assert kb_qa.parse_image_size(jpeg) == (1920, 1080), kb_qa.parse_image_size(jpeg)
    assert kb_qa.parse_image_size(b"not an image") is None
    assert kb_qa.parse_image_size(b"") is None

    # ② 尺寸提示：超宽等比缩到 600px
    assert kb_qa.size_hint((1920, 1440)) == " #600px #450px", kb_qa.size_hint((1920, 1440))
    assert kb_qa.size_hint((300, 200)) == " #300px #200px"
    assert kb_qa.size_hint(None) == "" and kb_qa.size_hint((0, 5)) == ""

    # ③ 抽图：按出现顺序去重、带上限
    md = (
        "宿舍条件如下：\n"
        "![阳台等布局](https://image-ai.lexiang-asset.com/a/img_1.png-resize1920?sign=abc)\n"
        "还有 ![盥洗室](https://image-ai.lexiang-asset.com/a/img_2.png?sign=def)\n"
        "重复引用 ![阳台等布局](https://image-ai.lexiang-asset.com/a/img_1.png-resize1920?sign=abc)\n"
        "![三](https://image-ai.lexiang-asset.com/a/img_3.png)\n"
        "![四](https://image-ai.lexiang-asset.com/a/img_4.png)"
    )
    images = kb_qa.extract_images(md)
    assert len(images) == kb_qa.MAX_IMAGES == 3, images
    assert images[0]["alt"] == "阳台等布局" and "img_1" in images[0]["url"]
    assert "img_2" in images[1]["url"] and images[2]["url"].endswith("img_3.png"), images
    assert kb_qa.extract_images("没有图") == []

    # ③b `$…$` → 纯文本（乐享连时间、分数都用 $ 包，QQ markdown 不渲染）
    assert kb_qa.latex_to_text(r"$90\text{cm}\times39\text{cm}$") == "90cm×39cm"
    assert kb_qa.latex_to_text(r"$195\times85\text{cm}$") == "195×85cm"
    assert kb_qa.latex_to_text(r"$x^{2}+1\le 3$") == "x²+1≤ 3"
    assert kb_qa.latex_to_text(r"开放 $11:00-23:00$，熄灯 $23:00$") == "开放 11:00-23:00，熄灯 23:00"
    assert kb_qa.latex_to_text(r"卫生差 $2-14$ 次 $-0.5$ 分") == "卫生差 2-14 次 -0.5 分"
    assert kb_qa.latex_to_text(r"$\frac{1}{2}$ 与 $\sqrt{9}$") == "1/2 与 √9"
    assert kb_qa.latex_to_text(r"床下空间高度 $29\text{cm}$，够放箱子") == "床下空间高度 29cm，够放箱子"
    assert kb_qa.latex_to_text("价格 5 元") == "价格 5 元"      # 没有 $ 就一个字都不动
    assert kb_qa.latex_to_text("没有公式") == "没有公式"

    # ④ 内嵌：前 3 张带尺寸提示，第 4 张删掉；未解析出尺寸的图也能内嵌
    for image in images:
        image["hint"] = kb_qa.size_hint((1920, 1440))
    content = kb_qa.apply_images(md, images)
    assert content.count("![") == 3, content
    assert "![阳台等布局 #600px #450px](https://image-ai.lexiang-asset.com/a/img_1.png-resize1920?sign=abc)" in content
    assert "img_4" not in content, content

    # ⑤ 整条卡片：一条 markdown、图在正文里、来源齐全、裸链接清掉
    card = kb_qa.format_answer(
        {
            "content": "宿舍 23:00 熄灯[1]\n" + md + "\n参考 https://lexiang.example/doc",
            "sources": ["华理新生指南（2026奉贤篇）"],
            "images": images,
        }
    )
    assert "## 🎓 校园问答" in card and "来源：《华理新生指南（2026奉贤篇）》" in card
    assert card.count("![") == 3 and "#600px #450px" in card
    assert "lexiang.example" not in card and "img_4" not in card
    # 图片标记必须完整（清理裸链接时不能把 `![…](url)` 里的 url 一起吃掉）
    assert (
        "![阳台等布局 #600px #450px]"
        "(https://image-ai.lexiang-asset.com/a/img_1.png-resize1920?sign=abc)" in card
    ), card

    # ⑥ 超长正文按「纯文字」截断：已经内嵌的图片标记不会被拦腰截断
    long_card = kb_qa.format_answer(
        {
            "content": "啊" * 2500 + "\n" + md,
            "sources": [],
            "images": images,
        }
    )
    assert "…（内容较长，已截断）" in long_card, long_card[-80:]
    # 文字已经把预算吃光，卡片里不该留下半截图片标记
    assert "![" not in long_card, long_card[-120:]

    partly = kb_qa.format_answer(
        {"content": "啊" * 1990 + "\n" + md, "sources": [], "images": images}
    )
    # 预算内出现的图片是完整的：每个 `![` 都能配上一个闭合的 `](…)`
    assert partly.count("![") == len(re.findall(r"!\[[^\]]*\]\([^)]*\)", partly)), partly[-160:]
    assert "…（内容较长，已截断）" in partly
    # 截断路径不能把 alt / url 当成独立片段漏进正文（re.split 捕获组踩过的坑）
    assert partly.count(images[0]["url"]) == 1, partly[-200:]
    for image in images[1:]:
        assert partly.count(image["url"]) <= 1, partly[-200:]
    no_markup = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", partly)
    assert "#600px #450px" not in no_markup, "尺寸提示漏到正文里了"

    mid = (
        "啊" * 1990
        + "\n![保留](https://img.example/keep.png)\n"
        + "尾" * 200
        + "![丢](https://img.example/drop.png)"
    )
    mid_card = kb_qa.format_answer(
        {
            "content": mid,
            "sources": [],
            "images": [{"url": "https://img.example/keep.png", "alt": "保留", "hint": " #600px #400px"}],
        }
    )
    assert "![保留 #600px #400px](https://img.example/keep.png)" in mid_card, mid_card[-200:]
    assert "drop.png" not in mid_card and "…（内容较长，已截断）" in mid_card

    # ⑦ 完整流程：一条回复（msg_type=2 markdown），图在卡片里
    replies = []

    class Msg:
        content = "宿舍几点熄灯"
        group_openid = "G1"

        async def reply(self, **kwargs):
            replies.append(kwargs)

    original_ask = kb_qa.ask_knowledge_base

    async def fake_ask(question):
        return {
            "ok": True,
            "content": "宿舍 23:00 熄灯[1]\n![布局](https://img.example/a.png)",
            "sources": ["华理新生指南（2026奉贤篇）"],
            "no_answer": False,
            "error": None,
            "answer_source": "internal-space",
            "images": [{"url": "https://img.example/a.png", "alt": "布局", "hint": " #600px #400px"}],
        }

    kb_qa.ask_knowledge_base = fake_ask
    try:
        assert await kb_qa.answer_school_question(None, Msg(), "宿舍几点熄灯")
    finally:
        kb_qa.ask_knowledge_base = original_ask
    assert len(replies) == 1, replies
    assert replies[0]["msg_type"] == 2 and "markdown" in replies[0]
    text = replies[0]["markdown"]["content"]
    assert "![布局 #600px #400px](https://img.example/a.png)" in text, text
    print("[OK] 知识库配图：尺寸解析 / 内嵌 markdown 卡片 / 上限与截断 / 整条流程")


def test_router_env_is_independent():
    """路由用独立的一套 env（ROUTER_*），不能和 /ai、/model 的 ECUST_* 共用"""
    import importlib

    import config
    from utils import router

    assert hasattr(config, "ROUTER_API_KEY") and hasattr(config, "ROUTER_URL")
    cfg = router._model_config()
    assert set(cfg) == {"api_key", "base_url", "model"}, cfg
    assert cfg["model"] == config.ROUTER_MODEL, cfg
    assert cfg["base_url"] == config.ROUTER_URL, cfg
    # /model 会改 ECUST_MODEL，路由不受影响
    original_model, original_ecust = config.ROUTER_MODEL, config.ECUST_MODEL
    try:
        config.ECUST_MODEL = "别的模型"
        config.MODEL_CONFIGS["别的模型"] = {"api_key": "x", "base_url": "http://other/v1"}
        assert router._model_config()["model"] == original_model
        assert router._model_config()["base_url"] == config.ROUTER_URL
    finally:
        config.ECUST_MODEL = original_ecust
    print("[OK] 路由配置独立（/model 换 ECUST_MODEL 不影响路由模型与入口）")


def test_router_parsing_and_rules():
    """路由：JSON 解析容错 + 规则降级 + 「都不做」交给 AI 对话"""
    from utils import intent, router

    assert router.parse_decision('{"send_group": true, "query_kb": false}') == {
        "send_group": True, "query_kb": False, "reason": ""
    }
    parsed = router.parse_decision(
        '好的，判断如下：\n```json\n{"send_group": false, "query_kb": true, "reason": "校园问题"}\n```\n'
    )
    assert parsed and parsed["query_kb"] is True and parsed["reason"] == "校园问题", parsed
    assert router.parse_decision("我觉得应该找群") is None
    assert router.parse_decision('{"foo": 1}') is None

    matched = [{"group_name": "原神群", "group_id": "1", "member_count": 1,
                "max_member_count": 200, "description": "原神"}]
    # 规则降级：找群 → 发群；提问 → 查知识库；短词/闲聊 → 交给 AI 对话
    assert router.heuristic_decide("原神", {"matched": matched})["send_group"] is True
    assert router.heuristic_decide("有没有计算机群", {"matched": []})["send_group"] is True
    kb = router.heuristic_decide("转专业怎么申请", {"matched": matched})
    assert kb["query_kb"] is True and kb["send_group"] is False, kb
    # 有疑问词 → 先按校园提问处理；知识库没收录时再由 answer_school_question 交给 AI 对话
    weather = router.heuristic_decide("今天天气怎么样", {"matched": []})
    assert weather["query_kb"] is True, weather
    # 短词/算术这类既没命中群表、也不像校园问题 → 两个都不做，走 AI 对话
    for text in ("1+1", "原神"):
        rule = router.heuristic_decide(text, {"matched": []})
        assert rule == {"send_group": False, "query_kb": False, "reason": "规则：交给 AI 对话"}, rule

    prompt = router.build_prompt("王者荣耀", {"matched": matched, "keyword": "王者荣耀"})
    assert "王者荣耀" in prompt and "原神群" in prompt, prompt
    prompt = router.build_prompt("宿舍", {"matched": [], "keyword": "宿舍"})
    assert "没有匹配的群" in prompt, prompt

    # 明确找群：全量消息模式的零成本触发判定
    for text in ["有没有计算机群", "找一下新生群", "求个原神群", "拉我进群", "群号多少", "有没有三角洲群"]:
        assert intent.is_explicit_group_search(text), text
    for text in ["王者荣耀", "这个群好热闹", "计算机群", "篮球群有吗", "群号：615374518", "老乡群在哪"]:
        assert not intent.is_explicit_group_search(text), text
    print("[OK] 路由 JSON 解析容错 / 规则降级（含「都不做→AI对话」）/ 全量模式明确找群判定")


def test_group_matching_with_real_table():
    """用真实飞书群表导出（tests/fixtures/feishu_groups.json）验证找群匹配"""
    import json
    import os

    from handlers import group_management as gm
    from utils import intent

    path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "tests", "fixtures", "feishu_groups.json")
    groups = json.load(open(path, encoding="utf-8"))["groups"]
    assert len(groups) > 100, len(groups)

    def names(keyword):
        return [g["group_name"] for g in gm.match_groups(groups, keyword)]

    # 历史惯性：群友只丢一个游戏/话题名，靠群名或「描述」里的关键词命中
    assert any("王者荣耀" in n for n in names("王者荣耀")), names("王者荣耀")
    assert len(names("三角洲")) >= 2, names("三角洲")          # 描述里是 "三角洲行动/Delta Force"
    assert any("空月之歌" in n for n in names("原神")), names("原神")
    assert any("龙历院" in n for n in names("怪猎")), names("怪猎")  # 描述里是 "怪物猎人/怪猎/MH"
    assert any("doro" in n for n in names("妮姬")), names("妮姬")
    assert len(names("计算机")) >= 3, names("计算机")
    # 大小写/空格不敏感
    assert names("delta force") and names("DeltaForce"), names("delta force")

    # 关键：校园问题不该误命中任何群（否则会被当成找群，答不上学校的事）
    for question in ["转专业 申请", "宿舍几点熄灯", "医保报销", "奖学金评定", "军训要带什么"]:
        assert names(question) == [], (question, names(question))

    # 不可信的群一个都不能出现（飞书表里有 是否可信=false 的记录）
    untrusted = [g for g in groups if not g.get("trusted", True)]
    assert untrusted, "快照里应该保留是否可信标记（含不可信样本）"
    for group in untrusted:
        assert gm.match_groups(groups, group["group_name"]) == [], group["group_name"]
        assert gm.match_groups(groups, group["group_id"]) == [], group["group_id"]
    # 直接问群号也拿不到不可信的群
    assert all(gm.is_trusted(g) for g in gm.match_groups(groups, "群")), "匹配结果含不可信群"

    # 关键词提取 → 匹配，串起来跑一遍
    for text, expect in [("有没有王者荣耀群", "王者荣耀"), ("求个怪猎群", "怪猎"),
                         ("我想加个三角洲群", "三角洲")]:
        keyword = intent.extract_group_keyword(text)
        assert keyword == expect, (text, keyword)
        assert gm.match_groups(groups, keyword), (text, keyword)

    # 真实群名（"华理辽宁群""华理东方群"）本来就长得像找群，这是期望行为：
    # 用户直接报群名时应该去找群。真正要防的是「校园提问被判成找群」。
    for question in ["转专业 申请", "宿舍几点熄灯", "医保报销", "军训要带什么",
                     "奖学金怎么评", "绩点怎么算"]:
        assert not intent.looks_like_group_search(question), question
    # 群表里的「描述」是话题清单，不该被判成找群
    topic_false_positive = [
        g["description"] for g in groups if intent.looks_like_group_search(g["description"])
    ]
    assert len(topic_false_positive) <= 3, topic_false_positive
    print(f"[OK] 真实群表（{len(groups)} 个群）匹配：游戏/话题名命中、校园提问 0 误命中")


def test_lexiang_answer_cleaning():
    """乐享返回内容的清洗、引用解析与响应信封解析"""
    from handlers.kb_qa import MAX_REPLY_CHARS, clean_answer, format_answer
    from utils.lexiang_client import (
        LexiangClient,
        LexiangError,
        parse_targets,
        unwrap_payload,
    )

    # 两种响应风格都要能解析：AI 助手类带 code，知识库类是 JSON:API
    assert unwrap_payload("cgi-bin/v1/ai/qa", 200, {"code": 0, "data": {"content": "x"}}) == {
        "content": "x"
    }
    space = unwrap_payload(
        "cgi-bin/v1/kb/spaces/19e3",
        200,
        {"data": {"id": "19e3", "attributes": {"name": "苏群新生指南"}}, "included": []},
    )
    assert space["attributes"]["name"] == "苏群新生指南", space
    try:
        unwrap_payload("cgi-bin/v1/kb/teams", 403, {"code": 403, "message": "版本需升级后启用"})
        raise AssertionError("错误码应抛 LexiangError")
    except LexiangError as e:
        assert e.code == 403 and "版本需升级" in e.message, e

    raw = (
        "看这里 ![图](https://x.example/y.png)\n"
        "[IMAGE]abc[/IMAGE]\n"
        "链接 https://z.example/a?b=1 结束"
    )
    out = clean_answer(raw)
    assert "http" not in out and "IMAGE" not in out and "看这里" in out and "结束" in out, out

    # 插图相关的解析见 test_kb_answer_with_images（尺寸/内嵌/截断都在那边测）
    out = clean_answer("句子。" * 800, limit=200)
    assert len(out) <= 260, len(out)
    assert out.endswith("…（内容较长，已截断）"), out[-30:]

    client = LexiangClient(app_key="k", app_secret="s")
    parsed = client.extract_answer(
        {
            "content": "答案[1]",
            "answer_source": "internal-team",
            "additional_content": {
                "reference_docs": [{"title": "新生指南"}, {"title": "学生手册"}],
                "reference_chunks": [{"title": "新生指南"}],
            },
        }
    )
    assert parsed["sources"] == ["新生指南", "学生手册"], parsed
    assert parsed["no_answer"] is False and parsed["answer_source"] == "internal-team"

    parsed = client.extract_answer(
        {"content": "当前问题可能因内容未收录、解析中、权限受限或命中敏感词无法解答。"}
    )
    assert parsed["no_answer"] is True, parsed
    assert client.extract_answer({"content": ""})["no_answer"] is True

    markdown = format_answer(
        {"content": "宿舍 23:00 熄灯[1]", "sources": ["华理新生指南（2026奉贤篇）"]}
    )
    assert "校园问答" in markdown and "熄灯" in markdown and "来源" in markdown

    assert parse_targets("space:abc, kb_entry:def") == [
        {"type": "space", "id": "abc"},
        {"type": "kb_entry", "id": "def"},
    ]
    assert parse_targets("") == []
    assert parse_targets("bogus:xx,team:yy") == [{"type": "team", "id": "yy"}]
    # 默认知识范围应锁定「苏群新生指南」（space 19e38335…）
    from config import CAMPUS_KB_SPACE_ID, LEXIANG_TARGETS

    assert parse_targets(LEXIANG_TARGETS) == [{"type": "space", "id": CAMPUS_KB_SPACE_ID}], LEXIANG_TARGETS
    assert MAX_REPLY_CHARS >= 500
    print("[OK] 乐享响应信封 / 答案清洗与配图抽取 / 引用解析 / targets 解析 / 回复模板")


async def test_full_mode_routing():
    """全量消息模式：@了机器人走完整兜底，明确找群只搜群，其余闲聊静默"""
    import bot_client
    from handlers import kb_qa
    from handlers import group_management as gm

    client = bot_client.EcustmcClient.__new__(bot_client.EcustmcClient)
    client.api = make_api()
    client.robot_id = 123456789

    asked = []
    searched = []
    decided = []

    async def fake_ask(question):
        asked.append(question)
        return {"ok": True, "content": "知识库答案", "sources": [], "no_answer": False,
                "error": None, "answer_source": "internal-space"}

    async def fake_search(search_key):
        searched.append(search_key)
        return {"ok": True, "matched": [{
            "group_id": "615374518", "group_name": "CIC计算机信息交流协会",
            "description": "CIC", "member_count": 1792, "max_member_count": 2000, "url": None,
        }], "total": 1, "keyword": search_key, "error": None}

    async def fake_decide(user_input, group_result):
        decided.append(user_input)
        return {"send_group": False, "query_kb": True, "reason": "校园问题", "source": "ai"}

    originals = (bot_client.handlers, kb_qa.ask_knowledge_base,
                 kb_qa.router.decide, kb_qa.CAMPUS_QA_ENABLED, gm.search_groups)
    bot_client.handlers = []
    kb_qa.ask_knowledge_base = fake_ask
    kb_qa.router.decide = fake_decide
    kb_qa.CAMPUS_QA_ENABLED = True
    gm.search_groups = fake_search
    try:
        # ① 普通群聊（没 @ 机器人、也不是找群）→ 静默
        plain = fake_message(msg_id="FULL_PLAIN", content="今天天气不错", api=client.api)
        await client._handle_group(plain, group_full_message=True)
        assert searched == [] and asked == [] and decided == [], (searched, asked, decided)
        assert client.api._http.payloads == []
        print("[OK] 全量模式：普通闲聊完全静默（不搜群、不调模型/知识库）")

        # ② @了机器人 + 校园问题 → 和 @事件 一样走完整兜底（找群 → 路由 → 查知识库）
        at = fake_message(
            msg_id="FULL_AT", content="<@BOT_OPENID> 宿舍几点熄灯 ",
            mentions=[("BOT_OPENID", True)], api=client.api,
        )
        await client._handle_group(at, group_full_message=True)
        # 群表搜索用的是剥掉疑问词后的关键词（"宿舍几点熄灯" → "宿舍 熄灯"），
        # 而交给路由/知识库的是用户原话
        assert len(searched) == 1 and "宿舍" in searched[0], searched
        assert decided == ["宿舍几点熄灯"], decided
        assert asked == ["宿舍几点熄灯"], asked
        assert len(client.api._http.payloads) == 1, client.api._http.payloads
        print("[OK] 全量模式：@机器人 提问 → 走完整兜底并查知识库（和 @事件 一致）")

        # ③ @了机器人 + 裸词「王者荣耀」→ 同样走完整兜底（不再被静默丢掉）
        searched.clear()
        asked.clear()
        decided.clear()
        client.api._http.payloads.clear()
        bare_at = fake_message(
            msg_id="FULL_AT_BARE", content="<@BOT_OPENID> 王者荣耀 ",
            mentions=[("BOT_OPENID", True)], api=client.api,
        )
        await client._handle_group(bare_at, group_full_message=True)
        assert decided == ["王者荣耀"], decided
        assert len(client.api._http.payloads) == 1, client.api._http.payloads
        print("[OK] 全量模式：@机器人 说裸词「王者荣耀」→ 交给完整兜底（不再没反应）")

        # ④ 明确的找群句式（不用 @）→ 零成本快速通道：只搜群，不调模型/知识库
        searched.clear()
        asked.clear()
        decided.clear()
        client.api._http.payloads.clear()
        found = fake_message(msg_id="FULL_FOUND", content="有没有计算机群", api=client.api)
        await client._handle_group(found, group_full_message=True)
        assert searched == ["计算机"], searched
        assert asked == [] and decided == [], (asked, decided)
        assert len(client.api._http.payloads) == 1, client.api._http.payloads
        assert "CIC计算机" in client.api._http.payloads[0]["markdown"]["content"]
        print("[OK] 全量模式：「有没有计算机群」只搜群并回复（零模型成本，不 @ 也响应）")

        # ⑤ @了机器人 + 明确找群 → 仍走便宜的快速通道（先判找群，再考虑完整兜底）
        searched.clear()
        asked.clear()
        decided.clear()
        client.api._http.payloads.clear()
        at_found = fake_message(
            msg_id="FULL_AT_FOUND", content="<@BOT_OPENID> 有没有计算机群 ",
            mentions=[("BOT_OPENID", True)], api=client.api,
        )
        await client._handle_group(at_found, group_full_message=True)
        assert searched == ["计算机"], searched
        assert decided == [] and asked == [], (decided, asked)
        assert len(client.api._http.payloads) == 1, client.api._http.payloads
        print("[OK] 全量模式：@机器人 + 明确找群 → 仍走只搜群的快速通道")

        # ⑥ 没 @ 的裸词（历史惯性的「王者荣耀」）→ 保持安静，避免关键词误触发
        searched.clear()
        asked.clear()
        decided.clear()
        client.api._http.payloads.clear()
        bare = fake_message(msg_id="FULL_BARE", content="王者荣耀", api=client.api)
        await client._handle_group(bare, group_full_message=True)
        assert searched == [] and decided == [] and asked == [], (searched, decided, asked)
        assert client.api._http.payloads == []
        print("[OK] 全量模式：没 @ 的裸词「王者荣耀」保持安静（不打扰群聊）")
    finally:
        (bot_client.handlers, kb_qa.ask_knowledge_base,
         kb_qa.router.decide, kb_qa.CAMPUS_QA_ENABLED, gm.search_groups) = originals


async def main():
    apply_reply_seq_patch()
    await test_msg_seq_passive_increments()
    await test_c2c_msg_seq()
    test_trigger()
    await test_safe_reply()
    await test_internal_find_group_single_reply()
    await test_dispatcher_no_duplicate_reply()
    await test_full_mode_gate_does_not_eat_at_event()
    await test_at_command_in_full_mode()
    test_intent_group_detection()
    await test_default_reply_routing()
    await test_ai_fallback_uses_ecust_model()
    await test_kb_answer_with_images()
    test_router_env_is_independent()
    test_router_parsing_and_rules()
    test_group_matching_with_real_table()
    await test_full_mode_routing()
    test_lexiang_answer_cleaning()
    print("\n全部自检通过")


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

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
    def __init__(self, msg_id="MSG_A", content="/帮助", mentions=(), api=None, group_openid="G1"):
        self.id = msg_id
        self.content = content
        self.mentions = [
            SimpleNamespace(id=m, member_openid=m, union_openid=None) for m in mentions
        ]
        self.message_type = 0
        self.group_openid = group_openid
        self.api = api

    async def reply(self, **kwargs):
        return await self.api.post_group_message(
            group_openid=self.group_openid, msg_id=self.id, **kwargs
        )


def fake_message(msg_id="MSG_A", content="/帮助", mentions=(), api=None):
    return FakeMsg(msg_id=msg_id, content=content, mentions=mentions, api=api)


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
    # @事件：永远放行
    assert group_trigger.is_triggerable(fake_message(content="你好"), False, bot_id=bot_id)
    # 全量：命令前缀
    assert group_trigger.is_triggerable(fake_message(content="/帮助"), True, bot_id=bot_id)
    # 全量：白名单关键词
    assert group_trigger.is_triggerable(fake_message(content="vv"), True, bot_id=bot_id)
    # 全量：普通聊天 -> 忽略
    assert not group_trigger.is_triggerable(fake_message(content="今天天气不错"), True, bot_id=bot_id)
    # 全量：@了机器人但没带命令前缀（content 里的 @ 已被平台去掉）-> 放行
    assert group_trigger.is_triggerable(
        fake_message(content="你好", mentions=[bot_id]), True, bot_id=bot_id
    )
    # 全量：@的是别人 -> 忽略
    assert not group_trigger.is_triggerable(
        fake_message(content="你好", mentions=["SOMEONE_ELSE"]), True, bot_id=bot_id
    )
    # 全量：拿不到机器人 id 时保守忽略（不会误触发）
    assert not group_trigger.is_triggerable(
        fake_message(content="你好", mentions=[bot_id]), True, bot_id=None
    )
    # 全量：图片/卡片（content 为空）-> 忽略
    assert not group_trigger.is_triggerable(fake_message(content=None), True, bot_id=bot_id)
    print("[OK] 全量消息触发判定：/ 前缀、vv、@机器人 放行，其余忽略")

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

    gm.fetch_groups_from_feishu = fake_fetch2
    await gm.internal_find_group(api=None, message=Msg(), search_key="测试")
    assert len(replies) == 1, replies
    assert "markdown" in replies[0], replies
    print("[OK] internal_find_group 命中群组只回复一次（markdown）")


async def test_dispatcher_no_duplicate_reply():
    """复现「处理器回复后返回假值 -> 兜底再回一条」：修复后两次回复 msg_seq 递增"""
    import bot_client

    client = bot_client.EcustmcClient.__new__(bot_client.EcustmcClient)
    client.api = make_api()
    client.robot_id = "BOT_OPENID"

    async def handler_reply_then_false(api, message, params=None):
        # 模拟原来的 query_deltaforce_password：回了用户，却返回 False
        await message.reply(content="第一条：API 请求失败")
        return False

    async def handler_noop(api, message, params=None):
        return False

    async def fallback(api, message, search_key):
        # 原来的 internal_find_group 兜底会再回一条
        await message.reply(content=f"第二条：没有找到包含 '{search_key}' 的群组")

    bot_client.handlers = [handler_reply_then_false, handler_noop]
    bot_client.internal_find_group = fallback

    msg = fake_message(msg_id="ROBOT1.0_DUP", content="你好", api=client.api)
    await client._handle_group(msg, group_full_message=False)

    seqs = [p["msg_seq"] for p in client.api._http.payloads]
    assert seqs == [1, 2], seqs
    print("[OK] 处理器+兜底各回一次 -> msg_seq =", seqs, "（不会再 40054005）")

    # 兜底回复本身报错时也不允许抛出异常（原来会刷 traceback）
    class BoomMsg(FakeMsg):
        async def reply(self, **kwargs):
            raise Exception("40054005 消息被去重，请检查请求msgseq")

    async def boom_fallback(api, message, search_key):
        await message.reply(content="兜底再回一条")

    bot_client.handlers = [handler_noop]
    bot_client.internal_find_group = boom_fallback

    boom = BoomMsg(msg_id="ROBOT1.0_BOOM", content="你好", api=client.api)
    await client._handle_group(boom, group_full_message=False)
    print("[OK] 兜底回复失败时未抛异常（不再刷 traceback）")


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


async def main():
    apply_reply_seq_patch()
    await test_msg_seq_passive_increments()
    await test_c2c_msg_seq()
    test_trigger()
    await test_safe_reply()
    await test_internal_find_group_single_reply()
    await test_dispatcher_no_duplicate_reply()
    await test_full_mode_gate_does_not_eat_at_event()
    print("\n全部自检通过")


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

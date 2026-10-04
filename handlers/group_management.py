"""群组管理相关处理器"""
import re
import time
import aiohttp
import botpy
from botpy import BotAPI
from botpy.ext.command_util import Commands
from botpy.message import GroupMessage
from botpy.types.message import MarkdownPayload
from utils.network import get_tenant_access_token
from utils.reply import safe_reply
from config import FEISHU_APP_ID, FEISHU_APP_SECRET

_log = botpy.logging.get_logger()

# 飞书群表缓存：默认 @ 的流程里每次都要先搜一遍群，缓存一下免得把飞书打爆
_GROUPS_CACHE_TTL = 300
_groups_cache = {"at": 0.0, "groups": []}

# 针对 QQ 敏感词限制的替换表
_SENSITIVE_WORDS_MAP = {
    "ba": "Blue Archive",
    # 可以在这里添加更多敏感词映射
    # "敏感词（小写）": "替换词",
}


async def fetch_groups_from_feishu_cached(app_id: str, app_secret: str, ttl: int = _GROUPS_CACHE_TTL) -> list:
    """带 TTL 缓存的群表拉取（缓存为空/过期/上次为空时重新拉）"""
    now = time.monotonic()
    cached = _groups_cache["groups"]
    if cached and now - _groups_cache["at"] < ttl:
        return cached
    groups = await fetch_groups_from_feishu(app_id, app_secret)
    if groups:
        _groups_cache["groups"] = groups
        _groups_cache["at"] = now
    return groups


def clear_groups_cache():
    """清空群表缓存（测试/手动刷新用）"""
    _groups_cache["groups"] = []
    _groups_cache["at"] = 0.0


def _normalize_search_key(search_key: str) -> str:
    """敏感词替换（QQ 会拦截部分词）"""
    key = (search_key or "").strip()
    return _SENSITIVE_WORDS_MAP.get(key.lower(), key)


def is_trusted(group: dict) -> bool:
    """群是否「可信」

    飞书群表里 ``是否可信`` 为 false 的群（信息没核实过）一律不能往外发，
    所以：

    * 拉取时请求体里已经带了 ``是否可信 is true`` 的过滤条件；
    * 这里再兜一层 —— 群表快照、缓存、别的调用方塞进来的数据同样受保护。
    没有 ``trusted`` 字段的历史数据按可信处理（飞书那条过滤已经拦过了）。
    """
    return bool(group.get("trusted", True))


def match_groups(groups: list, search_key: str) -> list:
    """按群名/描述/群号子串匹配（忽略空格与大小写；只返回可信的群）"""
    key = _normalize_search_key(search_key)
    if not key:
        return []
    needle = key.replace(" ", "").lower()
    matched = []
    for group in groups:
        if not is_trusted(group):
            continue
        if (
            needle in group["group_name"].replace(" ", "").lower()
            or needle in group["description"].replace(" ", "").lower()
            or needle == group["group_id"]
        ):
            matched.append(group)
    return matched


def format_groups_markdown(matched: list, search_key: str, limit: int = 10) -> str:
    """把匹配到的群格式化成 markdown（internal_find_group 与路由共用）"""
    if not matched:
        reply = f"没有找到包含 '{_normalize_search_key(search_key)}' 的群组\n"
    else:
        reply = f"## 🔍 找到 {len(matched)} 个匹配的群组\n\n"
        for group in matched[:limit]:
            reply += (
                f"### 🏷️ {group['group_name']}\n\n"
                f"- 🆔 群号：**{group['group_id']}**\n"
                f"- 👥 人数：**{group['member_count']}/{group['max_member_count']}**\n"
                f"- 📝 描述：{group['description'][:50]}\n"
            )
            if group["url"]:
                clean_url = group["url"].replace("https://", "").replace("http://", "")
                new_url = f"https://mcskin.ecustvr.top/auth/qqbot/{clean_url}"
                reply += f"- 🔗 [加群链接]({new_url})\n"
            reply += "***\n\n"
        if len(matched) > limit:
            reply += f"📢 还有 **{len(matched)-limit}** 个结果未显示..."

    reply += "\n\n👉 有想添加的群聊？立即[填写表单](https://mcskin.ecustvr.top/auth/qqtj)"
    return reply


async def search_groups(search_key: str) -> dict:
    """只搜群、不回复。给「默认 @ 」的路由用：先搜一遍，再决定发不发。

    返回 {"ok": bool, "matched": [...], "total": int, "keyword": str, "error": str|None}
    """
    keyword = _normalize_search_key(search_key)
    result = {"ok": False, "matched": [], "total": 0, "keyword": keyword, "error": None}
    if not keyword:
        result["ok"] = True
        return result
    try:
        groups = await fetch_groups_from_feishu_cached(FEISHU_APP_ID, FEISHU_APP_SECRET)
    except Exception as e:  # noqa: BLE001
        _log.error(f"获取群组信息出错: {e}")
        result["error"] = str(e)
        return result
    if not groups:
        result["error"] = "群表为空或飞书接口异常"
        return result
    result["ok"] = True
    result["total"] = len(groups)
    result["matched"] = match_groups(groups, keyword)
    return result


async def fetch_groups_from_feishu(app_id: str, app_secret: str) -> list:
    """从飞书获取群组数据"""
    token = await get_tenant_access_token(app_id, app_secret)
    if not token:
        return []
    
    all_groups = []
    page_token = None
    has_more = True
    
    try:
        while has_more:
            url = "https://open.feishu.cn/open-apis/bitable/v1/apps/Y9HBbtQoxawALxs3XK8cOY9pn8g/tables/tblVq51wR2ZPVax4/records/search?page_size=100"
            if page_token:
                url += f"&page_token={page_token}"
            
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "sort": [{"field_name": "类别", "desc": False}],
                # 只取「是否可信 = true」的群：不可信的群不给群友
                "filter": {
                    "conjunction": "and",
                    "conditions": [{
                        "field_name": "是否可信",
                        "operator": "is",
                        "value": ["true"]
                    }]
                }
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload) as response:
                    data = await response.json()
                    if data.get("code") == 0:
                        for item in data["data"]["items"]:
                            fields = item["fields"]
                            
                            # 处理群号
                            group_id = str(fields.get("QQ群号", ""))
                            
                            # 处理加群链接
                            join_url = fields.get("加群链接", {}).get("link") if fields.get("加群链接") else None
                            
                            # 是否可信：请求体已经过滤过一次，这里再解析出来兜底
                            trusted = fields.get("是否可信")
                            if trusted is None:
                                trusted = True
                            elif not isinstance(trusted, bool):
                                trusted = str(trusted).strip().lower() in ("true", "1", "是")
                            if not trusted:
                                continue
                            
                            # 处理描述
                            description = "暂无描述"
                            if fields.get("描述"):
                                description = "".join(
                                    part["text"] for part in fields["描述"] 
                                    if part.get("type") == "text"
                                )
                            
                            # 处理群名称
                            group_name = f"群组({group_id})"
                            if fields.get("群名称"):
                                group_name = "".join(
                                    part["text"] for part in fields["群名称"]
                                    if part.get("type") == "text"
                                )
                            
                            # 处理群人数
                            member_count = 0
                            max_member_count = 0
                            if fields.get("群人数"):
                                count_text = "".join(
                                    part["text"] for part in fields["群人数"]
                                    if part.get("type") == "text"
                                )
                                match = re.search(r"(\d+)\s*\/\s*(\d+)", count_text)
                                if match:
                                    member_count = int(match.group(1))
                                    max_member_count = int(match.group(2))
                            
                            all_groups.append({
                                "group_id": group_id,
                                "group_name": group_name,
                                "description": description,
                                "member_count": member_count,
                                "max_member_count": max_member_count,
                                "url": join_url,
                                "trusted": True,
                            })
                        
                        has_more = data["data"].get("has_more", False)
                        page_token = data["data"].get("page_token")
                    else:
                        print(f"获取飞书数据失败: {data}")
                        break
    except Exception as e:
        print(f"获取群组信息出错: {e}")
    
    return all_groups


async def internal_find_group(api: BotAPI, message: GroupMessage, search_key: str):
    """内部群组查找函数：搜群 + 回复

    约定：**无论成功还是失败都只回复一次**，并且自身不抛异常。
    之前这里回复失败后会再回一条错误消息，两条消息用的是同一个 msg_id +
    msg_seq=1，第二条必定 40054005「消息被去重」，最后在 bot_client 里又回一次，
    形成「3 条接口报错 + 一段 traceback」。
    """
    result = await search_groups(search_key)

    if not result["ok"]:
        # 注意：message.reply 只接受关键字参数，之前写成位置参数会直接 TypeError
        await safe_reply(message, content="获取群组信息失败，请稍后再试")
        return

    try:
        markdown = MarkdownPayload(
            content=format_groups_markdown(result["matched"], result["keyword"])
        )
    except Exception as e:
        await safe_reply(message, content=f"❌ 查询群组信息时发生错误: {str(e)}")
        return

    await safe_reply(message, markdown=markdown, msg_type=2)


@Commands("/找群")
async def find_group(api: BotAPI, message: GroupMessage, params=None):
    search_key = "".join(params).strip().replace("群", "") if params else ""
    await internal_find_group(api, message, search_key)
    return True
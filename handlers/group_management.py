"""群组管理相关处理器"""
import re
import aiohttp
from botpy import BotAPI
from botpy.ext.command_util import Commands
from botpy.message import GroupMessage
from botpy.types.message import MarkdownPayload
from utils.network import get_tenant_access_token
from config import FEISHU_APP_ID, FEISHU_APP_SECRET


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
                                "url": join_url
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
    """内部群组查找函数"""
    try:
        groups = await fetch_groups_from_feishu(FEISHU_APP_ID, FEISHU_APP_SECRET)
        if not groups:
            await message.reply("获取群组信息失败，请稍后再试")
            return

        matched_groups = []

        # 针对QQ敏感词限制的处理
        # 敏感词映射字典，方便后续添加更多敏感词
        sensitive_words_map = {
            "ba": "Blue Archive",
            # 可以在这里添加更多敏感词映射
            # "敏感词（小写）": "替换词",
        }
        
        # 检查并替换敏感词
        search_key_lower = search_key.lower()
        if search_key_lower in sensitive_words_map:
            search_key = sensitive_words_map[search_key_lower]

        for group in groups:
            if (search_key.replace(" ", "").lower() in group["group_name"].replace(" ", "").lower() or 
                search_key.replace(" ", "").lower() in group["description"].replace(" ", "").lower() or
                search_key.replace(" ", "") == group["group_id"]):
                matched_groups.append(group)

        if not matched_groups:
            reply = f"没有找到包含 '{search_key}' 的群组\n"
        else:
            reply = f"## 🔍 找到 {len(matched_groups)} 个匹配的群组\n\n"
            for group in matched_groups[:10]:
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
            if len(matched_groups) > 10:
                reply += f"📢 还有 **{len(matched_groups)-10}** 个结果未显示..."
        
        reply += "\n\n👉 有想添加的群聊？立即[填写表单](https://mcskin.ecustvr.top/auth/qqtj)"
        markdown = MarkdownPayload(content=reply)
        await message.reply(markdown=markdown, msg_type=2)

    except Exception as e:
        await message.reply(content=f"❌ 查询群组信息时发生错误: {str(e)}")


@Commands("/找群")
async def find_group(api: BotAPI, message: GroupMessage, params=None):
    search_key = "".join(params).strip().replace("群", "") if params else ""
    await internal_find_group(api, message, search_key)
    return True
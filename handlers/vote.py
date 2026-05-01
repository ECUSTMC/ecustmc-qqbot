"""整合包投票处理器"""
import re
import aiohttp
from botpy import BotAPI
from botpy.ext.command_util import Commands
from botpy.message import GroupMessage, DirectMessage
from botpy.types.message import MarkdownPayload, KeyboardPayload
import config


async def fetch_vote_list():
    url = f"{config.MCVOTE_API_URL}/api.php?action=list"
    headers = {"Authorization": f"Bearer {config.MCVOTE_API_TOKEN}"}
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            if response.status == 200:
                data = await response.json()
                return data.get("packages", [])
            return None


async def fetch_current_package():
    url = f"{config.MCVOTE_API_URL}/api.php?action=current"
    headers = {"Authorization": f"Bearer {config.MCVOTE_API_TOKEN}"}
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            if response.status == 200:
                data = await response.json()
                return data.get("current") or data
            return None


async def submit_vote(package_id: int, vote_type: str, qq_id: str):
    url = f"{config.MCVOTE_API_URL}/api.php?action=vote"
    headers = {
        "Authorization": f"Bearer {config.MCVOTE_API_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "package_id": package_id,
        "vote_type": vote_type,
        "qq_id": qq_id
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload) as response:
            return await response.json(), response.status


async def add_package(name: str, link: str):
    url = f"{config.MCVOTE_API_URL}/api.php?action=add"
    headers = {
        "Authorization": f"Bearer {config.MCVOTE_API_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {"name": name, "link": link}
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload) as response:
            return await response.json(), response.status


def build_vote_keyboard(packages):
    rows = []
    for pkg in packages[:5]:
        pkg_id = pkg["id"]
        name = pkg["name"]
        short_name = name[:5] + "…" if len(name) > 5 else name
        rows.append({
            "buttons": [
                {
                    "id": f"support_{pkg_id}",
                    "render_data": {
                        "label": f"👍支持{short_name}",
                        "visited_label": f"👍支持{short_name}",
                        "style": 1
                    },
                    "action": {
                        "type": 1,
                        "permission": {"type": 2},
                        "data": f"vote_support_{pkg_id}",
                        "unsupport_tips": "暂不支持"
                    }
                },
                {
                    "id": f"oppose_{pkg_id}",
                    "render_data": {
                        "label": f"👎反对{short_name}",
                        "visited_label": f"👎反对{short_name}",
                        "style": 1
                    },
                    "action": {
                        "type": 1,
                        "permission": {"type": 2},
                        "data": f"vote_oppose_{pkg_id}",
                        "unsupport_tips": "暂不支持"
                    }
                }
            ]
        })
    return rows


@Commands("/vote")
async def query_vote(api: BotAPI, message, params=None):
    if not config.MCVOTE_API_URL or not config.MCVOTE_API_TOKEN:
        await message.reply(content="❌ 投票功能未配置")
        return True

    if not params:
        packages = await fetch_vote_list()
        if packages is None:
            await message.reply(content="❌ 获取投票列表失败，请稍后再试")
            return True
        if not packages:
            await message.reply(content="📋 当前没有活跃的整合包投票")
            return True

        md_lines = ["## 📋 整合包投票\n"]
        for i, pkg in enumerate(packages, 1):
            name = pkg["name"]
            link = pkg.get("link", "")
            proposer = pkg.get("proposer", {})
            proposer_name = proposer.get("nickname", "匿名") if proposer else "匿名"
            votes_up = pkg.get("votes_up", 0)
            votes_down = pkg.get("votes_down", 0)
            is_current = pkg.get("is_current", False)
            tag = " 🏆当前" if is_current else ""
            md_lines.append(f"**{i}. {name}**{tag}")
            md_lines.append(f"提议：{proposer_name} | 👍{votes_up} 👎{votes_down}")
            if link:
                safe_link = re.sub(r'^https?://', '', link)
                safe_link = f"https://mcskin.ecustvr.top/auth/qqbot/qm/{safe_link}"
                md_lines.append(f"[详情]({safe_link})")
            md_lines.append("")

        if len(packages) > 5:
            md_lines.append(f"*显示前5个整合包，共{len(packages)}个*")

        markdown = MarkdownPayload(content="\n".join(md_lines))
        keyboard = KeyboardPayload(content={"rows": build_vote_keyboard(packages)})
        await message.reply(markdown=markdown, keyboard=keyboard, msg_type=2)
    else:
        params = params.strip()
        if params.startswith("add "):
            content = params[4:].strip()
            url_match = re.search(r'https?://\S+', content)
            if url_match:
                link = url_match.group(0)
                name = content[:url_match.start()].strip()
            else:
                await message.reply(content="❌ 请提供整合包链接（需以 http:// 或 https:// 开头）")
                return True
            if not name:
                await message.reply(content="❌ 请提供整合包名称")
                return True
            result, status_code = await add_package(name, link)
            if status_code == 200 and result.get("success"):
                pkg_id = result.get("id", "")
                await message.reply(content=f"✅ 整合包「{name}」已添加成功！")
            else:
                error = result.get("error", "未知错误") if isinstance(result, dict) else "请求失败"
                await message.reply(content=f"❌ 添加失败：{error}")
        else:
            await message.reply(content="用法：\n/vote - 查看投票列表\n/vote add <名称> <链接> - 添加整合包")
    return True


async def handle_vote_interaction(api: BotAPI, button_data: str, user_openid: str):
    if button_data.startswith("vote_support_"):
        package_id = int(button_data[len("vote_support_"):])
        vote_type = "support"
    elif button_data.startswith("vote_oppose_"):
        package_id = int(button_data[len("vote_oppose_"):])
        vote_type = "oppose"
    else:
        return None

    result, status_code = await submit_vote(package_id, vote_type, user_openid)
    if status_code == 200 and result.get("success"):
        action = "支持" if vote_type == "support" else "反对"
        return f"## 🗳️ 投票成功\n\n你已**{action}**该整合包"
    elif status_code == 409:
        return "## ⚠️ 投票失败\n\n你已经对此整合包投过票了"
    else:
        error = result.get("error", "未知错误") if isinstance(result, dict) else "请求失败"
        return f"## ❌ 投票失败\n\n{error}"

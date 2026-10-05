"""服务器状态查询处理器"""
import time
import aiohttp
import botpy
from botpy import BotAPI
from botpy.ext.command_util import Commands
from botpy.message import GroupMessage
from botpy.types.message import MarkdownPayload
from config import MC_SERVERS, MC_MCSRVSTAT_SERVERS
import r
from utils.permissions import require_owner_or_group_admin
from utils.qq_text import qq_address, qq_display

_log = botpy.logging.get_logger()


def _current_servers() -> list:
    """当前配置的服务器地址列表（去空白、去空项）"""
    return [s.strip() for s in (r.mc_servers or "").split(",") if s.strip()]


def _resolve_address(text: str, current_servers: list) -> str:
    """把用户输入解析成真实地址

    * 原文命中列表 → 原样返回（真实地址带 ``-`` 的情况优先）；
    * **输入里有点号** → 认为用户给的就是真实地址，原样返回（不动它）；
    * 否则按 :func:`qq_address` 还原显示串（``mc-ecustvr-top`` →
      ``mc.ecustvr.top``、``my--server-example-com`` → ``my-server.example.com``）。

    最后一条有个天然歧义：不带点号又带 ``-`` 的输入（``my-server``）会被还原成
    ``my.server``。真要在这种环境下加一个「单段主机名 + 短横线」的地址，
    请直接写带点号的完整地址。
    """
    if text in current_servers or "." in text:
        return text
    return qq_address(text) or text


@Commands("/服务器状态")
async def query_ecustmc_server(api: BotAPI, message: GroupMessage, params=None):
    server_list = r.mc_servers.split(",")
    mcsrvstat_servers = r.mc_mcsrvstat_servers.split(",") if r.mc_mcsrvstat_servers else []

    reply_content = ""
    
    async with aiohttp.ClientSession() as session:
        for server in server_list:
            server = server.strip()
            if not server:
                continue

            if server in mcsrvstat_servers:
                headers = {'User-Agent': 'ecustmc-qqbot/1.0 (https://cnb.cool/ecustmc/ecustmc-qqbot)'}
                async with session.get(f"https://api.mcsrvstat.us/2/{server}", headers=headers) as res:
                    server_info = await res.json()
                    server = qq_display(server)
                    if server_info.get('online'):
                        players_online = server_info['players']['online']
                        players_max = server_info['players']['max']
                        description = server_info['motd']['raw'][0]
                        sample_players = server_info.get('players', {}).get('list', [])
                        version = server_info.get('version', 'N/A')

                        timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
                        
                        # 拼接每个服务器的状态信息
                        reply_content += (
                            f"### 🖥️ {server}\n\n"
                            f"> {description}\n\n"
                            f"- 在线玩家：**{players_online}/{players_max}**\n"
                            f"- 版本：**{version}**\n"
                            f"- 查询时间：{timestamp}\n\n"
                        )
                        
                        # 如果有在线玩家，显示他们的名字
                        if players_online > 0 and sample_players:
                            reply_content += "**正在游玩：**\n"
                            for player in sample_players:
                                player_name = player
                                reply_content += f"- {player_name}\n"
                            reply_content += "\n"
                        reply_content += "***\n"

                    else:
                        reply_content += (
                            f"\n查询 {server} 服务器信息失败，1分钟后再试\n"
                            f"状态码: {res.status}\n"
                        )
            else:
                async with session.post(f"https://mc.sjtu.cn/custom/serverlist/?query={server}") as res:
                    result = await res.json()
                    if res.ok:
                        server_info = result
                        server = qq_display(server)
                        description_raw = server_info.get('description_raw', {})
                        if isinstance(description_raw, str):
                            description_raw = {"text": description_raw}
                        description = description_raw.get('text', description_raw.get('translate', server_info.get('description', {}).get('text', '无描述')))
                        if "服务器已离线..." in description:
                            description = description.replace("...", "或查询失败")
                        players_max = server_info.get('players', {}).get('max', '未知')
                        players_online = server_info.get('players', {}).get('online', '未知')
                        sample_players = server_info.get('players', {}).get('sample', [])
                        version = server_info.get('version', '未知')

                        timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
                        
                        # 拼接每个服务器的状态信息
                        reply_content += (
                            f"### 🖥️ {server}\n\n"
                            f"> {description}\n\n"
                            f"- 在线玩家：**{players_online}/{players_max}**\n"
                            f"- 版本：**{version}**\n"
                            f"- 查询时间：{timestamp}\n\n"
                        )
                        
                        # 如果有在线玩家，显示他们的名字
                        if players_online > 0 and sample_players:
                            reply_content += "**正在游玩：**\n"
                            for player in sample_players:
                                player_name = player.get('name', '未知')
                                reply_content += f"- {player_name}\n"
                            reply_content += "\n"
                        reply_content += "***\n"

                    else:
                        reply_content += (
                            f"\n查询 {server} 服务器信息失败\n"
                            f"状态码: {res.status}\n"
                        )
    
    # 发送回复
    if not reply_content:
        reply_content = "未查询到任何服务器信息"
    
    reply_content += (
        '\n\n⚠️ 受 QQ 限制，地址里的 "." 显示成 "-"、原有的 "-" 显示成 "--"。\n'
        '可以直接复制上面的地址交给 `/添加服务器` / `/移除服务器`，机器人会自动还原。'
    )
    
    # 添加标题
    if reply_content.startswith("###"):
        reply_content = "## 🎮 MC 服务器状态\n\n" + reply_content
    
    markdown = MarkdownPayload(content=reply_content)
    await message.reply(
        markdown=markdown,
        msg_type=2
    )
    
    return True


@Commands("/添加服务器")
async def add_server(api: BotAPI, message: GroupMessage, params=None):
    """添加 MC 服务器（仅机器人管理员或本群群主 / 管理员，会改写 .env）"""
    if not await require_owner_or_group_admin(message, "/添加服务器"):
        return True

    if params:
        new_server = ''.join(params).strip()

        # 支持直接粘贴 /服务器状态 里的显示串（"." 显示成 "-"、原有的 "-" 显示成 "--"）
        current_servers = _current_servers()
        new_server = _resolve_address(new_server, current_servers) or new_server

        # 检查服务器是否已经存在
        if new_server in current_servers:
            await message.reply(content=f"服务器已存在")
            return True

        # 添加新服务器并更新 .env 文件
        current_servers.append(new_server)
        updated_servers = ','.join(current_servers)
        r.update_env_variable("MC_SERVERS", updated_servers)

        # 更新 r.py 中的 mc_servers
        r.mc_servers = updated_servers

        await message.reply(content=f"服务器 {qq_display(new_server)} 已添加")
    else:
        await message.reply(content="⚠️ 请提供要添加的服务器地址！")
    
    return True


@Commands("/移除服务器")
async def remove_server(api: BotAPI, message: GroupMessage, params=None):
    """移除 MC 服务器（仅机器人管理员或本群群主 / 管理员，会改写 .env）

    支持两种输入：

    * 真实地址（``mc.ecustvr.top``）—— 精确匹配；
    * 直接复制 ``/服务器状态`` 里的显示串（``mc-ecustvr-top``，
      含 ``--`` 的也能还原）—— 先用原文试一次，再用 :func:`qq_address` 还原后匹配。
    """
    if not await require_owner_or_group_admin(message, "/移除服务器"):
        return True

    if params:
        server_to_remove = ''.join(params).strip()

        # 获取当前服务器列表
        current_servers = _current_servers()

        # 先按原样匹配（真实地址带 "-" 的情况），否则按显示串还原后匹配
        candidate = _resolve_address(server_to_remove, current_servers)
        target = candidate if candidate in current_servers else None

        # 检查服务器是否存在
        if target is None:
            await message.reply(
                content=f"服务器不存在：{qq_display(server_to_remove)}\n\n"
                        f"当前列表：\n" + "\n".join(f"- {qq_display(s)}" for s in current_servers)
            )
            return True

        # 删除服务器并更新 .env 文件
        current_servers.remove(target)
        updated_servers = ','.join(current_servers)
        r.update_env_variable("MC_SERVERS", updated_servers)

        # 更新 r.py 中的 mc_servers
        r.mc_servers = updated_servers

        await message.reply(content=f"服务器 {qq_display(target)} 已删除")
    else:
        await message.reply(content="⚠️ 请提供要删除的服务器地址！")
    
    return True


@Commands("/status")
async def query_server_status(api: BotAPI, message: GroupMessage, params=None):
    # API 地址
    api_url = "http://mcsm.ecustvr.top/"  # 替换为实际 API 地址

    try:
        # 获取服务器状态数据（使用异步请求）
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url) as resp:
                if resp.status != 200:
                    await message.reply(content=f"无法获取服务器状态，状态码: {resp.status}")
                    # 已回复过，必须返回 True，否则会继续走兜底重复回复同一 msg_id
                    return True

                data = await resp.json()

        if data.get("status") != 200:
            await message.reply(content="服务器返回了非正常状态的数据")
            return True

        # 提取所需数据
        system_info = data["data"][0]["system"]

        # 系统信息展示
        uptime = system_info["uptime"] / 3600
        loadavg = system_info["loadavg"]
        total_mem = system_info["totalmem"] / (1024 ** 3)  # 转换为 GB
        free_mem = system_info["freemem"] / (1024 ** 3)  # 转换为 GB
        cpu_usage_percent = system_info["cpuUsage"] * 100
        mem_usage_percent = system_info["memUsage"] * 100

        # 构建信息内容
        info_message = (
            f"## 📊 服务器状态\n\n"
            f"- 运行时间：**{uptime:.2f}** 小时\n"
            f"- 近期负载：**{loadavg}**\n"
            f"- 总内存：**{total_mem:.2f}** GB\n"
            f"- 可用内存：**{free_mem:.2f}** GB\n"
            f"- CPU 使用率：**{cpu_usage_percent:.2f}%**\n"
            f"- 内存使用率：**{mem_usage_percent:.2f}%**"
        )

        # 回复状态信息
        markdown = MarkdownPayload(content=info_message)
        await message.reply(markdown=markdown, msg_type=2)

    except Exception as e:
        await message.reply(content=f"查询服务器状态时发生错误")
        _log.error(f"查询服务器状态时发生错误: {e}")

    return True
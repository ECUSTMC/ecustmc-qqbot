"""服务器状态查询处理器"""
import time
import aiohttp
import requests
from botpy import BotAPI
from botpy.ext.command_util import Commands
from botpy.message import GroupMessage
from config import MC_SERVERS
import r


@Commands("/服务器状态")
async def query_ecustmc_server(api: BotAPI, message: GroupMessage, params=None):
    # 假设 r.mc_servers 包含了服务器列表，用逗号分隔
    server_list = MC_SERVERS.split(",")

    reply_content = ""
    
    # 遍历每个服务器并查询状态
    async with aiohttp.ClientSession() as session:
        for server in server_list:
            server = server.strip()  # 去除两端的空格
            if not server:
                continue

            if server == "mcmod.ecustvr.top":
                headers = {'User-Agent': 'ecustmc-qqbot/1.0 (https://cnb.cool/ecustmc/ecustmc-qqbot)'}
                async with session.get(f"https://api.mcsrvstat.us/2/{server}", headers=headers) as res:
                    server_info = await res.json()
                    server=server.replace('.', '-')
                    if server_info.get('online'):
                        players_online = server_info['players']['online']
                        players_max = server_info['players']['max']
                        description = server_info['motd']['raw'][0]
                        sample_players = server_info.get('players', {}).get('list', [])
                        version = server_info.get('version', 'N/A')

                        timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
                        
                        # 拼接每个服务器的状态信息
                        reply_content += (
                            f"\n"
                            f"服务器地址: {server}\n"
                            f"描述: {description}\n"
                            f"在线玩家: {players_online}/{players_max}\n"
                            f"版本: {version}\n"
                            f"查询时间: {timestamp}\n"
                        )
                        
                        # 如果有在线玩家，显示他们的名字
                        if players_online > 0 and sample_players:
                            reply_content += "正在游玩:\n"
                            for player in sample_players:
                                player_name = player
                                reply_content += f"- {player_name}\n"
                        reply_content += "-----------------------------\n"

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
                        server=server.replace('.', '-')
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
                            f"\n"
                            f"服务器地址: {server}\n"
                            f"描述: {description}\n"
                            f"在线玩家: {players_online}/{players_max}\n"
                            f"版本: {version}\n"
                            f"查询时间: {timestamp}\n"
                        )
                        
                        # 如果有在线玩家，显示他们的名字
                        if players_online > 0 and sample_players:
                            reply_content += "正在游玩:\n"
                            for player in sample_players:
                                player_name = player.get('name', '未知')
                                reply_content += f"- {player_name}\n"
                        reply_content += "-----------------------------\n"

                    else:
                        reply_content += (
                            f"\n查询 {server} 服务器信息失败\n"
                            f"状态码: {res.status}\n"
                        )
    
    # 发送回复
    if not reply_content:
        reply_content = "未查询到任何服务器信息"
    
    reply_content += '⚠️由于QQAPI限制，服务器地址中间的"-"请自行换成"."！'
    
    await message.reply(
        content=reply_content,
        msg_type=0
    )
    
    return True


@Commands("/添加服务器")
async def add_server(api: BotAPI, message: GroupMessage, params=None):
    if params:
        new_server = ''.join(params).strip()

        # 获取当前服务器列表
        current_servers = MC_SERVERS.split(",")

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
        new_server = new_server.replace('.', '-')

        await message.reply(content=f"服务器 {new_server} 已添加")
    else:
        await message.reply(content="⚠️ 请提供要添加的服务器地址！")
    
    return True


@Commands("/移除服务器")
async def remove_server(api: BotAPI, message: GroupMessage, params=None):
    if params:
        server_to_remove = ''.join(params).strip()

        # 获取当前服务器列表
        current_servers = MC_SERVERS.split(",")

        # 检查服务器是否存在
        if server_to_remove not in current_servers:
            await message.reply(content=f"服务器不存在")
            return True

        # 删除服务器并更新 .env 文件
        current_servers.remove(server_to_remove)
        updated_servers = ','.join(current_servers)
        r.update_env_variable("MC_SERVERS", updated_servers)

        # 更新 r.py 中的 mc_servers
        r.mc_servers = updated_servers
        server_to_remove = server_to_remove.replace('.','-')

        await message.reply(content=f"服务器 {server_to_remove} 已删除")
    else:
        await message.reply(content="⚠️ 请提供要删除的服务器地址！")
    
    return True


@Commands("/status")
async def query_server_status(api: BotAPI, message: GroupMessage, params=None):
    # API 地址
    api_url = "http://mcsm.ecustvr.top/"  # 替换为实际 API 地址

    try:
        # 获取服务器状态数据
        response = requests.get(api_url)
        if response.status_code != 200:
            await message.reply(content=f"无法获取服务器状态，状态码: {response.status_code}")
            return

        data = response.json()
        if data.get("status") != 200:
            await message.reply(content="服务器返回了非正常状态的数据")
            return

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
            f"服务器状态:\n"
            f"运行时间: {uptime:.2f} 小时\n"
            f"近期负载: {loadavg}\n"
            f"总内存: {total_mem:.2f} GB\n"
            f"可用内存: {free_mem:.2f} GB\n"
            f"CPU 使用率: {cpu_usage_percent:.2f}%\n"
            f"内存使用率: {mem_usage_percent:.2f}%"
        )

        # 回复状态信息
        await message.reply(content=info_message)

    except Exception as e:
        await message.reply(content=f"查询服务器状态时发生错误: {str(e)}")

    return True
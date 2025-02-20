import asyncio

import botpy
from botpy import BotAPI
from botpy.ext.command_util import Commands
from botpy.manage import GroupManageEvent
from botpy.message import GroupMessage
import IPy
import time
import sqlite3
from datetime import datetime
import aiohttp
import random
import requests
import json
from mcrcon import MCRcon
from openai import OpenAI
import re
import socket

import r

_log = botpy.logging.get_logger()

session: aiohttp.ClientSession


async def on_ecustmc_backend_error(message: GroupMessage):
    await message.reply(content=f"服务无响应，请稍后再试，若此问题依然存在，请联系机器人管理员")


@Commands("/校园天气")
async def query_weather(api: BotAPI, message: GroupMessage, params=None):
    async with aiohttp.ClientSession() as session:
        fx_res, xh_res = await asyncio.gather(
            session.get(f"https://restapi.amap.com/v3/weather/weatherInfo?city=310120&key=" + r.weather_api_token),
            session.get(f"https://restapi.amap.com/v3/weather/weatherInfo?city=310104&key=" + r.weather_api_token)
        )

        if fx_res.ok:
            fx_result = await fx_res.json()
            xh_result = await xh_res.json()
            if fx_result.get("status") == "1" and "lives" in fx_result and len(fx_result["lives"]) > 0:
                fx_live_data = fx_result["lives"][0]
                xh_live_data = xh_result["lives"][0]

                fx_weather = fx_live_data.get("weather", "N/A")
                fx_temperature = fx_live_data.get("temperature", "N/A")
                fx_winddirection = fx_live_data.get("winddirection", "N/A")
                fx_windpower = fx_live_data.get("windpower", "N/A")
                fx_humidity = fx_live_data.get("humidity", "N/A")

                xh_weather = xh_live_data.get("weather", "N/A")
                xh_temperature = xh_live_data.get("temperature", "N/A")
                xh_winddirection = xh_live_data.get("winddirection", "N/A")
                xh_windpower = xh_live_data.get("windpower", "N/A")
                xh_humidity = xh_live_data.get("humidity", "N/A")

                reporttime = fx_live_data.get("reporttime", "N/A")

                reply_content = (
                    f"\n"
                    f"奉贤校区：\n"
                    f"天气：{fx_weather}\n"
                    f"温度：{fx_temperature}\n"
                    f"风向：{fx_winddirection}\n"
                    f"风力：{fx_windpower}\n"
                    f"湿度：{fx_humidity}\n"
                    f"\n"
                    f"徐汇校区：\n"
                    f"天气：{xh_weather}\n"
                    f"温度：{xh_temperature}\n"
                    f"风向：{xh_winddirection}\n"
                    f"风力：{xh_windpower}\n"
                    f"湿度：{xh_humidity}\n"
                    f"更新时间：{reporttime}"
                )

                await message.reply(content=reply_content)
            else:
                error_content = "查询失败，响应数据不正确"
                await message.reply(content=error_content)
        else:
            error_content = "查询失败，无法连接到天气服务"
            await message.reply(content=error_content)
        return True


@Commands("/服务器状态")
async def query_ecustmc_server(api: BotAPI, message: GroupMessage, params=None):
    # 假设 r.mc_servers 包含了服务器列表，用逗号分隔
    server_list = r.mc_servers.split(",")

    reply_content = ""
    
    # 遍历每个服务器并查询状态
    for server in server_list:
        server = server.strip()  # 去除两端的空格
        if not server:
            continue
        
        async with session.post(f"https://mc.sjtu.cn/custom/serverlist/?query={server}") as res:
            result = await res.json()
            if res.ok:
                server_info = result
                server=server.replace('.', '-')
                description_raw = server_info.get('description_raw', {})
                description = description_raw.get('text', description_raw.get('translate', server_info.get('description', {}).get('text', '无描述')))
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
    
    reply_content += "⚠️由于QQAPI限制，服务器地址中间的“-”请自行换成“.”！"
    
    await message.reply(
        content=reply_content,
        msg_type=0
    )
    
    return True


@Commands("/一言")
async def daily_word(api: BotAPI, message: GroupMessage, params=None):
    daily_word = f"https://v1.hitokoto.cn/"
    async with session.post(daily_word) as res:
        result = await res.json()
        if res.ok:
            content = result['hitokoto']
            author_from = result['from']
            author = result['from_who']
            if author != author_from and author != None:
                author_from = f"{author}《{author_from}》"
            reply_content = (
                f"\n"
                f"{content}"
                f"\n"
                f"——{author_from}"
            )

            await message.reply(content=reply_content)
        else:
            error_content = (
                f"获取一言失败"
            )
            await message.reply(content=error_content)
        return True


@Commands("/今日黄历")
async def daily_huangli(api: BotAPI, message: GroupMessage, params=None):
    # 获取当前日期
    current_date = time.strftime("%Y%m%d", time.localtime())
    
    # 构建 API 请求 URL
    daily_huangli = f"https://www.mxnzp.com/api/holiday/single/{current_date}?ignoreHoliday=false&app_id={r.api_app_id}&app_secret={r.api_app_secret}"
    
    # 发送请求
    async with aiohttp.ClientSession() as session:
        async with session.get(daily_huangli) as res:
            # 解析响应 JSON 数据
            result = await res.json()

            if res.ok and result['code'] == 1:  # 检查响应是否成功
                # 获取所需的黄历内容
                data = result['data']
                date = data.get('date', '未知')
                type_des = data.get('typeDes', '未知')
                chinese_zodiac = data.get('chineseZodiac', '未知')
                lunar_calendar = data.get('lunarCalendar', '未知')
                suit = data.get('suit', '无宜')
                avoid = data.get('avoid', '无忌')
                constellation = data.get('constellation', '未知')
                solar_terms = data.get('solarTerms', '未知')

                # 拼接黄历内容
                reply_content = (
                    f"\n"
                    f"📅 日期: {date}\n"
                    f"🀄 农历: {lunar_calendar}\n"
                    f"💫 星座: {constellation}\n"
                    f"🌞 节气: {solar_terms}\n"
                    f"🐉 生肖: {chinese_zodiac}\n"
                    f"📌 类型: {type_des}\n"
                    f"✅ 宜: {suit}\n"
                    f"❌ 忌: {avoid}\n"
                )

                # 发送回复
                await message.reply(content=reply_content)
            else:
                # 错误处理
                await message.reply(content="获取黄历失败")
                
    return True


@Commands("/今日运势")
async def jrys(api: BotAPI, message: GroupMessage, params=None):
    conn = sqlite3.connect('user_numbers.db')
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_numbers (
            user_id TEXT PRIMARY KEY,
            random_number INTEGER,
            number INTEGER,
            date TEXT
        )
    ''')
    conn.commit()

    with open('jrys.json', 'r', encoding='utf-8') as file:
        jrys_data = json.load(file)

    def get_fortune_number(lucky_star):
        star_count = lucky_star.count('★')
        if star_count == 0:
            return random.randint(0, 10)
        elif star_count == 1:
            return random.randint(5, 15)
        elif star_count == 2:
            return random.randint(10, 25)
        elif star_count == 3:
            return random.randint(25, 40)
        elif star_count == 4:
            return random.randint(40, 55)
        elif star_count == 5:
            return random.randint(55, 70)
        elif star_count == 6:
            return random.randint(70, 85)
        elif star_count == 7:
            return random.randint(85, 100)
        else:
            return None

    def get_user_number(user):
        today_date = datetime.now().strftime('%Y-%m-%d')

        cursor.execute('SELECT random_number, number FROM user_numbers WHERE user_id = ? AND date = ?',
                       (user, today_date))
        row = cursor.fetchone()

        if row:
            random_number = row[0]
            number = row[1]
            fortune_data = jrys_data[str(random_number)][0]
        else:
            while True:
                random_number = random.randint(1, 1433)
                fortune_data = jrys_data.get(str(random_number))

                if fortune_data:
                    fortune_data = fortune_data[0]
                    lucky_star = fortune_data['luckyStar']
                    number = get_fortune_number(lucky_star)

                    if number is not None:
                        break

            cursor.execute('''
                INSERT OR REPLACE INTO user_numbers (user_id, random_number, number, date) 
                VALUES (?, ?, ?, ?)
            ''', (user, random_number, number, today_date))
            conn.commit()

        return random_number, number, fortune_data

    user = f"{message.author.member_openid}"
    random_number, assigned_number, fortune_data = get_user_number(user)

    reply = (
        f"\n"
        f"今日运势：{fortune_data['fortuneSummary']}\n"
        f"幸运星象：{fortune_data['luckyStar']}\n"
        f"运势评述：{fortune_data['signText']}\n"
        f"评述解读：{fortune_data['unSignText']}"
    )

    await message.reply(content=reply)
    return True


@Commands("/今日人品")
async def jrrp(api: BotAPI, message: GroupMessage, params=None):
    conn = sqlite3.connect('user_numbers.db')
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_numbers (
            user_id TEXT PRIMARY KEY,
            random_number INTEGER,
            number INTEGER,
            date TEXT
        )
    ''')
    conn.commit()

    with open('jrys.json', 'r', encoding='utf-8') as file:
        jrys_data = json.load(file)

    def get_fortune_number(lucky_star):
        star_count = lucky_star.count('★')
        if star_count == 0:
            return random.randint(0, 10)
        elif star_count == 1:
            return random.randint(5, 15)
        elif star_count == 2:
            return random.randint(10, 25)
        elif star_count == 3:
            return random.randint(25, 40)
        elif star_count == 4:
            return random.randint(40, 55)
        elif star_count == 5:
            return random.randint(55, 70)
        elif star_count == 6:
            return random.randint(70, 85)
        elif star_count == 7:
            return random.randint(85, 100)
        else:
            return None

    def GetRangeDescription(score:int) -> str :
        if score==0:
            return "这运气也太差了吧？？？该不会是。。。。"
        if score==66:
            return "恭喜哦，抽到了隐藏彩蛋，六六大顺，666666666"
        if score==88:
            return "恭喜哦，抽到了隐藏彩蛋，发发发发，888888888"
        if score==69:
            return "这是什么意思啊，69696969696969696，哈哈哈哈哈哈哈哈哈"
        if score==100:
            return ""
        
        if score>0 and score<10:
            return "好烂的运气啊，大概率你今天买泡面没调料没叉子，点外卖没餐具。"
        if score>=10 and score<20:
            return "好烂的运气啊，大概率你今天买泡面没调料没叉子，点外卖没餐具。"
        if score>=20 and score<30:
            return "也许今天更适合摆烂。"
        if score>=30 and score<40:
            return "运气一般般啊，平平淡淡没什么新奇。"
        if score>=40 and score<50:
            return "运气不好不差，钻石矿可能比较难挖到。"
        if score>=50 and score<60:
            return "运气处于正态分布的中部，今天适合玩MC服。"
        if score>=60 and score<70:
            return "运气不好不差，今天就别开箱子了。"
        if score>=70 and score<80:
            return "今天你将会拥有非凡的一天。"
        if score>=80 and score<90:
            return "运气还不错，看起来一切都很顺利。"
        if score>=90 and score<100:
            return "运气真不错，今天适合抽卡。"

    def get_user_number(user):
        today_date = datetime.now().strftime('%Y-%m-%d')

        cursor.execute('SELECT random_number, number FROM user_numbers WHERE user_id = ? AND date = ?',
                       (user, today_date))
        row = cursor.fetchone()

        if row:
            random_number = row[0]
            number = row[1]
            fortune_data = jrys_data[str(random_number)][0]
        else:
            while True:
                random_number = random.randint(1, 100)
                fortune_data = jrys_data.get(str(random_number))

                if fortune_data:
                    fortune_data = fortune_data[0]
                    lucky_star = fortune_data['luckyStar']
                    number = get_fortune_number(lucky_star)

                    if number is not None:
                        break

            cursor.execute('''
                INSERT OR REPLACE INTO user_numbers (user_id, random_number, number, date) 
                VALUES (?, ?, ?, ?)
            ''', (user, random_number, number, today_date))
            conn.commit()

        return number

    user = f"{message.author.member_openid}"
    assigned_number = get_user_number(user)

    reply = f"今日人品值：{assigned_number}，{GetRangeDescription(int(assigned_number))}"

    await message.reply(content=reply)
    return True

import urllib.parse

@Commands("/wiki")
async def wiki(api: BotAPI, message: GroupMessage, params=None):
    if params:
        # 获取指令后的关键字
        query = ''.join(params)
        # 对查询关键词进行URL编码
        encoded_query = urllib.parse.quote(query)
        # 生成Wiki链接
        wiki_link = f"https://mc.ecustvr.top/wiki/{encoded_query}"
        
        reply_content = f"\n📚 你可以查看相关信息： \n🔗点击访问Wiki：{wiki_link}"
        
        await message.reply(content=reply_content)
    else:
        await message.reply(content="⚠️ 请提供要查询的Wiki页面关键字！例如 /wiki 门")
    
    return True

@Commands("/添加服务器")
async def add_server(api: BotAPI, message: GroupMessage, params=None):
    if params:
        new_server = ''.join(params).strip()

        # 获取当前服务器列表
        current_servers = r.mc_servers.split(",")

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
        current_servers = r.mc_servers.split(",")

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

@Commands("/塔罗牌")
async def query_tarot(api: BotAPI, message: GroupMessage, params=None):
    # 加载塔罗牌数据
    with open('Tarots.json', 'r', encoding='utf-8') as file:
        tarots = json.load(file)

    # 从塔罗牌列表中随机选择一张塔罗牌
    card_number = random.choice(list(tarots.keys()))
    tarot_card = tarots[card_number]
    
    # 获取塔罗牌信息
    name = tarot_card['name']
    description = tarot_card['info']['description']
    reverse_description = tarot_card['info']['reverseDescription']
    img_url = "http://www.ecustvr.top/"
    img_url += tarot_card['info']['imgUrl']

    # 随机决定正位还是逆位
    is_reverse = random.choice([True, False])
    if is_reverse:
        description_to_use = f"逆位：{reverse_description}"
    else:
        description_to_use = f"正位：{description}"

    # 上传图片
    uploadmedia = await api.post_group_file(
        group_openid=message.group_openid,
        file_type=1,
        url=img_url
    )

    # 构建回复内容
    reply_content = (
        f"\n"
        f"塔罗牌：{name}\n"
        f"{description_to_use}"
    )

    # 发送消息
    await message.reply(
        content=reply_content,
        msg_type=7,
        media=uploadmedia
    )

    return True

@Commands("vv")
async def query_vv(api: BotAPI, message: GroupMessage, params=None):
    # 如果没有提供查询参数，读取vv.txt文件获取表情名
    if not params:
        with open('vv.txt', 'r', encoding='utf-8') as file:
            emote_list = file.readlines()
        emote_name = random.choice(emote_list).strip()
    else:
        # 有查询参数，构建请求负载
        query = params  # 例如，"复旦大学"
        encoded_query = urllib.parse.quote(query)  # 对查询参数进行URL编码

        # 发起POST请求
        payload = {
            "query": query,
            "amount": 5
        }

        async with aiohttp.ClientSession() as session:
            url = f'https://api.xy0v0.top/search?q={encoded_query}&n=5'
            async with session.post(url, json=payload) as response:
                # 解析返回的JSON数据
                emotes = await response.json()
                emote_name = random.choice(emotes)  # 从返回的列表中随机选择一个表情包文件名

    # 拼接完整的URL
    encoded_emote_name = urllib.parse.quote(emote_name)
    emote_url = f"https://cn-sy1.rains3.com/clouddisk/clouddisk/images/{encoded_emote_name}"

    # 上传表情包图片
    uploadmedia = await api.post_group_file(
        group_openid=message.group_openid,
        file_type=1,
        url=emote_url
    )

    # 构建回复内容
    reply_content = (
        f"\n"
        f"{emote_name.rstrip('.png')}\n"
    )

    # 发送消息
    await message.reply(
        content=reply_content,
        msg_type=7,
        media=uploadmedia
    )

    return True

@Commands("/求签")
async def query_divinatory_symbol(api: BotAPI, message: GroupMessage, params=None):
    # 加载卦象数据
    with open('DivinatorySymbols.json', 'r', encoding='utf-8') as file:
        divinatory_symbols = json.load(file)
        
    # 从卦象列表中随机选择一个卦象
    symbol_number = random.choice(list(divinatory_symbols.keys()))
    divinatory_symbol = divinatory_symbols[symbol_number]
    
    # 获取卦象信息
    name = divinatory_symbol['name']
    description = divinatory_symbol['info']['description']
    level = divinatory_symbol['info']['level']

    # 构建回复内容
    reply_content = (
        f"\n"
        f"卦象: {name}\n"
        f"等级: {level}\n"
        f"解读: \n{description}"
    )

    # 发送消息
    await message.reply(content=reply_content)

    return True

@Commands("/帮助")
async def help(api: BotAPI, message: GroupMessage, params=None):
    help_content = (
        "\n👋 欢迎新人！\n"
        "为了享受更好的游戏体验，请先注册皮肤站账号。\n"
        "🔗 访问链接： https://mcskin.ecustvr.top/auth/register\n"
        "通过这个站点，你可以自定义和上传你的皮肤，使用联合认证账号登录游戏，便可进入使用 Union 联合认证的其他高校的 Minecraft 服务器游玩，或登录到支持 Union OAuth 登录的网站。\n"
        "更多关于游戏、启动器及账号配置等，欢迎访问 🔗萌新指南：https://mc.ecustvr.top/tutorial/\n"
        "更多关于bot指令的帮助，欢迎访问 🔗QQBot：https://mc.ecustvr.top/qqbot/，祝游戏愉快！"
    )
    
    await message.reply(content=help_content)
    return True

@Commands("/ip")
async def query_ip_info(api: BotAPI, message: GroupMessage, params=None):
    ip = "".join(params).strip() if params else None
    # 检查是否是 IPv4 地址
    def is_ipv4(ip):
        pattern = re.compile(r'^((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$')
        return pattern.match(ip) is not None
    def checkip(address):
        try:
            version = IPy.IP(address).version()
            if version == 4 or version == 6:
                return True
            else:
                return False
        except Exception as e:
            return False
        
    def resolve_domain(domain):
        try:
            # 获取所有地址信息
            addresses = socket.getaddrinfo(domain, None)
            # 提取 IP 地址
            ip_addresses = [addr[4][0] for addr in addresses]
            return ip_addresses[0]
        except socket.gaierror:
            return None
    
    if not checkip(ip):
        ip = resolve_domain(ip)

    try:
        if not checkip(ip):
            model_response = "输入的 IP地址/域名 格式不正确，请输入有效的 IPv4 或 IPv6 地址。"
            
        elif is_ipv4(ip):
            # 如果是 IPv4 地址，调用第一个接口
            api_url = f"https://ip.ecust.icu/find?ip={ip}"
            response = requests.get(api_url)
            if response.status_code == 200:
                result = response.json()
                if result.get("code") == 200:
                    query = result["data"]["query"]
                    isp = query.get("isp", "未知ISP")
                    locale = query.get("locale", "未知地区")
                    model_response = f"IPv4 地址 {ip} 的查询结果：\nISP: {isp}\n地区: {locale}\nPowered by Eric"
                else:
                    model_response = f"查询 IPv4 地址 {ip} 失败：{result.get('msg', '未知错误')}"
            else:
                model_response = f"调用 IPv4 查询接口失败，状态码: {response.status_code}"

        else:
            # 如果是 IPv6 地址，调用第二个接口
            api_url = f"https://ip.zxinc.org/api.php?type=json&ip={ip}"
            response = requests.get(api_url)
            if response.status_code == 200:
                result = response.json()
                if result.get("code") == 0:
                    location = result["data"].get("location", "未知地区")
                    model_response = f"IPv6 地址 {ip} 的查询结果：\n位置: {location}"
                else:
                    model_response = f"查询 IPv6 地址 {ip} 失败：{result.get('msg', '未知错误')}"
            else:
                model_response = f"调用 IPv6 查询接口失败，状态码: {response.status_code}"

        # 回复查询结果
        await message.reply(content=model_response)

    except Exception as e:
        await message.reply(content=f"查询 IP 信息时发生错误: {str(e)}")

    return True

@Commands("/nslookup")
async def query_domain_info(api: BotAPI, message: GroupMessage, params=None):
    ip = "".join(params).strip() if params else None

    if not ip:
        await message.reply(content="请输入有效的域名或 IP 地址。")
        return True

    try:
        # 获取所有地址信息
        addresses = socket.getaddrinfo(ip, None)
        # 提取 IP 地址
        ip_addresses = list(set([addr[4][0] for addr in addresses]))
        ip_addresses_str = ", ".join(ip_addresses)
        await message.reply(content="查询到的 IP 地址有：" + ip_addresses_str)
    except socket.gaierror:
        await message.reply(content="无效的域名或 IP 地址，请检查后重试。")

    return True

@Commands("/ping")
async def ping_info(api: BotAPI, message: GroupMessage, params=None):
    domain = "".join(params).strip() if params else None
    if not domain:
        await message.reply(content="请输入有效的域名或 IP 地址。")
    else:
        # 设置url
        url = 'https://api.tjit.net/api/ping/v2?key='+r.tjit_key+'&type=node'
        # 发送post请求
        response = requests.post(url)
        # 获取响应内容
        result = response.json()["data"][-1]["node"]
        random_node = random.sample(range(1, result), 6)
        ping_content = '\nping测试结果为（随机6节点）：\n'
        for i in random_node:
            url = 'https://api.tjit.net/api/ping/v2?key='+r.tjit_key+'&node='+str(i)+'&host='+domain
            response = requests.post(url)
            result = response.json()
            if 'time' in result['data']:
                ping_content += f"{result['data']['node_name']}-{result['data']['node_isp']}：{result['data']['time']}\n"
            else:
                ping_content += f"{result['data']['node_name']}-{result['data']['node_isp']}：{result['data']['msg']}\n"
        await message.reply(content=ping_content)
    return True

@Commands("/mc")
async def query_mc_command(api: BotAPI, message: GroupMessage, params=None):
    # 通过 r 获取 RCON 密码
    rcon_password = r.mc_rcon_password
    rcon_host = r.mc_server
    rcon_port = int(r.mc_rcon_port)

    if not params:
        await message.reply(content="请提供 Minecraft 服务器命令（say/list/永昼机/关闭永昼机）")
        return
    else:
        # 直接使用 params 作为 Minecraft 命令
        mc_command = params

        if mc_command == "永昼机":
            # 特殊处理命令为“永昼机”的情况
            try:
                with MCRcon(rcon_host, rcon_password, port=rcon_port) as mcr:
                    # 执行多个命令
                    mcr.command("player bot_sleep spawn at -3200 55 9370 facing -90 0 in minecraft:overworld")
                    mcr.command("player bot_sleep use interval 20")
                    await message.reply(content="永昼机已启动")
            except Exception as e:
                await message.reply(content=f"连接 Minecraft 服务器时发生错误: {str(e)}")
            return True

        if mc_command == "关闭永昼机":
            # 特殊处理命令为“关闭永昼机”的情况
            try:
                with MCRcon(rcon_host, rcon_password, port=rcon_port) as mcr:
                    # 执行多个命令
                    mcr.command("player bot_sleep kill")
                    await message.reply(content="永昼机已关闭")
            except Exception as e:
                await message.reply(content=f"连接 Minecraft 服务器时发生错误: {str(e)}")
            return True

        if mc_command not in {"list"} and not any(mc_command.startswith(prefix) for prefix in ["say", "tp"]):
            await message.reply(content="请提供合法的 Minecraft 服务器命令（say/list/永昼机/关闭永昼机）")
        else:
            try:
                # 连接到 RCON 服务器
                with MCRcon(rcon_host, rcon_password, port=rcon_port) as mcr:
                    # 发送命令并获取响应
                    response = mcr.command(mc_command)
                    # 回复命令执行的结果
                    await message.reply(content=f"消息已送达服务器\n{response}")
            except Exception as e:
                await message.reply(content=f"连接 Minecraft 服务器时发生错误: {str(e)}")
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

@Commands("/dsr")
async def query_deepseek_r1(api: BotAPI, message: GroupMessage, params=None):
    user_input = "".join(params) if params else "Hello world!"

    try:
        # 使用 OpenAI 类初始化客户端
        client = OpenAI(api_key=r.baidu_api_key, base_url="http://oneapi.ecustvr.top/v1/")

        # 调用大模型
        completion = client.chat.completions.create(
            model="deepseek-r1",
            messages=[
                {
                    "role": "user",
                    "content": user_input,
                },
            ],
            temperature=0.3,
        )

        # 提取并发送模型响应
        model_reasoning_content = completion.choices[0].message.reasoning_content
        model_response = completion.choices[0].message.content
        await message.reply(content=f"Deepseek-R1:\n推理：\n{model_reasoning_content}\n回复：\n{model_response}")

    except Exception as e:
        # 错误处理
        await message.reply(content=f"调用 Deepseek-R1 大模型时出错: {str(e)}")

    return True

handlers = [
    query_weather,
    query_ecustmc_server,
    daily_word,
    daily_huangli,
    jrrp,
    jrys,
    help,
    wiki,
    add_server,
    remove_server,
    query_tarot,
    query_deepseek_r1,
    query_divinatory_symbol,
    query_ip_info,
    query_domain_info,
    query_mc_command,
    ping_info,
    query_server_status
]


class EcustmcClient(botpy.Client):
    async def on_ready(self):
        _log.info(f"robot[{self.robot.name}] is ready.")

    async def on_group_at_message_create(self, message: GroupMessage):
        for handler in handlers:
            if await handler(api=self.api, message=message):
                return
        # 如果没有处理器处理，调用大模型
        user_input = message.content.strip()  # 获取用户输入
        if user_input:
            try:
                # 调用大模型
                client = OpenAI(api_key=r.ecust_api_key, base_url=r.ecust_url)
                response = client.chat.completions.create(
                    model=r.ecust_model,
                    messages=[
                        {"role": "user", "content": user_input}
                    ],
                    stream=False
                )

                # 提取大模型的回应
                model_response = response.choices[0].message.content if response.choices else "没有有效的回应"

                model_response = model_response.replace('ecust.edu.cn', 'ecust-edu-cn')

                # 定义要替换的域名后缀及其对应的替换字符串
                domain_replacements = {
                    '.cn': '-cn',
                    '.com': '-com',
                    '.org': '-org',
                    '.net': '-net',
                    '.edu': '-edu',
                    '.gov': '-gov',
                    '.top': '-top',
                    '.cc': '-cc',
                    '.me': '-me',
                    '.tv': '-tv',
                    '.info': '-info',
                    '.biz': '-biz',
                    '.name': '-name',
                    '.mobi': '-mobi',
                    '.club': '-club',
                    '.store': '-store',
                    '.app': '-app',
                    '.tech': '-tech',
                    '.ai': '-ai',
                    '.ink': '-ink',
                    '.live': '-live',
                    '.wiki': '-wiki',
                    # 可以继续添加其他需要替换的域名后缀
                }

                # 进行替换
                for old, new in domain_replacements.items():
                    model_response = model_response.replace(old, new)
                
                model_response += "\n\n⚠️由于QQAPI限制，服务器地址中间的“-”请自行换成“.”！"

                # 回复模型生成的内容
                await message.reply(content=f"\nECUST Helper:\n{model_response}")

            except Exception as e:
                # 错误处理，防止大模型调用失败时崩溃
                await message.reply(content=f"调用出错: {str(e)}")
        else:
            # 如果用户没有输入内容
            await message.reply(content=f"不明白你在说什么哦(๑• . •๑)")

    async def on_group_add_robot(self, message: GroupManageEvent):
        await self.api.post_group_message(group_openid=message.group_openid, content="欢迎使用ECUST-Minecraft QQ Bot服务")

    async def on_group_del_robot(self, event: GroupManageEvent):
        _log.info(f"robot[{self.robot.name}] left group ${event.group_openid}")


async def main():
    global session
    session = aiohttp.ClientSession()
    intents = botpy.Intents(
        public_messages=True
    )
    client = EcustmcClient(intents=intents, is_sandbox=False, log_level=30, timeout=60)
    await client.start(appid=r.appid, secret=r.secret)
    await session.close()


asyncio.run(main())
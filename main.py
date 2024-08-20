import asyncio

import botpy
from botpy import BotAPI
from botpy.ext.command_util import Commands
from botpy.manage import GroupManageEvent
from botpy.message import GroupMessage
import time
import sqlite3
from datetime import datetime
import aiohttp
import random
import json

import r

_log = botpy.logging.get_logger()

session: aiohttp.ClientSession


async def on_ecustmc_backend_error(message: GroupMessage):
    await message.reply(content=f"服务无响应，请稍后再试，若此问题依然存在，请联系机器人管理员")


@Commands("校园天气")
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


@Commands("服务器状态")
async def query_ecustmc_server(api: BotAPI, message: GroupMessage, params=None):
    # 假设 r.mc_servers 包含了服务器列表，用逗号分隔
    server_list = r.mc_servers.split(",")

    reply_content = ""
    
    # 遍历每个服务器并查询状态
    for server in server_list:
        server = server.strip()  # 去除两端的空格
        if not server:
            continue
        
        async with session.post(f"https://mcinfo.ecustvr.top/custom/serverlist/?query={server}") as res:
            result = await res.json()
            if res.ok:
                server_info = result
                server=server.replace('.', '-')
                description = server_info.get('description', {}).get('text', '无描述')
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
    
    await message.reply(
        content=reply_content,
        msg_type=0
    )
    
    return True


@Commands("一言")
async def daily_word(api: BotAPI, message: GroupMessage, params=None):
    daily_word = f"https://mxnzp.ecustvr.top/api/daily_word/recommend?count=1&app_id={r.api_app_id}&app_secret={r.api_app_secret}"
    async with session.post(daily_word) as res:
        result = await res.json()
        if res.ok:
            content = result['data'][0]['content']

            reply_content = (
                f"\n"
                f"{content}"
            )

            await message.reply(content=reply_content)
        else:
            error_content = (
                f"获取一言失败"
            )
            await message.reply(content=error_content)
        return True


@Commands("今日黄历")
async def daily_huangli(api: BotAPI, message: GroupMessage, params=None):
    # 获取当前日期
    current_date = time.strftime("%Y%m%d", time.localtime())
    
    # 构建 API 请求 URL
    daily_huangli = f"https://mxnzp.ecustvr.top/api/holiday/single/{current_date}?ignoreHoliday=false&app_id={r.api_app_id}&app_secret={r.api_app_secret}"
    
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


@Commands("今日运势")
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


@Commands("今日人品")
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

@Commands("新手教程")
async def tutorial(api: BotAPI, message: GroupMessage, params=None):
    tutorial_content = (
        "\n👋 欢迎新人！\n"
        "为了享受更好的游戏体验，请先注册皮肤站账号。\n"
        "🔗 访问链接： [点击注册皮肤站](https://mcskin.ecustvr.top/auth/register)\n"
        "通过这个站点，你可以自定义和上传你的皮肤，使用联合认证账号登录游戏，便可进入使用 Union 联合认证的其他高校的 Minecraft 服务器游玩，或登录到支持 Union OAuth 登录的网站。\n"
        "更多关于游戏、启动器及账号配置等，欢迎访问[萌新指南](https://mc.ecustvr.top/tutorial/)，祝游戏愉快！"
    )
    
    await message.reply(content=tutorial_content)
    return True

import urllib.parse

@Commands("wiki")
async def wiki(api: BotAPI, message: GroupMessage, params=None):
    if params:
        # 获取指令后的关键字
        query = ' '.join(params)
        # 对查询关键词进行URL编码
        encoded_query = urllib.parse.quote(query)
        # 生成Wiki链接
        wiki_link = f"https://mc.ecustvr.top/wiki/{encoded_query}"
        
        reply_content = f"\n📚 你可以查看相关信息： [点击访问Wiki]({wiki_link})"
        
        await message.reply(content=reply_content)
    else:
        await message.reply(content="⚠️ 请提供要查询的Wiki页面关键字！")
    
    return True

@Commands("添加服务器")
async def add_server(api: BotAPI, message: GroupMessage, params=None):
    if params:
        new_server = ' '.join(params).strip()
        new_server = new_server.replace(' ', '')

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


@Commands("移除服务器")
async def remove_server(api: BotAPI, message: GroupMessage, params=None):
    if params:
        server_to_remove = ' '.join(params).strip()
        server_to_remove = server_to_remove.replace(' ', '')

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


handlers = [
    query_weather,
    query_ecustmc_server,
    daily_word,
    daily_huangli,
    jrrp,
    jrys,
    tutorial,
    wiki,
    add_server,
    remove_server
]


class EcustmcClient(botpy.Client):
    async def on_ready(self):
        _log.info(f"robot[{self.robot.name}] is ready.")

    async def on_group_at_message_create(self, message: GroupMessage):
        for handler in handlers:
            if await handler(api=self.api, message=message):
                return
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
    client = EcustmcClient(intents=intents, is_sandbox=True, log_level=10, timeout=30)
    await client.start(appid=r.appid, secret=r.secret)
    await session.close()


asyncio.run(main())
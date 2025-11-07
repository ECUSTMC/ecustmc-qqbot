"""运势相关处理器"""
import json
import random
from botpy import BotAPI
from botpy.ext.command_util import Commands
from botpy.message import GroupMessage
from utils.database import get_user_fortune_data, get_user_rp_number


def get_range_description(score: int) -> str:
    """根据人品值获取描述"""
    if score == 0:
        return "这运气也太差了吧？？？该不会是。。。。"
    if score == 66:
        return "恭喜哦，抽到了隐藏彩蛋，六六大顺，666666666"
    if score == 88:
        return "恭喜哦，抽到了隐藏彩蛋，发发发发，888888888"
    if score == 69:
        return "这是什么意思啊，69696969696969696，哈哈哈哈哈哈哈哈哈"
    if score == 100:
        return "哇，今天是元气满满的一天"
    
    if 0 < score < 10:
        return "好烂的运气啊，大概率你今天买泡面没调料没叉子，点外卖没餐具。"
    if 10 <= score < 20:
        return "好烂的运气啊，大概率你今天买泡面没调料没叉子，点外卖没餐具。"
    if 20 <= score < 30:
        return "也许今天更适合摆烂。"
    if 30 <= score < 40:
        return "运气一般般啊，平平淡淡没什么新奇。"
    if 40 <= score < 50:
        return "运气不好不差，钻石矿可能比较难挖到。"
    if 50 <= score < 60:
        return "运气处于正态分布的中部，今天适合玩MC服。"
    if 60 <= score < 70:
        return "运气不好不差，今天就别开箱子了。"
    if 70 <= score < 80:
        return "今天你将会拥有非凡的一天。"
    if 80 <= score < 90:
        return "运气还不错，看起来一切都很顺利。"
    if 90 <= score < 100:
        return "运气真不错，今天适合抽卡。"


@Commands("/今日运势")
async def jrys(api: BotAPI, message: GroupMessage, params=None):
    with open('jrys.json', 'r', encoding='utf-8') as file:
        jrys_data = json.load(file)

    user = f"{message.author.member_openid}"
    random_number, assigned_number, fortune_data = get_user_fortune_data(user, jrys_data)

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
    with open('jrys.json', 'r', encoding='utf-8') as file:
        jrys_data = json.load(file)
    
    user = f"{message.author.member_openid}"
    assigned_number = get_user_rp_number(user, jrys_data)

    reply = f"今日人品值：{assigned_number}，{get_range_description(int(assigned_number))}"

    await message.reply(content=reply)
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
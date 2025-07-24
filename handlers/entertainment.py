"""娱乐功能处理器"""
import urllib.parse
import random
import aiohttp
from botpy import BotAPI
from botpy.ext.command_util import Commands
from botpy.message import GroupMessage


@Commands("vv")
async def query_vv(api: BotAPI, message: GroupMessage, params=None):
    # 如果没有提供查询参数，读取vv.txt文件获取表情名
    if not params:
        with open('vv.txt', 'r', encoding='utf-8') as file:
            emote_list = file.readlines()
        emote_name = random.choice(emote_list).strip()
        # 拼接完整的URL
        encoded_emote_name = urllib.parse.quote(emote_name)
        emote_url = f"https://cn-nb1.rains3.com/vvq/images/{encoded_emote_name}"
    else:
        # 有查询参数，构建请求负载
        query = params
        encoded_query = urllib.parse.quote(query)  # 对查询参数进行URL编码

        async with aiohttp.ClientSession() as session:
            url = f'https://api.zvv.quest/search?q={encoded_query}&n=5'
            async with session.get(url) as response:
                # 解析返回的JSON数据
                result = await response.json()
                emote_url = random.choice(result["data"])  # 从返回的列表中随机选择一个表情包文件名
                emote_name = urllib.parse.unquote(emote_url.split('/')[-1].rstrip('.png'))  # 获取表情包文件名

    # 上传表情包图片
    uploadmedia = await api.post_group_file(
        group_openid=message.group_openid,
        file_type=1,
        url=emote_url
    )

    # 构建回复内容
    reply_content = (
        f"\n"
        f"{emote_name.rstrip('.png')}"
    )

    # 发送消息
    await message.reply(
        content=reply_content,
        msg_type=7,
        media=uploadmedia
    )

    return True
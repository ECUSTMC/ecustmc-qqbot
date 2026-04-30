"""娱乐功能处理器"""
import urllib.parse
import random
import aiohttp
import json
from botpy import BotAPI
from botpy.ext.command_util import Commands
from botpy.message import GroupMessage, DirectMessage
import config


@Commands("vv")
async def query_vv(api: BotAPI, message: GroupMessage | DirectMessage, params=None):
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

    # 判断是群聊还是私聊，使用对应的上传接口
    if isinstance(message, DirectMessage):
        # 私聊：使用 post_c2c_file
        user_openid = message.author.user_openid
        uploadmedia = await api.post_c2c_file(
            openid=user_openid,
            file_type=1,
            url=emote_url
        )
    else:
        # 群聊：使用 post_group_file
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


@Commands("/三角洲密码")
async def query_deltaforce_password(api: BotAPI, message: GroupMessage, params=None):
    """查询三角洲行动密码"""
    try:
        # 构建API请求URL
        api_url = f"https://api.makuo.cc/api/get.game.deltaforce?token={config.DELTAFORCE_API_TOKEN}"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url) as response:
                if response.status != 200:
                    await message.reply(content="三角洲行动API请求失败，请稍后再试")
                    return False
                
                result = await response.json()
                
                if result["code"] != 200:
                    await message.reply(content=f"三角洲行动API返回错误: {result['msg']}")
                    return False
                
                # 构建回复内容
                reply_content = "🔍 三角洲行动密码查询结果\n\n"
                
                # 添加所有地图信息，包括图片链接
                for item in result["data"]:
                    reply_content += f"🗺️ {item['map_name']}\n"
                    reply_content += f"📍 {item['location']}\n" 
                    reply_content += f"🔢 密码: {item['password']}\n"
                    
                    # 添加图片链接
                    # if item["image_urls"]:
                    #     reply_content += "🖼️ 位置图: "
                    #     for img_url in item["image_urls"]:
                    #         reply_content += f"{img_url.replace('fs.img4399.com', 'mcskin.ecustvr.top/auth/qqbot/fs.img4399.com')} "
                    #     reply_content += "\n"
                    
                    reply_content += "\n"
                    
                reply_content += f"⏰ 更新时间: {result['time']}\n"
                
                await message.reply(content=reply_content)

                return True
                
    except Exception as e:
        await message.reply(content=f"查询三角洲行动密码时发生错误: {str(e)}")
        return False
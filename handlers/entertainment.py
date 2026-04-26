"""娱乐功能处理器"""
import urllib.parse
import random
import aiohttp
import json
from botpy import BotAPI
from botpy.ext.command_util import Commands
from botpy.message import GroupMessage
from botpy.types.message import MarkdownPayload
import config


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

    # 构建Markdown回复内容（使用QQ Markdown图片语法）
    reply_content = (
        f"## {emote_name.rstrip('.png')}\n\n"
        f"![{emote_name.rstrip('.png')} #200px #200px]({emote_url})"
    )

    # 发送消息
    markdown = MarkdownPayload(content=reply_content)
    await message.reply(markdown=markdown, msg_type=2)

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
                reply_content = "## 🔍 三角洲行动密码\n\n"
                
                # 添加所有地图信息，包括图片链接
                for item in result["data"]:
                    reply_content += f"### 🗺️ {item['map_name']}\n\n"
                    reply_content += f"- 📍 位置：**{item['location']}**\n"
                    reply_content += f"- 🔢 密码：**{item['password']}**\n"
                    
                    # 添加图片
                    if item.get("image_urls"):
                        for img_url in item["image_urls"]:
                            proxied_url = img_url.replace('fs.img4399.com', 'mcskin.ecustvr.top/auth/qqbot/fs.img4399.com')
                            reply_content += f"\n![{item['location']} #300px #200px]({proxied_url})\n"
                    
                    reply_content += "\n"
                    
                reply_content += f"***\n⏰ 更新时间：{result['time']}"
                
                markdown = MarkdownPayload(content=reply_content)
                await message.reply(markdown=markdown, msg_type=2)

                return True
                
    except Exception as e:
        await message.reply(content=f"查询三角洲行动密码时发生错误: {str(e)}")
        return False
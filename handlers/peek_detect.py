"""窥屏检测处理器"""
import asyncio
import re
import time
from datetime import datetime
import botpy
from botpy import BotAPI
from botpy.ext.command_util import Commands
from botpy.http import Route
from botpy.message import GroupMessage
from botpy.types.message import MarkdownPayload
from config import PEEK_IMAGE_URL, PEEK_NGINX_LOG

_log = botpy.logging.get_logger()

# 检测等待时间（秒），给客户端加载图片的时间
PEEK_WAIT_SECONDS = 8
# nginx 日志解析正则（combined 格式）
_NGINX_LOG_PATTERN = re.compile(
    r'^(\S+)\s+\S+\s+\S+\s+\[([^\]]+)\]\s+"GET\s+(\S+)\s+HTTP'
)


async def _recall_group_message(api: BotAPI, group_openid: str, message_id: str):
    """撤回群消息"""
    try:
        route = Route(
            "DELETE",
            "/v2/groups/{group_openid}/messages/{message_id}",
            group_openid=group_openid,
            message_id=message_id,
        )
        result = await api._http.request(route)
        _log.info(f"撤回消息 {message_id} 结果: {result}")
    except Exception as e:
        _log.error(f"撤回消息 {message_id} 失败: {e}")


@Commands("/窥屏")
async def peek_detect(api: BotAPI, message: GroupMessage, params=None):
    """窥屏检测：发送一张会自动渲染的图片，然后分析 nginx 日志中访问该图片的 IP"""

    # 从配置 URL 提取图片路径（如 https://qqbot.bestzyq.cn/bear.jpg -> /bear.jpg）
    from urllib.parse import urlparse
    image_path = urlparse(PEEK_IMAGE_URL).path

    # 记录发送时间
    send_time = time.time()
    send_time_str = datetime.now().strftime("%H:%M:%S")

    # 发送包含追踪图片的 markdown 消息
    # 添加时间戳参数避免浏览器缓存
    image_url_with_ts = f"{PEEK_IMAGE_URL}?t={int(send_time)}"
    md_content = (
        f"## 👁️ 窥屏检测\n\n"
        f"![peek #640px #640px]({image_url_with_ts})\n\n"
        f"⏳ 检测已启动，等待 {PEEK_WAIT_SECONDS} 秒后分析结果..."
    )
    markdown = MarkdownPayload(content=md_content)
    first_msg = await message.reply(markdown=markdown, msg_type=2)
    first_msg_id = first_msg.get("id") if isinstance(first_msg, dict) else getattr(first_msg, "id", None)
    _log.info(f"窥屏检测首条消息ID: {first_msg_id}")

    # 等待客户端加载图片
    await asyncio.sleep(PEEK_WAIT_SECONDS)

    # 读取并分析 nginx 日志
    try:
        with open(PEEK_NGINX_LOG, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
    except FileNotFoundError:
        await message.reply(content=f"❌ 未找到 nginx 日志文件: {PEEK_NGINX_LOG}", msg_seq=2)
        # 撤回第一条消息
        if first_msg_id:
            await _recall_group_message(api, message.group_openid, first_msg_id)
        return True
    except Exception as e:
        await message.reply(content=f"❌ 读取 nginx 日志失败: {str(e)}", msg_seq=2)
        # 撤回第一条消息
        if first_msg_id:
            await _recall_group_message(api, message.group_openid, first_msg_id)
        return True

    # 解析日志，筛选访问追踪图片且在时间窗口内的条目
    peek_ips = {}
    for line in lines:
        m = _NGINX_LOG_PATTERN.match(line)
        if not m:
            continue
        ip, log_time_str, request_path = m.group(1), m.group(2), m.group(3)

        # 检查是否访问了追踪图片路径
        if not request_path.startswith(image_path):
            continue

        # 解析日志时间：nginx 默认格式 "02/May/2026:13:45:22 +0800"
        try:
            log_time = datetime.strptime(log_time_str.split()[0], "%d/%b/%Y:%H:%M:%S")
            log_ts = log_time.timestamp()
        except (ValueError, IndexError):
            continue

        # 只统计发送时间前后窗口内的访问（前2秒到后PEEK_WAIT_SECONDS秒）
        if send_time - 2 <= log_ts <= send_time + PEEK_WAIT_SECONDS + 2:
            if ip not in peek_ips:
                peek_ips[ip] = log_time_str.split()[0]

    # 构建结果
    if not peek_ips:
        result_md = f"## 👁️ 窥屏检测结果\n\n✅ 未检测到任何窥屏 IP\n\n> 检测时间: {send_time_str} | 等待: {PEEK_WAIT_SECONDS}s"
    else:
        ip_lines = []
        for i, (ip, access_time) in enumerate(peek_ips.items(), 1):
            ip_lines.append(f"**{i}.** `{ip}` — {access_time}")

        result_md = (
            f"## 👁️ 窥屏检测结果\n\n"
            f"检测到 **{len(peek_ips)}** 个 IP 访问了追踪图片：\n\n"
            + "\n".join(ip_lines)
            + f"\n\n---\n> 检测时间: {send_time_str} | 等待: {PEEK_WAIT_SECONDS}s"
        )

    markdown = MarkdownPayload(content=result_md)
    await message.reply(markdown=markdown, msg_type=2, msg_seq=2)

    # 撤回第一条包含追踪图片的消息
    if first_msg_id:
        await _recall_group_message(api, message.group_openid, first_msg_id)

    return True

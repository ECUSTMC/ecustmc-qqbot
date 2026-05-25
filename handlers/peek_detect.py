"""窥屏检测处理器"""
import asyncio
import re
import time
from datetime import datetime
from botpy import BotAPI
from botpy.ext.command_util import Commands
from botpy.message import GroupMessage
from botpy.types.message import MarkdownPayload

# 窥屏检测图片配置
PEEK_IMAGE_URL = "https://qqbot.bestzyq.cn/bear.jpg"
NGINX_LOG_PATH = "/www/wwwlogs/qqbot.bestzyq.cn.log"
# 检测等待时间（秒），给客户端加载图片的时间
PEEK_WAIT_SECONDS = 8
# 日志时间解析格式（nginx 默认格式）
_NGINX_LOG_PATTERN = re.compile(
    r'^(\S+)\s+\S+\s+\S+\s+\[([^\]]+)\]\s+"GET\s+(\S+)\s+HTTP'
)


@Commands("/窥屏")
async def peek_detect(api: BotAPI, message: GroupMessage, params=None):
    """窥屏检测：发送一张会自动渲染的图片，然后分析 nginx 日志中访问该图片的 IP"""

    # 生成唯一追踪参数，避免缓存影响
    trace_id = f"peek_{int(time.time())}_{id(message)}"
    tracked_url = f"{PEEK_IMAGE_URL}?t={trace_id}"

    # 记录发送时间
    send_time = time.time()
    send_time_str = datetime.now().strftime("%H:%M:%S")

    # 发送包含追踪图片的 markdown 消息（参考塔罗牌的图片格式：![name #宽 #高](url)）
    md_content = (
        f"## 👁️ 窥屏检测\n\n"
        f"![peek #640px #640px]({tracked_url})\n\n"
        f"⏳ 检测已启动，等待 {PEEK_WAIT_SECONDS} 秒后分析结果..."
    )
    markdown = MarkdownPayload(content=md_content)
    sent_msg = await message.reply(markdown=markdown, msg_type=2)

    # 等待客户端加载图片
    await asyncio.sleep(PEEK_WAIT_SECONDS)

    # 撤回检测消息（隐藏撤回提示）
    try:
        if hasattr(message, 'group_openid') and message.group_openid:
            # 群消息：通过 api 直接调用撤回接口
            await api._http.request(
                type(api._http).Route("DELETE", "/v2/groups/{group_openid}/messages/{message_id}", group_openid=message.group_openid, message_id=sent_msg.id),
            )
    except Exception:
        pass  # 撤回失败不影响结果

    # 读取并分析 nginx 日志
    try:
        with open(NGINX_LOG_PATH, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
    except FileNotFoundError:
        await message.reply(content=f"❌ 未找到 nginx 日志文件: {NGINX_LOG_PATH}", msg_seq=2)
        return True
    except Exception as e:
        await message.reply(content=f"❌ 读取 nginx 日志失败: {str(e)}", msg_seq=2)
        return True

    # 解析日志，筛选包含追踪参数的条目
    peek_ips = {}
    for line in lines:
        m = _NGINX_LOG_PATTERN.match(line)
        if not m:
            continue
        ip, log_time_str, request_path = m.group(1), m.group(2), m.group(3)

        # 检查是否是本次追踪的请求
        if trace_id not in request_path:
            continue

        # 解析日志时间：nginx 默认格式 "02/May/2026:13:45:22 +0800"
        try:
            log_time = datetime.strptime(log_time_str.split()[0], "%d/%b/%Y:%H:%M:%S")
            log_ts = log_time.timestamp()
        except (ValueError, IndexError):
            continue

        # 只统计发送时间之后（允许 2 秒误差）的访问
        if log_ts >= send_time - 2:
            if ip not in peek_ips:
                peek_ips[ip] = log_time_str.split()[0]  # 只保留时间部分

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
    return True

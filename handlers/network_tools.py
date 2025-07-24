"""网络工具处理器"""
import socket
import random
import requests
from botpy import BotAPI
from botpy.ext.command_util import Commands
from botpy.message import GroupMessage
from utils.network import is_ipv4, checkip, resolve_domain, query_ipv4, query_ipv6
from config import TJIT_KEY


@Commands("/ip")
async def query_ip_info(api: BotAPI, message: GroupMessage, params=None):
    ip = "".join(params).strip() if params else None
    
    try:
        if not ip:
            model_response = "请输入要查询的IP地址或域名"
        else:
            if not checkip(ip):
                ips = resolve_domain(ip)
                if not ips:
                    model_response = "输入的 IP地址/域名 格式不正确或无法解析，请输入有效的 IPv4/IPv6 地址或域名。"
                else:
                    results = []
                    for current_ip in ips:
                        if is_ipv4(current_ip):
                            results.append(query_ipv4(current_ip))
                        else:
                            results.append(query_ipv6(current_ip))
                    model_response = "\n\n".join(results)
            else:
                if is_ipv4(ip):
                    model_response = query_ipv4(ip)
                else:
                    model_response = query_ipv6(ip)

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
        url = 'https://api.tjit.net/api/ping/v2?key='+TJIT_KEY+'&type=node'
        # 发送post请求
        response = requests.post(url)
        # 获取响应内容
        result = response.json()["data"][-1]["node"]
        random_node = random.sample(range(1, result), 6)
        ping_content = '\nping测试结果为（随机6节点）：\n'
        for i in random_node:
            url = 'https://api.tjit.net/api/ping/v2?key='+TJIT_KEY+'&node='+str(i)+'&host='+domain
            response = requests.post(url)
            result = response.json()
            if 'time' in result['data']:
                ping_content += f"{result['data']['node_name']}-{result['data']['node_isp']}：{result['data']['time']}\n"
            else:
                ping_content += f"{result['data']['node_name']}-{result['data']['node_isp']}：{result['data']['msg']}\n"
        await message.reply(content=ping_content)
    return True
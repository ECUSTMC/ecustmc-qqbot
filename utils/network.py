"""网络工具模块"""
import socket
import re
import IPy
import requests
import aiohttp


def is_ipv4(ip):
    """检查是否为IPv4地址"""
    pattern = re.compile(r'^((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$')
    return pattern.match(ip) is not None


def checkip(address):
    """检查IP地址是否有效"""
    try:
        version = IPy.IP(address).version()
        if version == 4 or version == 6:
            return True
        else:
            return False
    except Exception as e:
        return False


def resolve_domain(domain):
    """解析域名获取IP地址"""
    try:
        addresses = socket.getaddrinfo(domain, None)
        ip_addresses = list(set(addr[4][0] for addr in addresses))
        return ip_addresses
    except socket.gaierror:
        return None


def query_ipv4(ip):
    """查询IPv4地址信息"""
    api_url = f"https://ip.ecust.icu/find?ip={ip}"
    response = requests.get(api_url)
    if response.status_code == 200:
        result = response.json()
        if result.get("code") == 200:
            query = result["data"]["query"]
            isp = query.get("isp", "未知ISP")
            locale = query.get("locale", "未知地区")
            return f"IPv4 地址 {ip} 的查询结果：\nISP: {isp}\n地区: {locale}\nPowered by Eric"
        else:
            return f"查询 IPv4 地址 {ip} 失败：{result.get('msg', '未知错误')}"
    else:
        return f"调用 IPv4 查询接口失败，状态码: {response.status_code}"


def query_ipv6(ip):
    """查询IPv6地址信息"""
    api_url = f"https://ip.zxinc.org/api.php?type=json&ip={ip}"
    response = requests.get(api_url)
    if response.status_code == 200:
        result = response.json()
        if result.get("code") == 0:
            location = result["data"].get("location", "未知地区")
            return f"IPv6 地址 {ip} 的查询结果：\n位置: {location}"
        else:
            return f"查询 IPv6 地址 {ip} 失败：{result.get('msg', '未知错误')}"
    else:
        return f"调用 IPv6 查询接口失败，状态码: {response.status_code}"


async def get_tenant_access_token(app_id: str, app_secret: str) -> str:
    """获取飞书访问令牌"""
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    headers = {"Content-Type": "application/json"}
    payload = {"app_id": app_id, "app_secret": app_secret}
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as response:
                data = await response.json()
                if data.get("code") == 0:
                    return data["tenant_access_token"]
                else:
                    print(f"获取飞书访问令牌失败: {data}")
                    return None
    except Exception as e:
        print(f"获取飞书访问令牌出错: {e}")
        return None
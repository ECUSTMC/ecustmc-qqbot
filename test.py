import socket

ip = "blog.ecust.fun"

# 获取所有地址信息
addresses = socket.getaddrinfo(ip, None)
print("Addresses:", addresses)

# 提取 IP 地址并去重
ip_addresses = list(set([addr[4][0] for addr in addresses]))
print("Unique IP Addresses:", ip_addresses)

# 输出 IP 地址字符串
ip_addresses_str = ", ".join(ip_addresses)
print("IP Addresses String:", ip_addresses_str)
"""校车查询处理器"""
import asyncio
import aiohttp
import json
from datetime import datetime, time
from botpy import BotAPI
from botpy.ext.command_util import Commands
from botpy.message import GroupMessage


@Commands("/校车")
async def query_bus(api: BotAPI, message: GroupMessage, params=None):
    """查询校车时刻表并返回最近的班次"""
    # 解析参数，默认查询1班车
    count = 1
    if params and params.replace(" ", "").isdigit():
        count = min(int(params.replace(" ", "")), 13)  # 最多查询13班车
        count = max(count, 1)  # 至少查询1班车
    
    url = "https://hqfw.ecust.edu.cn/hqecust/api/bus/departure/time/search"
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            # 同时查询两个线路
            tasks = []
            for router_id in ["14", "15"]:
                payload = {
                    "pageSize": 100,
                    "EQ": {"routerId": router_id},
                    "ASC": ["orderNumber"]
                }
                tasks.append(session.post(url, json=payload, headers=headers))
            
            responses = await asyncio.gather(*tasks)
            
            all_buses = []
            for i, response in enumerate(responses):
                if response.status == 200:
                    data = await response.json()
                    if data.get("status") == 200 and data.get("result", {}).get("result"):
                        router_id = "14" if i == 0 else "15"
                        route_name = "徐汇→奉贤" if router_id == "14" else "奉贤→徐汇"
                        buses = data["result"]["result"]
                        for bus in buses:
                            bus["route_name"] = route_name
                        all_buses.extend(buses)
            
            if all_buses:
                # 找出每个方向最近的班次
                xh_to_fx_buses = [bus for bus in all_buses if bus.get("route_name") == "徐汇→奉贤"]
                fx_to_xh_buses = [bus for bus in all_buses if bus.get("route_name") == "奉贤→徐汇"]
                
                next_xh_buses = find_next_buses(xh_to_fx_buses, count)
                next_fx_buses = find_next_buses(fx_to_xh_buses, count)
                
                if next_xh_buses or next_fx_buses:
                    reply_content = format_buses_info(next_xh_buses, next_fx_buses, count)
                else:
                    reply_content = "今日已无班次，恭喜你要露宿街头了🐶"
                    
                await message.reply(content=reply_content)
            else:
                await message.reply(content="校车查询失败，请稍后再试")
                
    except Exception as e:
        await message.reply(content=f"查询校车时发生错误: {str(e)}")
    
    return True


def find_next_buses(bus_schedules, count=1):
    """从校车时刻表中找出最近的几班车"""
    now = datetime.now()
    current_time = now.time()
    current_weekday = now.weekday() + 1  # 周一=1, 周日=7
    
    valid_buses = []
    
    for bus in bus_schedules:
        # 检查星期是否匹配
        weeks = bus.get("weeks", "").split(",")
        if str(current_weekday) not in weeks and "7" not in weeks:
            continue
            
        # 解析发车时间
        departure_str = bus.get("departureTime", "")
        try:
            if "(" in departure_str:
                departure_str = departure_str.split("(")[0]
            departure_time = datetime.strptime(departure_str, "%H:%M").time()
        except ValueError:
            continue
            
        # 只保留未来的班次
        if departure_time > current_time:
            valid_buses.append({
                "time": departure_time,
                "departure_str": departure_str,
                "bus_info": bus
            })
    
    # 按时间排序，取最近的几班
    if valid_buses:
        valid_buses.sort(key=lambda x: x["time"])
        return [bus["bus_info"] for bus in valid_buses[:count]]
    
    return []


def format_buses_info(xh_buses, fx_buses, count):
    """格式化多班校车信息（双向各显示指定数量）"""
    
    result = f"🚌 最近{count}班校车信息：\n\n"
    
    # 徐汇→奉贤方向
    if xh_buses:
        result += "🔵 徐汇校区 → 奉贤校区：\n"
        for i, bus in enumerate(xh_buses, 1):
            departure_time = bus.get("departureTime", "未知时间")
            
            result += (
                f"   {i}. 🕐 {departure_time}\n"
            )
        result += "\n"
    else:
        result += "🔵 徐汇→奉贤：今日已无班次\n\n"
    
    # 奉贤→徐汇方向
    if fx_buses:
        result += "🟠 奉贤校区 → 徐汇校区：\n"
        for i, bus in enumerate(fx_buses, 1):
            departure_time = bus.get("departureTime", "未知时间")
            
            result += (
                f"   {i}. 🕐 {departure_time}\n"
            )
        result += "\n"
    else:
        result += "🟠 奉贤→徐汇：今日已无班次\n\n"
    
    result += "💡 提示：使用 /校车 3 查询双向各3班车，最多13班。"
    return result
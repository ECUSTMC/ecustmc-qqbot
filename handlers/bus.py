"""校车查询处理器"""
import json
from datetime import datetime, time
from botpy import BotAPI
from botpy.ext.command_util import Commands
from botpy.message import GroupMessage
from botpy.types.message import MarkdownPayload


@Commands("/校车")
async def query_bus(api: BotAPI, message: GroupMessage, params=None):
    """查询校车时刻表并返回最近的班次"""
    # 解析参数，默认查询1班车
    count = 1
    if params and params.replace(" ", "").isdigit():
        count = min(int(params.replace(" ", "")), 13)  # 最多查询13班车
        count = max(count, 1)  # 至少查询1班车
    
    try:
        # 从本地JSON文件读取校车时刻表
        all_buses = []
        
        # 读取线路14（徐汇→奉贤）
        try:
            with open("bus_schedule_14.json", "r", encoding="utf-8") as f:
                data_14 = json.load(f)
                if data_14.get("status") == 200 and data_14.get("result", {}).get("result"):
                    buses = data_14["result"]["result"]
                    for bus in buses:
                        bus["route_name"] = "徐汇→奉贤"
                    all_buses.extend(buses)
        except Exception as e:
            await message.reply(content=f"读取徐汇→奉贤线路数据失败: {str(e)}")
            return True
        
        # 读取线路15（奉贤→徐汇）
        try:
            with open("bus_schedule_15.json", "r", encoding="utf-8") as f:
                data_15 = json.load(f)
                if data_15.get("status") == 200 and data_15.get("result", {}).get("result"):
                    buses = data_15["result"]["result"]
                    for bus in buses:
                        bus["route_name"] = "奉贤→徐汇"
                    all_buses.extend(buses)
        except Exception as e:
            await message.reply(content=f"读取奉贤→徐汇线路数据失败: {str(e)}")
            return True
        
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
                
            markdown = MarkdownPayload(content=reply_content)
            await message.reply(markdown=markdown, msg_type=2)
        else:
            await message.reply(content="校车数据读取失败，请检查数据文件")
            
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
        if str(current_weekday) not in weeks:
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
    
    result = f"## 🚌 最近{count}班校车信息\n\n"
    
    # 徐汇→奉贤方向
    if xh_buses:
        result += "### 🔵 徐汇校区 → 奉贤校区\n\n"
        for i, bus in enumerate(xh_buses, 1):
            departure_time = bus.get("departureTime", "未知时间")
            result += f"{i}. 🕐 **{departure_time}**\n"
        result += "\n"
    else:
        result += "### 🔵 徐汇→奉贤\n\n今日已无班次\n\n"
    
    # 奉贤→徐汇方向
    if fx_buses:
        result += "### 🟠 奉贤校区 → 徐汇校区\n\n"
        for i, bus in enumerate(fx_buses, 1):
            departure_time = bus.get("departureTime", "未知时间")
            result += f"{i}. 🕐 **{departure_time}**\n"
        result += "\n"
    else:
        result += "### 🟠 奉贤→徐汇\n\n今日已无班次\n\n"
    
    result += "***\n💡 提示：使用 `/校车 3` 查询双向各3班车，最多13班。"
    return result
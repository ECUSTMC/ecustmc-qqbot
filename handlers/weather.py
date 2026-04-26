"""天气查询处理器"""
import asyncio
import aiohttp
from botpy import BotAPI
from botpy.ext.command_util import Commands
from botpy.message import GroupMessage
from botpy.types.message import MarkdownPayload
from config import WEATHER_API_TOKEN


@Commands("/校园天气")
async def query_weather(api: BotAPI, message: GroupMessage, params=None):
    async with aiohttp.ClientSession() as session:
        fx_res, xh_res = await asyncio.gather(
            session.get(f"https://restapi.amap.com/v3/weather/weatherInfo?city=310120&key=" + WEATHER_API_TOKEN),
            session.get(f"https://restapi.amap.com/v3/weather/weatherInfo?city=310104&key=" + WEATHER_API_TOKEN)
        )

        if fx_res.ok:
            fx_result = await fx_res.json()
            xh_result = await xh_res.json()
            if fx_result.get("status") == "1" and "lives" in fx_result and len(fx_result["lives"]) > 0:
                fx_live_data = fx_result["lives"][0]
                xh_live_data = xh_result["lives"][0]

                fx_weather = fx_live_data.get("weather", "N/A")
                fx_temperature = fx_live_data.get("temperature", "N/A")
                fx_winddirection = fx_live_data.get("winddirection", "N/A")
                fx_windpower = fx_live_data.get("windpower", "N/A")
                fx_humidity = fx_live_data.get("humidity", "N/A")

                xh_weather = xh_live_data.get("weather", "N/A")
                xh_temperature = xh_live_data.get("temperature", "N/A")
                xh_winddirection = xh_live_data.get("winddirection", "N/A")
                xh_windpower = xh_live_data.get("windpower", "N/A")
                xh_humidity = xh_live_data.get("humidity", "N/A")

                reporttime = fx_live_data.get("reporttime", "N/A")

                reply_content = (
                    f"🌤️ **校园天气**\n"
                    f"\n"
                    f"📍 **奉贤校区**\n"
                    f"> 天气：{fx_weather} ｜ 温度：{fx_temperature}°C\n"
                    f"> 风向：{fx_winddirection} ｜ 风力：{fx_windpower}级\n"
                    f"> 湿度：{fx_humidity}%\n"
                    f"\n"
                    f"📍 **徐汇校区**\n"
                    f"> 天气：{xh_weather} ｜ 温度：{xh_temperature}°C\n"
                    f"> 风向：{xh_winddirection} ｜ 风力：{xh_windpower}级\n"
                    f"> 湿度：{xh_humidity}%\n"
                    f"\n"
                    f"🕐 更新时间：{reporttime}"
                )

                markdown = MarkdownPayload(content=reply_content)
                await message.reply(markdown=markdown, msg_type=2)
            else:
                error_content = "❌ 查询失败，响应数据不正确"
                markdown = MarkdownPayload(content=error_content)
                await message.reply(markdown=markdown, msg_type=2)
        else:
            error_content = "❌ 查询失败，无法连接到天气服务"
            markdown = MarkdownPayload(content=error_content)
            await message.reply(markdown=markdown, msg_type=2)
        return True
"""配置模块"""
import r

# 机器人配置
APPID = r.appid
SECRET = r.secret

# API配置
WEATHER_API_TOKEN = r.weather_api_token
API_APP_ID = r.api_app_id
API_APP_SECRET = r.api_app_secret
BAIDU_API_KEY = r.baidu_api_key
TJIT_KEY = r.tjit_key

# 服务器配置
MC_SERVERS = r.mc_servers
MC_RCON_PASSWORD = r.mc_rcon_password
MC_SERVER = r.mc_server
MC_RCON_PORT = int(r.mc_rcon_port)

# 飞书配置
FEISHU_APP_ID = "cli_a8f1d48265fc500e"
FEISHU_APP_SECRET = "u2NfRSgPlrI4KUhba3389eyj3LSa4aGR"

# AI模型配置字典 - 支持不同模型使用不同的API设置
MODEL_CONFIGS = {
    "deepseek-reasoner": {
        "api_key": r.ecust_api_key,
        "base_url": r.ecust_url
    },
    "deepseek-chat": {
        "api_key": r.ecust_api_key, 
        "base_url": r.ecust_url
    },
    "ernie-speed-8k": {
        "api_key": r.ecust_api_key,
        "base_url": r.ecust_url
    }
    # 可以继续添加其他模型的配置
    # "gpt-4": {
    #     "api_key": r.openai_api_key,
    #     "base_url": "https://api.openai.com/v1/"
    # },
    # "claude-3": {
    #     "api_key": r.anthropic_api_key,
    #     "base_url": "https://api.anthropic.com/v1/"
    # }
}

# 三角洲行动API配置
DELTAFORCE_API_TOKEN = r.deltaforce_api_token
CLASS_API_KEY = r.class_api_token
"""配置模块"""
import r

# 机器人配置
APPID = r.appid
SECRET = r.secret

# API配置
WEATHER_API_TOKEN = r.weather_api_token
API_APP_ID = r.api_app_id
API_APP_SECRET = r.api_app_secret
TJIT_KEY = r.tjit_key

# 服务器配置
MC_SERVERS = r.mc_servers
MC_MCSRVSTAT_SERVERS = r.mc_mcsrvstat_servers
MC_RCON_PASSWORD = r.mc_rcon_password
MC_SERVER = r.mc_server
MC_RCON_PORT = int(r.mc_rcon_port)

# 飞书配置
FEISHU_APP_ID = r.feishu_app_id
FEISHU_APP_SECRET = r.feishu_app_secret

ECUST_MODEL = r.ecust_model

# AI模型配置字典 - 支持不同模型使用不同的API设置
MODEL_CONFIGS = {
    "clawdbot": {
        "api_key": r.clawdbot_api_key, 
        "base_url": r.clawdbot_url
    },
    "auto": {
        "api_key": r.ecust_api_key,
        "base_url": r.ecust_url
    },
    ECUST_MODEL: {
        "api_key": r.ecust_api_key,
        "base_url": r.ecust_url
    }
}

# 三角洲行动API配置
DELTAFORCE_API_TOKEN = r.deltaforce_api_token
CLASS_API_KEY = r.class_api_token

# AI功能开关
AI_GROUP_ENABLED = r.ai_group_enabled
AI_DIRECT_ENABLED = r.ai_direct_enabled

# AI图片处理配置
IMAGE_SAVE_DIR = r.image_save_dir
IMAGE_BASE_URL = r.image_base_url
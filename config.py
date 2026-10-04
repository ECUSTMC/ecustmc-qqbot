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
# 注：早期还有一套独立的 "clawdbot" 配置（另一个网关、模型名写死 clawdbot），
# 那个模型早已下线（newapi 上不存在，调用必 503），现已全部改用 ECUST_MODEL。
MODEL_CONFIGS = {
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

# 校园问答（腾讯乐享知识库）—— 默认 @ 机器人时回答学校相关问题
LEXIANG_APP_KEY = r.lexiang_app_key
LEXIANG_APP_SECRET = r.lexiang_app_secret
LEXIANG_BASE_URL = r.lexiang_base_url
LEXIANG_STAFF_ID = r.lexiang_staff_id
LEXIANG_QA_MODE = r.lexiang_qa_mode
LEXIANG_TARGETS = r.lexiang_targets
CAMPUS_KB_SPACE_ID = r.DEFAULT_CAMPUS_KB_SPACE_ID
# 缺凭据时自动关闭（见 r.py）
CAMPUS_QA_ENABLED = r.campus_qa_enabled
CAMPUS_QA_REQUESTED = r.campus_qa_requested

# 消息路由（判断「找群 / 查知识库 / 走 AI 对话」）—— 与 /ai、/model 完全独立的一套配置
ROUTER_API_KEY = r.router_api_key
ROUTER_URL = r.router_url
ROUTER_MODEL = r.router_model
ROUTER_TIMEOUT = r.router_timeout

# MC投票API配置
MCVOTE_API_URL = r.mcvote_api_url
MCVOTE_API_TOKEN = r.mcvote_api_token

# 窥屏检测配置
PEEK_IMAGE_URL = r.peek_image_url
PEEK_NGINX_LOG = r.peek_nginx_log

# 全量消息调试开关
FULL_MESSAGE_DEBUG = r.full_message_debug
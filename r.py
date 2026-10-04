import os
from dotenv import load_dotenv

load_dotenv()
# 定义更新 .env 文件的函数
def update_env_variable(key, value):
    # 读取现有的 .env 文件
    with open('.env', 'r') as file:
        lines = file.readlines()

    # 查找并更新变量
    updated = False
    for i, line in enumerate(lines):
        if line.startswith(f"{key}="):
            lines[i] = f"{key}={value}\n"
            updated = True
            break

    # 如果没有找到变量，则添加它
    if not updated:
        lines.append(f"{key}={value}\n")

    # 将更新后的内容写回 .env 文件
    with open('.env', 'w') as file:
        file.writelines(lines)

    # 更新环境变量，使其生效
    os.environ[key] = value

appid = os.getenv("QQBOT_APP_ID")
if appid is None:
    raise Exception('Missing "QQBOT_APP_ID" environment variable for your bot AppID')

secret = os.getenv("QQBOT_APP_SECRET")
if secret is None:
    raise Exception('Missing "QQBOT_APP_SECRET" environment variable for your AppSecret')

weather_api_token = os.getenv("WEATHER_API_TOKEN")
if weather_api_token is None:
    raise Exception('Missing "WEATHER_API_TOKEN" environment variable for your AppSecret')

api_app_id = os.getenv("API_APP_ID")
if api_app_id is None:
    raise Exception('Missing "API_APP_ID" environment variable for your AppSecret')

api_app_secret = os.getenv("API_APP_SECRET")
if api_app_secret is None:
    raise Exception('Missing "API_APP_SECRET" environment variable for your AppSecret')

mc_servers = os.getenv("MC_SERVERS")
if mc_servers is None:
    raise Exception('Missing "MC_SERVERS" environment variable for your bot MC_SERVERS')

mc_mcsrvstat_servers = os.getenv("MC_MCSRVSTAT_SERVERS", "")

ecust_api_key = os.getenv("ECUST_API_Key")
if ecust_api_key is None:
    raise Exception('Missing "ECUST_API_Key" environment variable for your bot ECUST_API_Key')

ecust_url = os.getenv("ECUST_URL")
if ecust_url is None:
    raise Exception('Missing "ECUST_URL" environment variable for your bot ECUST_URL')

ecust_model = os.getenv("ECUST_MODEL", "MiniMax-M2.5")

# 注：早期还有 CLAWDBOT_URL / CLAWDBOT_API_Key 指向另一个网关（模型名写死 clawdbot），
# 那个模型早已下线（newapi 上不存在，调用必 503），相关配置已删除，一律走 ECUST_*。

tjit_key= os.getenv("TJIT_KEY")
if tjit_key is None:
    raise Exception('Missing "TJIT_KEY" environment variable for your bot TJIT_KEY')

mc_rcon_password= os.getenv("MC_KEY")
if mc_rcon_password is None:
    raise Exception('Missing "MC_KEY" environment variable for your bot MC_KEY')

mc_server = os.getenv("MC_SERVER")
if mc_server is None:
    raise Exception('Missing "MC_SERVER" environment variable for your bot MC_SERVER')

mc_rcon_port = os.getenv("MC_RCON_PORT")
if mc_rcon_port is None:
    raise Exception('Missing "MC_RCON_PORT" environment variable for your bot MC_RCON_PORT')

# 三角洲行动API配置
deltaforce_api_token = os.getenv("DELTAFORCE_API_TOKEN")
if deltaforce_api_token is None:
    raise Exception('Missing "DELTAFORCE_API_TOKEN" environment variable for Delta Force API')

# 查询空教室API配置
class_api_token = os.getenv("CLASS_API_KEY")
if class_api_token is None:
    raise Exception('Missing "CLASS_API_KEY" environment variable for CLASS_API_KEY')

# AI功能开关配置
ai_group_enabled = os.getenv("AI_GROUP_ENABLED", "false").lower() == "true"
ai_direct_enabled = os.getenv("AI_DIRECT_ENABLED", "false").lower() == "true"

# ---------------------------------------------------------------------------
# 校园问答：腾讯乐享知识库（https://lexiang.tencent.com/wiki/api/）
# 用于「默认 @ 机器人时回答学校相关问题」，未配置凭据时该功能自动关闭
# ---------------------------------------------------------------------------
# 「苏群新生指南」知识库的 space id（已用 GET /cgi-bin/v1/kb/spaces/<id> 核实：
# name=苏群新生指南，团队 c1aade5abfcf11f182f47612c9e9ccf7，根节点 e3d62e27014441e5bfb1ac255cb07166）
# 用它做 targets 可以把检索严格限制在这个知识库内
DEFAULT_CAMPUS_KB_SPACE_ID = "19e383358f904015bf1eb3101b2ad332"

lexiang_app_key = os.getenv("LEXIANG_APP_KEY", "")
lexiang_app_secret = os.getenv("LEXIANG_APP_SECRET", "")
lexiang_base_url = os.getenv("LEXIANG_BASE_URL", "https://lxapi.lexiangla.com")
# x-staff-id：传 system-bot 表示匿名调用，只能读到「公开」知识
lexiang_staff_id = os.getenv("LEXIANG_STAFF_ID", "system-bot")
# 问答模式：normal(快) / normal-hy3 / normal-ds-v4-flash / reasoning-hy3(深度思考，慢)
lexiang_qa_mode = os.getenv("LEXIANG_QA_MODE", "normal")
# 知识范围，格式 "space:xxx,team:yyy,kb_entry:zzz"
# 默认只查「苏群新生指南」，避免检索跑到授权范围内的其他知识库
lexiang_targets = os.getenv(
    "LEXIANG_TARGETS", f"space:{DEFAULT_CAMPUS_KB_SPACE_ID}"
).strip()

# 校园问答总开关（缺凭据时强制关闭）
campus_qa_requested = os.getenv("CAMPUS_QA_ENABLED", "false").lower() == "true"
campus_qa_enabled = (
    campus_qa_requested and bool(lexiang_app_key) and bool(lexiang_app_secret)
)
# 消息路由（判断「找群 / 查知识库 / 走 AI 对话」）用**独立**的一套配置：
# 不能和 /ai、/model 共用 —— /model 会在运行时改 ECUST_MODEL 并写回 .env，
# 路由跟着变就会莫名其妙地换模型（推理型模型还会把 max_tokens 花在思考上）。
# 三个都不配时退回 ECUST_* ，保证开箱可用。
router_api_key = os.getenv("ROUTER_API_KEY", "").strip() or ecust_api_key
router_url = os.getenv("ROUTER_URL", "").strip() or ecust_url
router_model = os.getenv("ROUTER_MODEL", "").strip()
router_timeout = float(os.getenv("ROUTER_TIMEOUT", "10") or 10)

# 飞书配置
feishu_app_id = os.getenv("FEISHU_APP_ID")
feishu_app_secret = os.getenv("FEISHU_APP_SECRET")

# 春节期间运势增强功能开关
spring_festival_enabled = os.getenv("SPRING_FESTIVAL_ENABLED", "false").lower() == "true"

# MC投票API配置
mcvote_api_url = os.getenv("MCVOTE_API_URL")
mcvote_api_token = os.getenv("MCVOTE_API_TOKEN")

# 窥屏检测配置
peek_image_url = os.getenv("PEEK_IMAGE_URL", "https://qqbot.bestzyq.cn/bear.jpg")
peek_nginx_log = os.getenv("PEEK_NGINX_LOG", "/www/wwwlogs/qqbot.bestzyq.cn.log")

# 全量消息调试开关：开启后把每条被忽略的全量消息也打成 WARNING
full_message_debug = os.getenv("FULL_MESSAGE_DEBUG", "false").lower() == "true"
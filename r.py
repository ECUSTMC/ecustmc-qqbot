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

clawdbot_url = os.getenv("CLAWDBOT_URL")
if clawdbot_url is None:
    raise Exception('Missing "CLAWDBOT_URL" environment variable for your bot CLAWDBOT_URL')

clawdbot_api_key = os.getenv("CLAWDBOT_API_Key")
if clawdbot_api_key is None:
    raise Exception('Missing "CLAWDBOT_API_Key" environment variable for your bot CLAWDBOT_API_Key')

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

# AI图片处理配置
image_save_dir = os.getenv("IMAGE_SAVE_DIR")
if image_save_dir is None:
    raise Exception('Missing "IMAGE_SAVE_DIR" environment variable for AI image save directory')

image_base_url = os.getenv("IMAGE_BASE_URL")
if image_base_url is None:
    raise Exception('Missing "IMAGE_BASE_URL" environment variable for AI image base URL')

# 春节期间运势增强功能开关
spring_festival_enabled = os.getenv("SPRING_FESTIVAL_ENABLED", "false").lower() == "true"
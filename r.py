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

deepseek_api_key = os.getenv("DeepSeek_API_Key")
if deepseek_api_key is None:
    raise Exception('Missing "DeepSeek_API_Key" environment variable for your bot DeepSeek_API_Key')

# DeepSeek模型特定配置
deepseek_chat_api_key = os.getenv("deepseek_chat_api_key")
if deepseek_chat_api_key is None:
    raise Exception('Missing "deepseek_chat_api_key" environment variable')

deepseek_chat_url = os.getenv("deepseek_chat_url")  
if deepseek_chat_url is None:
    raise Exception('Missing "deepseek_chat_url" environment variable')

deepseek_reasoner_api_key = os.getenv("deepseek_reasoner_api_key")
if deepseek_reasoner_api_key is None:
    raise Exception('Missing "deepseek_reasoner_api_key" environment variable')

deepseek_reasoner_url = os.getenv("deepseek_reasoner_url")
if deepseek_reasoner_url is None:
    raise Exception('Missing "deepseek_reasoner_url" environment variable')

baidu_url = os.getenv("Baidu_URL")
if baidu_url is None:
    raise Exception('Missing "baidu_url" environment variable for your bot baidu_url')

baidu_api_key = os.getenv("Baidu_API_Key")
if baidu_api_key is None:
    raise Exception('Missing "Baidu_API_Key" environment variable for your bot Baidu_API_Key')

ecust_api_key = os.getenv("ECUST_API_Key")
if ecust_api_key is None:
    raise Exception('Missing "ECUST_API_Key" environment variable for your bot ECUST_API_Key')

ecust_url = os.getenv("ECUST_URL")
if ecust_url is None:
    raise Exception('Missing "ECUST_URL" environment variable for your bot ECUST_URL')

ecust_model = os.getenv("ECUST_MODEL")
if ecust_model is None:
    raise Exception('Missing "ECUST_MODEL" environment variable for your bot ecust_model')

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
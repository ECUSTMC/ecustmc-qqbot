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
if weather_api_token is None:
    raise Exception('Missing "API_APP_ID" environment variable for your AppSecret')

api_app_secret = os.getenv("API_APP_SECRET")
if weather_api_token is None:
    raise Exception('Missing "API_APP_SECRET" environment variable for your AppSecret')

mc_servers = os.getenv("MC_SERVERS")
if appid is None:
    raise Exception('Missing "MC_SERVERS" environment variable for your bot MC_SERVERS')

qianfan_access_key = os.getenv("QIANFAN_ACCESS_KEY")
if appid is None:
    raise Exception('Missing "QIANFAN_ACCESS_KEY" environment variable for your bot QIANFAN_ACCESS_KEY')

qianfan_secret_key = os.getenv("QIANFAN_SECRET_KEY")
if appid is None:
    raise Exception('Missing "QIANFAN_SECRET_KEY" environment variable for your bot QIANFAN_SECRET_KEY')

deepseek_api_key = os.getenv("DeepSeek_API_Key")
if appid is None:
    raise Exception('Missing "DeepSeek_API_Key" environment variable for your bot DeepSeek_API_Key')
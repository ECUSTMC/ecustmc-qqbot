"""AI相关处理器"""
from openai import OpenAI
from botpy import BotAPI
from botpy.ext.command_util import Commands
from botpy.message import GroupMessage
from config import BAIDU_API_KEY


@Commands("/dsr")
async def query_deepseek_r1(api: BotAPI, message: GroupMessage, params=None):
    user_input = "".join(params) if params else "你好"

    try:
        # 使用 OpenAI 类初始化客户端
        client = OpenAI(api_key=BAIDU_API_KEY, base_url="http://oneapi.ecustvr.top/v1/")

        # 调用大模型
        completion = client.chat.completions.create(
            model="deepseek-reasoner",
            messages=[
                {
                    "role": "user",
                    "content": user_input,
                },
            ],
            temperature=0.3,
        )

        # 提取并发送模型响应
        model_reasoning_content = completion.choices[0].message.reasoning_content
        model_response = completion.choices[0].message.content
        await message.reply(content=f"Deepseek-Reasoner:\n推理：\n{model_reasoning_content}\n回复：\n{model_response}")

    except Exception as e:
        # 错误处理
        await message.reply(content=f"调用 Deepseek-Reasoner 大模型时出错: {str(e)}")

    return True


@Commands("/dsc")
async def query_deepseek_chat(api: BotAPI, message: GroupMessage, params=None):
    user_input = "".join(params) if params else "你好"

    try:
        # 使用 OpenAI 类初始化客户端
        client = OpenAI(api_key=BAIDU_API_KEY, base_url="http://oneapi.ecustvr.top/v1/")

        # 调用大模型
        completion = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {
                    "role": "user",
                    "content": user_input,
                },
            ],
            temperature=0.3,
        )

        # 提取并发送模型响应
        model_response = completion.choices[0].message.content
        await message.reply(content=f"Deepseek-Chat:\n{model_response}")

    except Exception as e:
        # 错误处理
        await message.reply(content=f"调用 Deepseek-Chat 大模型时出错: {str(e)}")

    return True
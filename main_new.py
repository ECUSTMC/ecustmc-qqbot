"""
重构后的主入口文件
这个文件替代原来的 main.py，提供更清晰的模块化结构
"""
from bot_client import main
import asyncio

if __name__ == "__main__":
    asyncio.run(main())
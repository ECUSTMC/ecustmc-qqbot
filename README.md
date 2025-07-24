# ECUST Minecraft QQ Bot 重构说明

## 项目结构

原来的 `main.py` 文件已经被拆分成以下模块化结构：

```
ecustmc-qqbot/
├── config.py                    # 配置管理模块
├── bot_client.py                # 机器人客户端主逻辑
├── main_new.py                  # 新的主入口文件
├── utils/                       # 工具模块
│   ├── database.py             # 数据库操作工具
│   └── network.py              # 网络工具函数
└── handlers/                    # 命令处理器模块
    ├── weather.py              # 天气查询处理器
    ├── server.py               # 服务器状态管理处理器
    ├── daily.py                # 每日内容处理器（一言、黄历）
    ├── fortune.py              # 运势相关处理器（人品、运势、塔罗牌、求签）
    ├── network_tools.py        # 网络工具处理器（IP查询、ping等）
    ├── minecraft.py            # Minecraft服务器命令处理器
    ├── entertainment.py        # 娱乐功能处理器（表情包等）
    ├── ai.py                   # AI相关处理器
    ├── group_management.py     # 群组管理处理器
    └── help.py                 # 帮助和工具处理器
```

## 模块说明

### 1. config.py
- 统一管理所有配置项
- 从 `r.py` 模块导入配置
- 提供清晰的配置接口

### 2. utils/ 工具模块
- **database.py**: 数据库操作相关函数，包括用户运势数据管理
- **network.py**: 网络工具函数，包括IP检查、域名解析、飞书API等

### 3. handlers/ 处理器模块
每个处理器模块负责特定功能的命令处理：

- **weather.py**: `/校园天气` 命令
- **server.py**: `/服务器状态`、`/添加服务器`、`/移除服务器`、`/status` 命令
- **daily.py**: `/一言`、`/今日黄历` 命令
- **fortune.py**: `/今日人品`、`/今日运势`、`/塔罗牌`、`/求签` 命令
- **network_tools.py**: `/ip`、`/nslookup`、`/ping` 命令
- **minecraft.py**: `/mc` 命令
- **entertainment.py**: `vv` 命令
- **ai.py**: `/dsr` 命令
- **group_management.py**: `/找群` 命令和群组查找功能
- **help.py**: `/帮助`、`/wiki` 命令

### 4. bot_client.py
- 机器人客户端主逻辑
- 事件处理（消息、群组管理等）
- 统一导入所有处理器

### 5. main_new.py
- 新的主入口文件
- 简洁的启动逻辑

## 重构优势

1. **模块化**: 每个功能模块独立，便于维护和扩展
2. **可读性**: 代码结构清晰，功能分离明确
3. **可维护性**: 修改某个功能时只需要关注对应的模块
4. **可扩展性**: 添加新功能时只需要创建新的处理器模块
5. **代码复用**: 公共工具函数提取到utils模块中

## 使用方法

1. 将原来的 `main.py` 重命名为 `main_old.py` 作为备份
2. 使用 `main_new.py` 作为新的启动文件：
   ```bash
   python main_new.py
   ```

## 注意事项

- 所有原有功能保持不变
- 配置文件 `r.py` 仍然需要存在
- 数据文件（如 `jrys.json`、`Tarots.json` 等）路径保持不变
- 依赖包保持不变

## 后续优化建议

1. 可以考虑将数据文件移动到 `data/` 目录
2. 可以添加日志配置模块
3. 可以添加错误处理中间件
4. 可以考虑使用配置文件替代硬编码的配置项
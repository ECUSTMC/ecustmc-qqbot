# ECUST Minecraft QQ Bot

华东理工大学 Minecraft 社团 QQ 机器人，基于 [botpy](https://github.com/tencent-connect/botpy) 开发。

## 项目结构

```
ecustmc-qqbot/
├── main_new.py                  # 主入口
├── bot_client.py                # 机器人客户端主逻辑
├── config.py                    # 配置管理模块
├── r.py                         # 环境变量配置（从 .env 读取）
├── utils/                       # 工具模块
│   ├── database.py             # 数据库操作工具
│   ├── network.py              # 网络工具函数
│   ├── group_message_patch.py  # 群消息「全量模式」SDK 补丁
│   └── group_trigger.py        # 群聊触发判定与消息去重
└── handlers/                    # 命令处理器模块
    ├── ai.py                   # AI 对话、模型切换
    ├── bus.py                  # 校车查询
    ├── classroom.py            # 空教室查询
    ├── daily.py                # 一言、黄历、通知
    ├── entertainment.py        # 表情包、三角洲密码
    ├── fortune.py              # 人品、运势、塔罗牌、求签
    ├── group_management.py     # 群组查找
    ├── help.py                 # 帮助、Wiki
    ├── minecraft.py            # MC 服务器命令
    ├── network_tools.py        # IP 查询、ping、nslookup
    ├── server.py               # 服务器状态管理
    ├── vote.py                 # 整合包投票
    ├── authorize.py            # 群主授权引导
    └── weather.py              # 天气查询
```

## 支持的命令

| 分类 | 命令 | 说明 |
|------|------|------|
| 天气 | `/校园天气` | 查询奉贤/徐汇校区天气 |
| 服务器 | `/服务器状态` `/status` `/添加服务器` `/移除服务器` | MC 服务器管理 |
| 每日 | `/一言` `/今日黄历` `/今日人品` `/今日运势` `/通知` | 每日内容与通知 |
| 娱乐 | `/塔罗牌` `/求签` `vv` `/三角洲密码` | 娱乐功能 |
| 网络工具 | `/ip` `/nslookup` `/ping` | 网络诊断 |
| Minecraft | `/mc` | 服务器 RCON 命令 |
| 投票 | `/vote` `/vote add` | 整合包投票列表、添加整合包 |
| AI | `/ai` `/model` `/models` | AI 对话与模型管理 |
| 校园 | `/校车` `/空教室` | 校车时刻表、空教室查询 |
| 群组 | `/找群` | 搜索群组 |
| 授权 | `/授权` | 查看「接收所有消息」群主授权指引 |
| 帮助 | `/帮助` `/wiki` | 帮助信息 |

## 环境准备

1. 安装依赖：
   ```bash
   pip install -r requirements.txt
   ```

2. 配置 `.env` 文件（参考 `r.py` 中的变量名），填入以下必要配置项：
   - `appid` / `secret`：QQ 机器人凭据
   - `weather_api_token`：高德天气 API Key
   - `api_app_id` / `api_app_secret`：黄历 API 凭据
   - `mc_servers`：MC 服务器地址列表（逗号分隔）
   - `mc_server` / `mc_rcon_port` / `mc_rcon_password`：RCON 配置
   - `mcvote_api_url` / `mcvote_api_token`：整合包投票 API 配置
   - `baidu_api_key`：AI 对话 API Key
   - 其他可选配置见 `config.py`

## 启动方式

```bash
python main_new.py
```

## 模块说明

### handlers/ 处理器模块

每个处理器模块负责特定功能的命令处理：

- **ai.py**：`/ai` AI 对话（支持多模态图片输入）、`/model` 模型切换、`/models` 模型列表
- **bus.py**：`/校车` 校车时刻表查询（徐汇↔奉贤双向）
- **classroom.py**：`/空教室` 按教学楼、楼层、时间段查询空教室
- **daily.py**：`/一言` `/今日黄历` `/通知`
- **entertainment.py**：`vv` 表情包、`/三角洲密码`
- **fortune.py**：`/今日人品` `/今日运势` `/塔罗牌` `/求签`
- **group_management.py**：`/找群` 群组搜索（联动飞书数据）
- **help.py**：`/帮助` `/wiki`
- **minecraft.py**：`/mc` MC 服务器 RCON 命令（支持交互式按钮）
- **network_tools.py**：`/ip` `/nslookup` `/ping`
- **server.py**：`/服务器状态` `/status` `/添加服务器` `/移除服务器`
- **vote.py**：`/vote` 整合包投票列表（支持分页、按钮投票）、`/vote add` 添加整合包
- **weather.py**：`/校园天气`

### utils/ 工具模块

- **database.py**：数据库操作相关函数，包括用户运势数据管理
- **network.py**：网络工具函数，包括 IP 检查、域名解析、飞书 API 等

### config.py

统一管理所有配置项，从 `r.py` 模块导入配置，提供清晰的配置接口。

## 重构优势

1. **模块化**：每个功能模块独立，便于维护和扩展
2. **可读性**：代码结构清晰，功能分离明确
3. **可维护性**：修改某个功能时只需要关注对应的模块
4. **可扩展性**：添加新功能时只需要创建新的处理器模块
5. **代码复用**：公共工具函数提取到 utils 模块中

## 注意事项

- `.env` 文件包含所有 API Key 和凭据，已加入 `.gitignore`，请勿提交到公开仓库
- 数据文件（如 `jrys.json`、`Tarots.json`、`bus_schedule_*.json` 等）需要保持最新
- 依赖包版本见 `requirements.txt`


## 群消息「全量模式」（接收所有消息）

机器人默认只能收到 **@它** 的消息。QQ 开放平台支持在群内开启「接收所有消息」，
开启后群里的每条消息都会通过 `GROUP_MESSAGE_CREATE` 事件推送。

### 如何在群里触发授权

群主 / 管理员无法通过指令直接授权（平台限制，必须手动点），流程是：

1. 在群里 **@机器人** 并发送 `/授权`
2. 机器人回复操作指引卡片
3. 群主在 QQ 客户端 → 群设置 → **群机器人** → 本机器人资料页
   打开「**接收所有消息**」并点击「同意」
4. 平台回调 `GROUP_MSG_RECEIVE` 事件，机器人在群里回执 ✅

授权 **按群独立**，每个群都要单独开一次。关掉时回调 `GROUP_MSG_REJECT`。

> 找不到开关通常是平台还没对该机器人开放此能力（部分机器人需要企业主体认证）。

### 实现要点

`qq-botpy` 1.2.1 之后未再更新，不认识 `GROUP_MESSAGE_CREATE`，事件会被静默丢弃：

- `utils/group_message_patch.py`：在 Client 实例化 **之前** 补齐 parser，
  并增强 `GroupMessage` 字段解析（`member_role` / `message_type` /
  `message_scene` / `msg_elements` / `ark_data`）。
- `utils/group_trigger.py`：全量模式下只响应 `/` 前缀指令与白名单关键词，
  其余静默丢弃，避免「群里聊到 vv」被误触发。

### 行为约定

| 事件 | 响应条件 |
|------|----------|
| `GROUP_AT_MESSAGE_CREATE`（@机器人） | 保持原有行为，未命中指令时走兜底 |
| `GROUP_MESSAGE_CREATE`（全量） | **仅** `/` 前缀指令或 `vv`，其余静默；不走兜底（不扫群、不触发 AI） |

另外全量消息按 `msg_id` 去重（官方提示同一 `msg_id` 可能重复推送）。

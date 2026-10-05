# ECUST Minecraft QQ Bot

华东理工大学 Minecraft 社团 QQ 机器人，基于 [botpy](https://github.com/tencent-connect/botpy) 开发。

功能：校园天气、校车/空教室查询、MC 服务器状态与 RCON 管理、整合包投票、AI 对话、
每日人品运势、表情包与娱乐指令，以及**默认 @ 的三分支兜底**（找群 / 校园问答 / AI 对话）。

> 📖 本文只讲「这是什么、怎么跑起来」。功能细节、配置项、排障都在
> **[ADVANCED.md](ADVANCED.md)**：默认 @ 的路由流程、只发可信群、知识库配图、
> 路由模型与内外网 newapi、乐享接口速查、全量模式、`msg_seq` 去重等。

## 项目结构

```
ecustmc-qqbot/
├── main_new.py                  # 主入口
├── bot_client.py                # 机器人客户端主逻辑
├── selfcheck.py                 # 离线自检（无需联网、无需 QQ 凭据）
├── config.py                    # 配置管理模块
├── r.py                         # 环境变量配置（从 .env 读取）
├── ADVANCED.md                  # 进阶说明：路由 / 找群 / 校园问答 / 全量模式
├── utils/                       # 工具模块
│   ├── database.py              # 数据库操作工具
│   ├── intent.py                # 「找群 / 校园问答」意图判定（纯规则）
│   ├── router.py                # 路由大模型：决定发群还是查知识库
│   ├── lexiang_client.py        # 腾讯乐享知识库 OpenAPI 客户端
│   ├── network.py               # 网络工具函数
│   ├── reply.py                 # safe_reply：回复失败只记日志不抛异常
│   ├── reply_seq.py             # 回复 msg_seq 自动递增补丁（40054005 去重）
│   ├── group_message_patch.py   # 群消息「全量模式」SDK 补丁
│   └── group_trigger.py         # 群聊触发判定与消息去重
├── tests/fixtures/
│   └── feishu_groups.json       # 真实飞书群表快照（119 个群，含「是否可信」标记）
└── handlers/                    # 命令处理器模块
    ├── ai.py                    # AI 对话、模型切换
    ├── bus.py                   # 校车查询
    ├── classroom.py             # 空教室查询
    ├── daily.py                 # 一言、黄历、通知
    ├── entertainment.py         # 表情包、三角洲密码
    ├── fortune.py               # 人品、运势、塔罗牌、求签
    ├── group_management.py      # 群组查找（飞书群表）
    ├── help.py                  # 帮助、Wiki
    ├── kb_qa.py                 # 校园问答（乐享知识库）+ 默认 @ 的兜底路由
    ├── minecraft.py             # MC 服务器命令
    ├── network_tools.py         # IP 查询、ping、nslookup
    ├── server.py                # 服务器状态管理
    ├── vote.py                  # 整合包投票
    ├── authorize.py             # 群主授权引导
    └── weather.py               # 天气查询
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
| 校园问答 | `/问答 <问题>` | 基于乐享知识库回答学校相关的问题（转专业、宿舍、军训…） |
| 授权 | `/授权` | 查看「接收所有消息」群主授权指引 |
| 身份/权限 | `/我的id` `/权限` | 查看自己的 openid 与群内身份、当前指令权限 |
| 帮助 | `/帮助` `/wiki` | 帮助信息 |

指令权限（谁能用哪些指令）：

| 指令 | 谁能用 | 怎么判定 |
|------|--------|----------|
| `/model` `/models` | 机器人管理员 | `.env` 的 `ADMIN_OPENIDS`（openid 白名单，逗号分隔） |
| `/添加服务器` `/移除服务器` | 本群群主 / 管理员 | 平台下发的 `member_role` = `owner`/`admin` |

两者都是**取不到身份就拒绝**（fail closed）；`ADMIN_OPENIDS` 留空时管理员指令对所有人都拒绝。
配置方法：先发 `/我的id` 拿到自己的 openid，填进 `.env` 后重启。详见
[ADVANCED.md](ADVANCED.md#指令权限谁能用哪些指令)。

## 环境准备

1. 安装依赖：

   ```bash
   pip install -r requirements.txt
   ```

2. 配置 `.env`（可参考 `.env.example`，变量名以 `r.py` 为准）：

   - `QQBOT_APP_ID` / `QQBOT_APP_SECRET`：QQ 机器人凭据
   - `WEATHER_API_TOKEN`：高德天气 API Key
   - `API_APP_ID` / `API_APP_SECRET`：黄历 API 凭据
   - `ECUST_API_Key` / `ECUST_URL` / `ECUST_MODEL`：AI 对话（`/ai`，以及默认 @ 的 AI 兜底）
   - `MC_SERVERS`：MC 服务器地址列表（逗号分隔）
   - `MC_SERVER` / `MC_RCON_PORT` / `MC_KEY`：RCON 配置
   - `MCVOTE_API_URL` / `MCVOTE_API_TOKEN`：整合包投票 API 配置
   - `FEISHU_APP_ID` / `FEISHU_APP_SECRET`：飞书群表（找群）
   - `LEXIANG_APP_KEY` / `LEXIANG_APP_SECRET` / `LEXIANG_TARGETS` / `CAMPUS_QA_ENABLED`：校园问答（乐享知识库）
   - `ROUTER_API_KEY` / `ROUTER_URL` / `ROUTER_MODEL` / `AI_GROUP_ENABLED` / `AI_DIRECT_ENABLED`：默认 @ 的兜底路由，见 [ADVANCED.md](ADVANCED.md#校园问答配置项)

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
- **kb_qa.py**：`/问答` 校园问答（乐享知识库）+ 默认 @ 的「找群 / 问答」兜底路由
- **minecraft.py**：`/mc` MC 服务器 RCON 命令（支持交互式按钮）
- **network_tools.py**：`/ip` `/nslookup` `/ping`
- **server.py**：`/服务器状态` `/status` `/添加服务器` `/移除服务器`
- **vote.py**：`/vote` 整合包投票列表（支持分页、按钮投票）、`/vote add` 添加整合包
- **weather.py**：`/校园天气`

### utils/ 工具模块

- **database.py**：数据库操作相关函数，包括用户运势数据管理
- **network.py**：网络工具函数，包括 IP 检查、域名解析、飞书 API 等
- **intent.py**：找群 / 提问的意图判定与群关键词提取（纯规则，可离线自检）
- **router.py**：路由大模型（`ROUTER_*`），判断该发群结果还是查知识库；失败自动熔断并降级为规则
- **lexiang_client.py**：腾讯乐享知识库 OpenAPI 客户端（AI 问答、知识库详情、targets 核实）

### config.py

统一管理所有配置项，从 `r.py` 模块导入配置，提供清晰的配置接口。

## 默认 @ 机器人

被 **@**（或私聊）且没命中任何指令时，机器人会**先拿这句话去飞书群表搜一遍**
（群友常只丢一个「王者荣耀」「三角洲」），然后：

1. **明确在找群**（「有没有XX群」）→ 有结果就发结果、没有就说没找到（不花大模型调用）；
2. 其余交给路由大模型判断，三种走向：**只发群结果** / **查校园知识库**
   （答案 + 引用来源，正文里的插图按 QQ markdown 语法内嵌在同一条卡片里）/
   **用已有的 `/ai` 对话回复**；
3. 大模型不可用时自动降级为规则判断，并熔断 60 秒。

```
@机器人 转专业怎么申请  → 查知识库（《2026学生手册》等来源）
@机器人 有没有计算机群  → 直接发群结果
@机器人 今天天气怎么样  → 交给 /ai 对话
```

完整流程、真机联调耗时、只发「可信」群、路由模型与内外网 newapi、
找群匹配规则、乐享接口速查与排障：**[ADVANCED.md](ADVANCED.md#默认--机器人先搜群再决定发群--查知识库--走-ai-对话)**。

## 群消息「全量模式」

群主可在群内为机器人开启「接收所有消息」，开启后群里每条消息都会推送过来。
本项目把全量模式的钱只花在**明确召唤**上：

- **@机器人** → 和 @事件 完全一致，走完整兜底（找群 → 校园问答 → AI 对话）；
- **明确的找群句式**（`有没有XX群` / `找XX群` / `拉我进群` / `群号`，不 @ 也响应）
  与 `/` 指令、`vv` → 只走零成本路径（/ 指令、带缓存的群表查询）；
- **其余闲聊** → 一律静默，绝不主动调用大模型或知识库（群里逐条自动回答会持续烧钱并撞限频）。

授权方法、触发规则、`msg_seq` 去重与「@机器人 没反应」的排查：
**[ADVANCED.md](ADVANCED.md#群消息全量模式接收所有消息)**。

## 注意事项

- `.env` 文件包含所有 API Key 和凭据，已加入 `.gitignore`，请勿提交到公开仓库
- 数据文件（如 `jrys.json`、`Tarots.json`、`bus_schedule_*.json` 等）需要保持最新
- 依赖包版本见 `requirements.txt`
- 改完代码建议跑一次离线自检（不需要网络与 QQ 凭据）：

  ```bash
  python selfcheck.py          # 全部自检通过
  ```

## 重构优势

1. **模块化**：每个功能模块独立，便于维护和扩展
2. **可读性**：代码结构清晰，功能分离明确
3. **可维护性**：修改某个功能时只需要关注对应的模块
4. **可扩展性**：添加新功能时只需要创建新的处理器模块
5. **代码复用**：公共工具函数提取到 utils 模块中

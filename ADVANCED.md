# 进阶说明：默认 @ 路由 / 找群 / 校园问答 / 全量模式

[README.md](README.md) 只讲「这是什么、怎么跑起来」，本文放功能细节、配置项与排障。

- [默认 @ 机器人：先搜群，再决定「发群 / 查知识库 / 走 AI 对话」](#默认--机器人先搜群再决定发群--查知识库--走-ai-对话)
  - [只发「可信」的群](#只发可信的群)
  - [知识库的配图：直接内嵌在 markdown 卡片里](#知识库的配图直接内嵌在-markdown-卡片里)
  - [第三分支的 AI 对话用哪个模型（clawdbot 已删除）](#第三分支的ai-对话用哪个模型clawdbot-已删除)
  - [路由模型与「内外网两个 newapi」](#路由模型与内外网两个-newapi)
  - [找群匹配：关键词怎么来、怎么算命中](#找群匹配关键词怎么来怎么算命中)
  - [知识范围锁死在「苏群新生指南」](#知识范围锁死在苏群新生指南)
  - [为什么用乐享而不是 ima](#为什么用乐享而不是-ima)
  - [乐享接口速查](#乐享接口速查)
  - [校园问答配置项](#校园问答配置项)
  - [校园问答排障](#校园问答排障)
- [群消息「全量模式」（接收所有消息）](#群消息全量模式接收所有消息)
  - [如何在群里触发授权](#如何在群里触发授权)
  - [实现要点](#实现要点)
  - [行为约定](#行为约定)
  - [排障](#排障)
  - [离线自检](#离线自检)
- [指令权限（谁能用哪些指令）](#指令权限谁能用哪些指令)
  - [机器人管理员：ADMIN_OPENIDS 白名单](#机器人管理员admin_openids-白名单)
  - [群主 / 管理员：按平台 member_role](#群主--管理员按平台-member_role)
  - [加一条受保护的指令](#加一条受保护的指令)
- [服务器地址的 QQ 脱敏（可逆转义）](#服务器地址的-qq-脱敏可逆转义)

---

## 默认 @ 机器人：先搜群，再决定「发群 / 查知识库 / 走 AI 对话」

被 **@**（或私聊）但没命中任何指令时的行为：

```
@机器人 <消息>
   │
   ├─ ① 先拿这句话去飞书群表搜一遍
   │     （历史惯性：群友往往只丢一个"王者荣耀""三角洲"，而不是"找XX群"）
   │
   ├─ ② 明确在找群（"有没有XX群"）→ 有结果就发结果、没有就说没找到，
   │     两种都不花大模型调用
   │
   ├─ ③ 其余交给路由大模型判断：输入 = 用户原话 + 找群结果
   │     输出 = {"send_group": ?, "query_kb": ?}
   │       ├─ 搜到群 + 用户就是要这些群      → 只发群结果，结束
   │       ├─ 顺手还在问学校的事（"计算机专业保研难吗"）→ 发群 + 查知识库
   │       ├─ 问的是学校的事（"转专业怎么申请"）→ 查知识库（答案 + 引用来源）
   │       └─ 都不是（"今天天气怎么样""1+1"）→ 用**已有的 /ai 对话**回复
   │
   └─ ④ 大模型不可用（超时 / 代理挂了 / 返回解析不出来）→ 规则降级：
         找群意图或"裸词命中群表"→ 发群；像在提问**或命中「校园事」关键词**
         （`intent.is_campus_topic`：如何上网/信息服务/初始密码…，这些说法没有疑问词
         又不满 7 个字，只靠"长度≥7"会被误判成闲聊）→ 查知识库；其余 → /ai 对话
         并熔断 60 秒，避免每条消息都白等一次超时
```

提示词里给模型的「校园事」清单（`utils/router.py::_SYSTEM_PROMPT`）覆盖：
学业（转专业、保研、绩点、选课、考试、毕业…）、后勤（宿舍、食堂、军训、报到、校车、
校园卡、图书馆…）、资助（奖学金、助学金、医保报销…）、
**网络与信息服务**（如何上网、校园网/无线网络/宿舍网络、信息服务、信息门户、一站式平台、
VPN、邮箱、云盘、报修…）、**各类账号与初始密码**（统一身份认证、学号、邮箱、校园网账号的
初始密码/激活/忘记密码/重置…）。实测这几类在知识库里都有收录，来源如
《华东理工大学校内网络及信息系统常见问题（FAQ）》《无线网络》《eduroam》。

> 改动这份清单时要**两边一起改**：提示词负责正常路径，`intent._CAMPUS_TOPIC_WORDS`
> 负责大模型不可用时的降级路径（selfcheck 里两边都有断言）。

真机联调结果（真实飞书群表 + 真实乐享知识库 + 真实路由模型）：

| @机器人 说 | 路由判定 | 结果 | 耗时 |
|-----------|---------|------|------|
| `王者荣耀` | send_group | 华理王者荣耀丨华理爸爸会（626314374） | 3.7s |
| `三角洲` | send_group | 打洲社、乌冬理工鼠鼠聚集地 | 1.7s |
| `原神` | send_group | 花梨～空月之歌！ | 1.5s |
| `有没有计算机群` | 快速通道 | 4 个 CIC 计算机群 | 0.0s（群表缓存） |
| `转专业怎么申请` | query_kb | 答案 + 来源《2026学生手册》等 | 10.7s |
| `宿舍几点熄灯` | query_kb | 周日至四 23:00 熄灯… | 7.6s |
| `今天天气怎么样` | 都不做 | 交给 `/ai` 对话 | 1.4s |
| `1+1` | 都不做 | 交给 `/ai` 对话 | 1.5s |
| `如何上网` | query_kb | 校园无线网络 / ECUST.1x / 宿舍区网络… | — |
| `初始密码是什么` | query_kb | 统一身份认证 / 各类账号初始密码 | — |
| `信息服务都有啥` | query_kb | 信管中心：认证、一站式、校园卡、邮箱、云盘、VPN… | — |

关键词提取与「明确找群」判定在 `utils/intent.py`（纯规则、可离线自检），
路由在 `utils/router.py`，知识库问答与三分支实现在 `handlers/kb_qa.py`。

显式指令：`/找群 XX` 强制找群；`/问答 XX` 强制走知识库问答（都跳过路由）。

> 第三分支依赖已有的 AI 对话，需要在 `.env` 里开 `AI_GROUP_ENABLED=true`
> （私聊还要 `AI_DIRECT_ENABLED=true`），否则退化成一句功能提示。

### 第三分支的 AI 对话用哪个模型（clawdbot 已删除）

「既不是找群也不是校园问题」时走 `handlers/ai.py::group_chat_fallback`
（私聊 `direct_chat_fallback`），它们请求的就是 **`ECUST_MODEL`**（`.env` 里现在填的 `hy3`），
和 `/ai` 命令完全同一条路。

这里踩过一个坑：这两个函数原来叫 `group_chat_with_clawdbot` / `direct_chat_with_clawdbot`，
**写死**请求一个名叫 `clawdbot` 的模型（配置来自 `CLAWDBOT_URL` / `CLAWDBOT_API_Key`）。
但那个模型早已下线 —— `CLAWDBOT_URL` 被指到了和 `ECUST_URL` 同一个 newapi
（`http://newapi.ecustvr.top/v1`），而那台 newapi 的模型列表里**没有 `clawdbot`**：

```
@ECUSTMC 今天天气
→ 调用 clawdbot 模型时出错: Error code: 503 - model_not_found:
  No available channel for model clawdbot under group default (distributor)
```

以前 `AI_GROUP_ENABLED=false`，默认 @ 的兜底是找群、根本走不到 AI，所以这个坑一直没暴露。
现在整套 `clawdbot` 已经删掉：`MODEL_CONFIGS` 里不再有它，`r.py` 不再读那两个环境变量，
群聊/私聊与 `/ai` 一律用 `ECUST_MODEL`。

顺带修了两个体验问题：

* **失败不再把原始报错甩给群友**。`_call_ai_model` 现在返回 True/False
  （True = 已经给用户一个可见结果），并新增 `report_errors` 参数：
  `/ai` 这种显式命令仍然回「调用 X 模型时出错: …」方便排查，
  默认 @ 的隐式兜底传 `report_errors=False`，静默返回 False 后由兜底逻辑回一句正常话术。
* **输出审查（敏感信息检测）不再和模型名绑死**。原来写成 `if model_name == "clawdbot"`，
  等于这个安全审查只在那条 503 的死路上生效；现在改为只看 `audit_output` 开关，
  **默认关闭**（它每次都要额外调一次模型，而 `/ai` 从来就没审查过），
  需要时给 `_call_ai_model(..., audit_output=True)` 即可。

### 只发「可信」的群

飞书群表里有 `是否可信` 字段，**只有可信的群才会出现在回复里**：

* 拉取时请求体就带了 `是否可信 is true` 的过滤条件（原逻辑，保留）；
* `handlers/group_management.py::match_groups()` 再按 `trusted` 兜一层，
  群表快照/缓存/别的调用方塞进来的数据同样受保护；
* `tests/fixtures/feishu_groups.json` 保留了不可信样本（`PUNISHING ECUST高维观测中心`），
  自检会验证它**搜群名、搜群号都搜不出来**。

真机验证：搜 `战双帕弥什` / `高维观测` → 0 命中；搜 `原神` → 正常命中。

### 知识库的配图：直接内嵌在 markdown 卡片里

乐享的回答**本身就是 markdown**（`## 标题`、`**加粗**`、`- 列表`、`![说明](url)`），
QQ markdown 也支持图片，所以整条回答按 **`/塔罗牌` 那种发法**一次发出去：

```
![阳台等布局 #416px #472px](https://image-ai.lexiang-asset.com/…-resize1920?sign=…)
```

* 图片按 QQ 官方语法补上尺寸提示（`![说明 #宽px #高px](url)`）——
  发之前只取每张图**头部 4KB** 解析宽高（PNG/JPEG/GIF，见 `kb_qa.parse_image_size`），
  超过 `kb_qa.IMAGE_MAX_WIDTH = 600px` 的等比缩小；读不到尺寸就不带提示，不影响显示；
* 最多内嵌 `kb_qa.MAX_IMAGES = 3` 张（按出现顺序去重），超出部分删掉 ——
  乐享的签名链接一张约 500 字，全塞进去卡片会被撑爆；
* **截断只算纯文字**：`![…](…)` 标记永远完整保留，不会出现半截 URL（自检覆盖）；
* 官方文档明确"开放平台会下载转存该资源"，所以图会被 QQ 重新托管，
  乐享那边 7 天的签名过期也不影响已发出的消息；
* 正文里其余裸链接（非图片）会被清理，但 `![…](url)` / `[文字](url)` 里的链接不动。

顺带解决了一个坑：乐享还会把所有数字包进 `$…$`（公式 `$90\text{cm}\times39\text{cm}$`、
时间 `$23:00$`、分数 `$2-14$` 次 `$-0.5$` 分），QQ markdown 不渲染公式，
用户会看到一串 `\text{cm}\times` 和多余的 `$`。`kb_qa.latex_to_text()` 会拆掉定界符
并映射常见命令：`$90\text{cm}\times39\text{cm}$` → `90cm×39cm`、`$23:00$` → `23:00`、
`$\frac{1}{2}$` → `1/2`、`$x^{2}$` → `x²`。

> 早先试过「文字卡片 + `vv` 那套富媒体消息补发图」（`post_group_file` + `msg_type=7`，
> 好处是**会 @ 提问者**）。既然内容是 markdown，就改用更适配 markdown 的 `/塔罗牌` 方式，
> 一条消息搞定；代价是**不会额外 @ 提问者**。真要「用图片 @ 提问者」，
> 在 `answer_school_question` 里加一条 `api.post_group_file(file_type=1, url=…)`
> → `message.reply(msg_type=7, media=…)` 即可（约 20 行）。

### 路由模型与「内外网两个 newapi」

路由用**自己的一套**环境变量（刻意不与 `/ai`、`/model` 共用 ——
`/model` 会在运行时改写 `ECUST_MODEL` 并写回 `.env`，共用会让路由模型被悄悄换掉）：

```ini
ROUTER_API_KEY=…
ROUTER_URL=https://newapi.bestzyq.cn/v1
ROUTER_MODEL=gemini-3.5-flash-lite
ROUTER_TIMEOUT=10
```

三个都不配时会回退到 `ECUST_*`，保证开箱可用。

* **`ROUTER_URL`**：`newapi.ecustvr.top` 是校园**内网**地址，
  `newapi.bestzyq.cn` 是**外网**地址（同一个 newapi 实例，同一把 key）。
  机器人若跑在外网，`ECUST_URL` 那台内网代理是不通的，靠这行把路由指到外网入口。
* **`ROUTER_MODEL`**：实测 `hy3` 是推理型模型，一次要 ~800 token、3~8s，
  而且推理偶尔把额度用光、`finish_reason=length` 且 `content` 为空；
  换 `gemini-3.5-flash-lite` 后是 ~28 token、1.2s，判断质量相当
  （`qwen3.5` 则久到 100s 以上，不适合做路由）。推理型模型也能用，
  代码里 `max_tokens` 给到 800 就是为它留的。
* 解析上做了三层兜底：正常 JSON → 被截断的半个 JSON（正则直接抓两个布尔值）
  → 都不行才退回规则，并把模型原文打进日志，不会出现"看起来像配置问题"的静默降级。
* 代理连续失败会**熔断 60 秒**：期间直接用规则判断，不再每条消息都白等一次超时。

### 找群匹配：关键词怎么来、怎么算命中

* `match_groups()` 在**群名 + 描述**上做子串匹配（都做了小写化与去空格），
  所以真实群表里"描述"写的游戏别名才是关键：
  `三角洲行动/Delta Force`、`怪物猎人/怪猎/Monster Hunter/MH`、`妮姬/胜利女神新的希望/NIKKE`。
* `extract_group_keyword()` 负责把"有没有王者荣耀群"剥成 `王者荣耀`，
  剥词表只保留语气词/动词（"有没有""帮我""求个"…），标点交给正则统一处理——
  原来那张又长又没用的「新生|迎新|交流|老乡|社团…」群名前缀表已经删掉：
  真实群名五花八门（"乌冬理工鼠鼠聚集地""伊卡斯特龙历院"），前缀表盖不住；
  而"新生群""老乡群"这类整句本来就是群名，由「整句就是一个群名」那条规则兜住。
* `tests/fixtures/feishu_groups.json` 是导出的**真实群表快照（119 个群）**，
  自检直接拿它验证匹配：游戏/话题名能命中、校园提问一律 0 命中
  （否则"转专业申请"会被当成找群，就答不上学校的事了）。

### 知识范围锁死在「苏群新生指南」

`ai/qa` 支持 `targets` 限定检索范围，默认配置成只有这**一个**知识库，
避免检索跑到授权范围内的其他知识库：

```ini
LEXIANG_TARGETS=space:19e383358f904015bf1eb3101b2ad332
```

已用接口核实过这个 id：

```bash
GET https://lxapi.lexiangla.com/cgi-bin/v1/kb/spaces/19e383358f904015bf1eb3101b2ad332
# → {"data":{"id":"19e383358f904015bf1eb3101b2ad332","type":"kb_space",
#            "attributes":{"name":"苏群新生指南","description":"给新同学介绍学校信息"},
#            "relationships":{"team":{"data":{"id":"c1aade5abfcf11f182f47612c9e9ccf7"}},
#                             "root_entry":{"data":{"id":"e3d62e27014441e5bfb1ac255cb07166"}}}}}
```

启动时也会自动核实一次并打进日志：

```
校园问答知识库已核实: 苏群新生指南（space id=19e383358f904015bf1eb3101b2ad332，团队=c1aade5a…）
```

配上 `targets` 后 `ai/qa` 返回的 `answer_source` 为 `internal-space`（不限范围时是
`internal-team`），答案更聚焦。想放开范围就改 `LEXIANG_TARGETS`
（`space:<知识库ID>,team:<团队ID>,kb_entry:<节点ID>`，逗号分隔）。

### 为什么用乐享而不是 ima

ima 的 OpenAPI（官方 skill 包 `ima-skills-1.1.10.zip`）**只有知识库/笔记的增删查改**：

| 接口 | 用途 |
|------|------|
| `openapi/wiki/v1/get_knowledge_list` | 列出知识库条目 |
| `openapi/wiki/v1/get_media_info` | 取原文的签名下载链接 |
| `openapi/wiki/v1/search_knowledge` | 搜索（**只按标题/元数据命中，不搜正文**） |
| `openapi/wiki/v1/import_urls` / `add_knowledge` | 往知识库写内容 |

`openapi/wiki/v1/chat`、`/qa`、`/ai_search` 等问答类路径实测全部 **404**。
要用 ima 回答问题，只能自己「下载原文 → 解析 PDF/DOCX → 分块 → 本地检索 → 喂给大模型」，
而且扫描件/图片型 PDF 还得自己做 OCR（苏群知识库里
《转专业录取方案》《学籍管理条例》正是扫描件，实测提不出文字）。

腾讯乐享则直接提供 **AI 问答**接口（`POST /cgi-bin/v1/ai/qa`）：

* 乐享侧完成检索 + 大模型生成，返回 `data.content`（答案）与
  `additional_content.reference_docs`（引用来源）；
* 扫描件/图片由乐享侧解析（`imgParseSvr`），知识库内容更新后本仓库无需改代码；
* `x-staff-id: system-bot` 表示匿名调用，只读「公开」知识，适合群机器人。

因此回答引擎用乐享（`utils/lexiang_client.py`）。

### 乐享接口速查

| 事项 | 值 |
|------|-----|
| 获取令牌 | `POST https://lxapi.lexiangla.com/cgi-bin/token`，body `{"grant_type":"client_credentials","app_key":…,"app_secret":…}` |
| 令牌有效期 | `expires_in=7200` 秒，限 **20 次/10 分钟**，必须缓存（`LexiangClient` 进程内缓存并提前 5 分钟刷新） |
| AI 问答 | `POST /cgi-bin/v1/ai/qa`，header 带 `Authorization: Bearer <token>`、`x-staff-id: system-bot` |
| 请求体 | `{"query":…,"stream":false,"new_session":true,"qa_mode":"normal","targets":[{"type":"space","id":"…"}]}`（不设 `max_chars`，交给乐享默认，答案更完整） |
| 返回 | `{"code":0,"data":{"content":…,"answer_source":"internal-space","additional_content":{"reference_chunks":[…],"reference_docs":[{"title","url"}]}}}` |
| 答不出来 | `code=0`，但 `content` 固定为 `当前问题可能因内容未收录、解析中、权限受限或命中敏感词无法解答。` |
| 知识库详情 | `GET /cgi-bin/v1/kb/spaces/<space_id>`（核实知识库名字/团队/根节点） |
| AI 搜索 | `POST /cgi-bin/v1/ai/search`（返回 rerank 片段，本项目暂未使用） |
| 团队列表 | `GET /cgi-bin/v1/kb/teams` —— 本企业调用返回 `403 版本需升级后启用`，所以知识库 id 直接写死在上面的 `LEXIANG_TARGETS` 里 |
| 接口文档 | <https://lexiang.tencent.com/wiki/api/40000.html> |

### 校园问答配置项

```ini
LEXIANG_APP_KEY=...           # 乐享后台【开发】-【接口凭证管理】创建，并勾选「AI 助手」接口权限
LEXIANG_APP_SECRET=...
LEXIANG_STAFF_ID=system-bot   # 匿名身份，只能读「公开」知识
LEXIANG_QA_MODE=normal        # normal(快) / normal-hy3 / normal-ds-v4-flash / reasoning-hy3(深度思考，慢)
LEXIANG_TARGETS=space:19e383358f904015bf1eb3101b2ad332   # 只查「苏群新生指南」
CAMPUS_QA_ENABLED=true        # 总开关（缺凭据时自动关闭并在启动日志告警）

# 路由大模型：独立配置，不与 /ai、/model 共用（/model 会改 ECUST_MODEL 并写回 .env）
ROUTER_API_KEY=…
ROUTER_URL=https://newapi.bestzyq.cn/v1   # 外网入口；内网是 http://newapi.ecustvr.top/v1
ROUTER_MODEL=gemini-3.5-flash-lite
# ROUTER_TIMEOUT=10

# 「既不是找群也不是校园问题」时用已有的 /ai 对话回复（不开则回功能提示）
AI_GROUP_ENABLED=true
AI_DIRECT_ENABLED=true
```

### 校园问答排障

* 启动日志会打印 `默认回复规则: @我 → ①先搜一遍飞书群表 → ②由 … 判断…`
  以及核实到的知识库名字；若打印「校园问答未启用」说明 `CAMPUS_QA_ENABLED=false` 或凭据缺失。
* 日志里 `路由(ai)` 表示大模型判断成功，`路由(rule)` 表示走了规则降级 ——
  降级原因会紧跟一条日志：`路由模型调用失败…熔断 60s`（代理不通 / 超时）或
  `路由模型返回无法解析…`（会附上模型原文）。两条都说明检查 `ROUTER_URL` 与
  `ROUTER_MODEL`：内网 `newapi.ecustvr.top` 与外网 `newapi.bestzyq.cn` 要对上机器人的网络环境。
* `code=123 ai token quota exhausted`：乐享侧大模型配额用完，需要管理员在乐享后台处理
  （也可切换 `LEXIANG_QA_MODE`）。
* 回答里乐享图床的插图（签名 7 天有效、公网可访问）会按 QQ markdown 语法
  **内嵌在卡片里**（最多 3 张，超出删掉），QQ 侧会下载转存所以过期也不怕；
  卡片长度只按纯文字算，图片标记不会被截断。
* 知识库只覆盖学校的事：**没收录**时会交给已有的 `/ai` 对话（配了 `AI_GROUP_ENABLED` 时），
  所以"今天天气怎么样"最终也能答上来，而不是只回一句"没找到"。
* 看到 `调用 clawdbot 模型时出错: 503 … model_not_found` 的话，那是历史遗留
  （`clawdbot` 模型早已下线），现在整套已删除，见上文
  [第三分支的 AI 对话用哪个模型](#第三分支的ai-对话用哪个模型clawdbot-已删除)。
* 飞书群表有 5 分钟缓存（`handlers/group_management.py::_GROUPS_CACHE_TTL`），
  所以「先搜一遍群」几乎不增加耗时（实测首次 2.2s、命中缓存 0.00s）。

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
- `utils/group_trigger.py`：全量模式下只响应 `/` 前缀指令、白名单关键词、
  **明确 @ 了机器人**、以及**明确的找群句式**的消息，其余静默丢弃，
  避免「群里聊到 vv」「群里有人叫王者荣耀」被误触发。
- `utils/reply_seq.py`：回复时自动递增 `msg_seq`（见下文「消息被去重」）。

### 行为约定

| 事件 / 消息 | 响应条件与代价 |
|------|----------|
| `GROUP_AT_MESSAGE_CREATE`（@机器人） | 保持原有行为，未命中指令时走完整兜底（先搜群 → 路由 → 发群 / 查知识库 / AI 对话） |
| `GROUP_MESSAGE_CREATE` + **明确找群句式**（`有没有XX群` / `找XX群` / `拉我进群` / `群号`） | **零成本快速通道**：只搜一次带 5 分钟缓存的群表就回复，不调模型也不查知识库（不 @ 机器人也响应） |
| `GROUP_MESSAGE_CREATE` + `/` 指令、`vv` | 交给对应指令处理器（`/帮助`、`/找群`、`/问答`…） |
| `GROUP_MESSAGE_CREATE` + **@了机器人** | **按 @事件 对待**，走完整兜底：先搜群 → 路由模型判断 → 发群结果 / 查知识库 / 用 `ECUST_MODEL` 兜底对话 |
| `GROUP_MESSAGE_CREATE` + 其余（闲聊、没 @ 的裸词与提问） | 一律静默（不搜群、不调模型、不查知识库） |

> **全量模式的钱只花在「明确召唤」上**：群里每条消息都会推送过来，
> 逐条自动回答必然持续烧钱 + 撞限频，所以只有
> **@了机器人** 才走完整兜底（和 @事件 完全一致），
> **明确找群句式** 只走零成本的群表查询，其余全部静默。
> 想查知识库也可以直接 `/问答 你的问题`，或私聊机器人。

全量消息按 `msg_id` 去重（官方提示同一 `msg_id` 可能重复推送）。
**触发判定在去重之前**：被判定为「不响应」的全量消息不会占用 `msg_id`，
否则同一条消息随后再以 @事件 到达时会被误当成重复消息丢掉，
表现就是「群里 @机器人 反而没反应」。

### 排障

#### 40054005「消息被去重，请检查请求msgseq」

官方规则：**相同的 `msg_id + msg_seq` 重复发送会失败**，
同一条消息要多次回复必须递增 `msg_seq`；主动消息重复 `msg_seq` 同样会被判重。
而 `qq-botpy` 把 `msg_seq` 写死成默认值 `1`，所以只要一条消息回了两次
（错误兜底、先发回执再撤回、多段消息…）就必然报这个错。

修复：

- `utils/reply_seq.py` 在 `BotAPI.post_group_message` / `post_c2c_message`
  外层包了一层，按 `msg_id` / `event_id` / 会话自动分配递增序号，
  调用方显式传的 `msg_seq`（如 `peek_detect` 的 `msg_seq=2`）依然生效。
- 处理器若已经回复过用户，必须 `return True` 终止分发，不能返回 `False`/`None`，
  否则会继续走兜底、用同一个 `msg_id` 再回一条。
- 兜底回复统一走 `utils/reply.py::safe_reply`，失败只记日志，不再抛异常刷 traceback。

#### 「@机器人 没反应」

**关键坑**：全量模式（`GROUP_MESSAGE_CREATE`）下平台**不会**去掉「@机器人」前缀，
而是原样下发形如 `<@93C3B65BF2EE20F5A11FFB14EC18EF85> /通知 ` 的内容
（`content` 里带 `<@openid>` 占位符）。若只判断「是否以 `/` 开头」，
`@ECUSTMC /通知` 就永远不匹配、被静默丢弃 —— 这就是「@了没反应」的根因。

修复：`utils/group_trigger.py::strip_leading_mentions()` 会先剥掉开头的
`<@openid>` 占位符再判定 / 再交给处理器（正文里 @ 别人不受影响）。

@ 的识别还有一层坑：群事件里被 @ 的用户用 **openid**，而
`botpy.Client.robot.id` 是**数字 appid**（`robot.py` 里 `int(data["id"])`），
两者对不上，所以 `mentions` 与本机 id 无法直接比较。因此触发规则为：

1. 剥掉占位符后以 `/`、`／` 开头；
2. 剥掉占位符后命中白名单关键词（`vv`）；
3. `mentions` 里出现 `bot=true` 的条目（@ 了机器人，本群通常只有本机器人）；
4. `mentions` 命中调用方给出的候选 id（将来若能拿到机器人 openid 即可精确匹配）。

其余（含图片/卡片、只 @ 人无正文）静默丢弃，机器人（含自己）发的消息一律不响应，
避免全量模式下「机器人转述指令」形成自问自答的死循环。

判定通过之后还有第二道关卡（`bot_client.py::_dispatch_group_handlers`）：

- **明确找群句式** → 零成本快速通道（只查一次带缓存的群表）；
- **@了机器人** → 按 @事件 走完整兜底（搜群 → 路由 → 发群结果 / 查知识库 / AI 对话）；
- **其余** → 静默。

早期版本第二道关卡要求「必须是明确找群」，于是「@机器人 + 裸词」虽然通过了闸门，
随后仍被静默 —— 群友看到的就是「@了完全没反应」。现在 @ 与 @事件 同等待遇。

**日志级别提醒**：启动时的几条规则说明是 INFO，但 `bot_client.py` 里
`EcustmcClient(..., log_level=30)` 会把日志级别设成 WARNING，
所以运行期的 `_log.info` / `_log.debug`（含 `[全量消息] …`、`[默认回复] 路由(ai) …`、
`[校园问答] 命中 …`、`重复消息，已忽略`）**都看不到**。排查「@了没反应」时：
把 `FULL_MESSAGE_DEBUG=true` 打开可以看见**被闸门拒绝**的全量消息（WARNING 级），
若 @ 消息在这条日志里没出现，说明它过了闸门；想连运行期 INFO/DEBUG 一起看，
需要把 `log_level` 调成 20 或 10。

排查手段：

- 启动日志会打印「群聊触发规则」和 `on_ready` 的 `robot_id`；
- 把 `.env` 里的 `FULL_MESSAGE_DEBUG` 设为 `true`，被忽略的全量消息会打 WARNING，
  格式为 `content=... type=... author=... mentions=['93C3B65B(bot)']`
  —— 从 `(bot)` 标记就能看出平台有没有把机器人标成 `bot=true`。

### 离线自检

```bash
python3 selfcheck.py
```

不需要网络与 QQ 凭据，覆盖：`msg_seq` 递增、全量消息触发判定、
`msg_id` 去重、兜底回复不抛异常、找群关键词提取、兜底路由
（明确找群走快速通道 / 大模型判定 / 先发群再回答案 / 都不做走 AI 对话 /
知识库没收录交给 AI / 大模型 502 降级为规则）、全量模式只响应明确找群句式、
**用真实群表快照（119 个群）验证匹配、校园提问 0 误命中、不可信群搜不出来**、
**知识库配图：图片头部字节解析宽高 / 尺寸提示缩放 / 内嵌 markdown 卡片 /
上限与「按纯文字截断」/ LaTeX 转纯文本**、
**路由配置与 `/model` 解耦**、乐享答案清洗与引用解析、群表 TTL 缓存、
**指令权限（管理员白名单 / 群主管理员判定 / 被拒时未改配置）**。

---

## 指令权限（谁能用哪些指令）

实现在 `utils/permissions.py`，两种判定各管一类指令：

| 指令 | 判定方式 | 配置 |
|------|----------|------|
| `/model`、`/models` | 「机器人管理员」白名单 | `.env` 的 `ADMIN_OPENIDS`（逗号分隔 openid） |
| `/添加服务器`、`/移除服务器` | **两级放行**：机器人管理员 **或** 本群群主 / 管理员 | 白名单，或平台下发的 `member_role` |
| `/mc`、「永昼机」按钮 | 任何人（当前刻意不加限制） | —— |

### 机器人管理员：ADMIN_OPENIDS 白名单

- **留空 = 谁都不是管理员**（fail closed）：管理员指令一律拒绝并回一句说明，
  同时打一条 WARNING 日志（`[权限] 拒绝 /model：身份=[...] role=... 白名单=0 条`），
  便于你在线上日志里确认到底是谁在试。
- **怎么拿到自己的 openid**：发一次 `/我的id`（群里要 @机器人），
  输出会列出 openid（几个字段同值时归并成一行）和你的群内身份。
  把它填进 `.env`：

  ```env
  ADMIN_OPENIDS=01A2B3C4...,01D5E6F7...
  ```

- **一份 id 就够（实测）**：本机器人下同一个用户的
  `union_openid` / `member_openid` / `id`（群聊）与 `user_openid`（私聊）
  是**同一个值**，也就是跨群、跨私聊都认这一份。
  代码里 `identity_ids()` 仍会把四个字段都比对一遍（大小写不敏感），
  所以哪天平台把它们拆成按群隔离的值也不会漏；真出现不同值时优先用
  `union_openid`（跨群稳定），或把用到的 id 都列上。

### 群主 / 管理员：按平台 member_role

- 平台在群消息的 `author.member_role` 里给出 `owner` / `admin` / `member`
  （`utils/group_message_patch.py` 补了这个字段的解析）。
- `/添加服务器`、`/移除服务器` 是**两级放行**（`require_owner_or_group_admin`）：
  机器人管理员在哪个群甚至私聊都能改（私聊没有 `member_role` 也认），
  本群群主 / 管理员在本群也能改 —— 群管理自己维护服务器列表，不必都来找你。
- **取不到身份就拒绝**（平台没下发、或私聊且不在白名单）并打 WARNING：
  `role=(平台未下发)` —— 这是刻意的 fail closed，
  免得平台改字段后权限静默失效、谁都能改 `.env`。
- 这两条指令会改写 `.env`（`MC_SERVERS`），所以判定放在 handler 的**第一行**，
  拒绝时立刻 `return True` 终止分发（不返回 True 会继续走默认回复，用户会收到
  第二句莫名其妙的话）。
- `/mc`（RCON 命令）与「永昼机」按钮**刻意不加限制**（群友想用就用）。

### 加一条受保护的指令

```python
from utils.permissions import (
    require_owner,                 # 只有机器人管理员
    require_group_admin,           # 只有本群群主 / 管理员
    require_owner_or_group_admin,  # 两级放行
)

@Commands("/危险指令")
async def dangerous(api, message, params=None):
    if not await require_owner(message, "/危险指令"):
        return True                                       # 必须 return True
    ...
```

三个守卫都会：允许时返回 `True`（继续执行）、拒绝时回一句给用户并返回 `False`。
附带的 `/权限` 指令会告诉提问者当前各类指令的要求以及他自己的身份状态。

---

## 服务器地址的 QQ 脱敏（可逆转义）

QQ 会把消息里的域名当链接做风控，所以 `/服务器状态` 展示地址时不能直接写
`mc.ecustvr.top`。原来的做法是 `replace(".", "-")`，**不可逆**：
地址本身带短横线时（`my-server.example.com`）分不清哪个 `-` 原本是 `.`，
管理员也没法把显示串复制回 `/移除服务器`。

现在用可逆转义（`utils/qq_text.py`）：

```
qq_display(addr):  addr.replace("-", "--").replace(".", "-")
qq_address(text):  "--" → "-"，单个 "-" → "."
```

| 真实地址 | `/服务器状态` 显示 |
|----------|-------------------|
| `mc.ecustvr.top` | `mc-ecustvr-top` |
| `my-server.example.com` | `my--server-example-com` |
| `a-b-c.d-e.org` | `a--b--c-d--e-org` |

规则一句话：**显示串里单个 `-` 一定是 `.`，`--` 一定是原本的 `-`**，
所以 `qq_address()` 能无损还原（自检里有往返断言）。

`/移除服务器`（以及 `/添加服务器`）的入参解析顺序（`handlers/server.py::_resolve_address`）：

1. **原文精确命中当前列表** → 直接用它（真实地址带 `-` 的情况优先）；
2. **输入里有点号** → 认为用户给的就是真实地址，原样使用（不还原）；
3. **否则**按 `qq_address()` 还原 —— 于是可以直接把 `/服务器状态` 里的
   `mc-ecustvr-top` 复制过来，机器人自己换回 `mc.ecustvr.top`。

找不到时回复会带上当前列表（同样按显示串列出），方便复制：

```
服务器不存在：nope-nope-nope

当前列表：
- mc-ecustvr-top
- my--server-example-com
```

> 天然歧义：不带点号又带 `-` 的输入（`my-server`）会被还原成 `my.server`。
> 真要用这种「单段主机名 + 短横线」的地址，请写带点号的完整地址
> （`my-server.example.com`，会走第 2 条规则原样使用）。



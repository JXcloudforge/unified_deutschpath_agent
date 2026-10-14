# Deutschpath Unified Agent v1.0 公网正式版范围冻结

日期：2026-10-13。应用版本仍为 `0.1.1.dev0`。本文是 v1.0 范围、技术路线和验收顺序的唯一规范；Git 表格记录的是开发源目录历史风险，本发布副本已从指定 GitHub 仓库独立 clone，且未带入源 `.git`；正式发布状态由 `RELEASE_CHECKLIST.md` 和 `RELEASE_BLOCKERS.md` 跟踪。

## 文档来源与冻结原则

本次工作区和仓库文件清单中未发现《Deutschpath v1.0 正式版产品与技术栈冻结草案》，本轮消息也没有附带该文件。因此本文对产品草案的纠错以实际 `pyproject.toml`、运行入口、源码、部署文件和有证据的验收记录为准；未从缺失草案推断未提供的需求。若后续提供草案，只能通过评审后更新本文件，不另建平行范围文件。

冻结对象是 v1.0 的产品承诺和技术路线，不表示实现、供应商配置、部署或正式验收已经完成。功能状态定义：

- **INCLUDED**：目标 v1.0 产品范围内，已有可调用代码及可复现证据；公网所需身份、部署及真实服务条件仍须单独过发布门槛。
- **EXPERIMENTAL**：代码存在且有本机/离线证据，但功能、部署或外部服务边界未达到生产承诺。
- **DEFERRED**：明确不纳入 v1.0，不以“未来规划”充当已交付能力。
- **BLOCKED**：目标范围要求或发布前置项尚无足够实现/真实验收证据；满足前必须保持 NOT READY。

## v1.0 产品边界

v1.0 的目标是 HTTPS 公网多用户 Deutschpath 学习 Agent：用户通过可信 OIDC 登录；服务端独立验证面向 Deutschpath API 的 Access Token；每个账号的会话、学习状态、附件、编排状态及获准使用的私人数据按可信 Actor 隔离。用户以对话、德语学习资料检索、明确的 Web Search 请求和受控 OCR/词汇核对为主流程。

项目中的“CRM”当前实际是学习者资料、学习目标/偏好和学习事件的 UserState 模块，不是完整的客户关系管理产品。M08 是有限编排示例，不是通用 Agent 任务规划器。以上范围不能扩大解释为 CRM 销售流程、任意业务写入或任意工具自动执行。

## 冻结技术路线与当前事实

活动环境在 2026-10-13 读取；`pyproject.toml` 仅声明范围或固定少数依赖，仓库没有完整 lockfile。下表的 observed 是本机事实，不是已锁定的生产镜像版本。

| 技术 | 路线冻结 | 仓库声明 / 本机观察 | 状态与限制 |
|---|---|---|---|
| Python | Python 3.14 系列 | `>=3.14,<3.15`；3.14.6 | 本机 API、UI、测试使用；正式镜像 `python:3.14-slim` 仍是浮动 patch tag，未构建验收 |
| FastAPI / Uvicorn | 保留 ASGI HTTP API | FastAPI `>=0.115,<1`（0.141.1）；Uvicorn `>=0.30,<1`（0.52.4） | 入口 `app.api.main:app`，开发端口 8765；真实 loopback Uvicorn 已用于本机验收 |
| Streamlit | 保留现有 UI，使用原生 OIDC 登录 | `streamlit[auth]>=1.55,<2`；Streamlit 1.65.0，Authlib 1.8.0 | 入口 `ui/streamlit_app.py`，本机端口 8501；Auth-C 已实现 gate/Bearer 接线，真实 IdP 未验证 |
| SQLite | 业务模块内部封装，单 API 实例持久化 | Python stdlib；SQLite 3.50.4 | Chat 与 UserState 当前分模块/分表但共用 `stage2.db`；Auth/M08/MCP 状态还各有自有状态库/路径。无跨库事务；不承诺多 API 副本写一致性 |
| Chroma | 单实例本地持久向量库 | `chromadb>=1,<2`；1.5.9 | RAG/会话向量存储；依赖 `/data` 持久卷和备份。不是托管向量服务 |
| OIDC | 外部标准 OIDC Provider；Streamlit 原生登录，API 验证 API Access Token | API 使用 `PyJWT[crypto]>=2.10,<3`、JWKS；本机 Authlib 1.8.0 | Provider、issuer、audience、scope、域名与真实 secrets 尚未提供；禁止 ID Token 代替 API Access Token |
| Docker Compose | 单机单 API/单 Streamlit/单数据卷 | `deploy/compose.yaml` | 配置草案未运行；依赖 `STREAMLIT_SECRETS_FILE` 和 OIDC 环境变量 |
| Caddy | 公网 TLS 反向代理 Streamlit；API 只在容器内网 | `caddy:2.10`，`deploy/Caddyfile` | 域名、真实 TLS、WebSocket/OIDC 回调、请求体策略均未实测 |
| DeepSeek / Tavily | 外部可选 Provider，由既有 LLM/Web Adapter 调用 | SDK/HTTP Adapter 已实现；密钥是否存在不作为联通证据 | 本轮与验收记录未证明真实调用成功；请求可能产生费用 |
| MCP / OCR | 项目内部 stdio MCP Host，工具受 Host 授权及用户确认约束 | `mcp==1.30.0`、`rapidocr==3.10.0`、ONNX Runtime 1.29.0 | 测试覆盖协议及真实 loopback HTTP 闭环；MCP Inspector GUI 未验收，不提供公网 MCP endpoint |
| 文件解析 | 当前 Parser Registry 支持 TXT、MD、PDF、DOCX | `pypdf`、`python-docx`、RapidOCR | 自动化解析/上传有测试；生产体积限制、恶意文件扫描及备份恢复还未完成 |

正式候选必须另行锁定可复现依赖集合、基础镜像 digest、Compose/Caddy 运行版本；本机版本表不能代替生产 SBOM、构建或运行证据。当前技术路线不引入 PostgreSQL、消息队列、微服务拆分或托管向量数据库；只有实际单机 SQLite/Chroma 负载或一致性证据触发 ADR 后才重新评估。

## 模块能力与 v1.0 分类

| 模块 / 能力 | 状态 | 真实职责、调用接口与范围 |
|---|---|---|
| Agent / UnifiedOrchestrator | INCLUDED | `ChatService` 调用 `UnifiedOrchestrator.answer`，选择 Router 结果并组合 RAG/Web/直接上下文、证据及 LLM；它不保存通用任务计划 |
| UserState（历史称 CRM） | INCLUDED | 拥有学习者资料和学习事件；FastAPI 调用 UserState service，按可信 Actor 的内部 user_id 分区；没有完整 CRM 工作流 |
| Conversation / Chat | INCLUDED | `ConversationCommands` / `ConversationQueries`（由 `ChatService` 实现）拥有会话、消息、附件元数据、改名及上下文快照；UI 只经 `Stage2ApiClient`/HTTP 消费 |
| M07 会话历史和上下文 | INCLUDED | create/list/get/rename、消息历史、owner 查询、多轮历史快照和进程重启持久化已实现；上下文上限最近 20 条、12,000 字符，不是精确 token 预算；没有摘要持久化 |
| RAG / 文件 | INCLUDED | `RAGService`、`ChromaVectorStore`、Parser Registry；支持知识库和 session namespace 检索，Router 选择 rag。个人资料/附件必须由 API 与所属 Query 验证归属 |
| Router | INCLUDED（能力）；BLOCKED（独立指标门槛） | `IntentRouter.route(message, RoutingContext) -> RouteDecision` 只分类 `rag` / `web_search` / `no_tool`；`mixed_sources` 是来源策略。Rules/Hybrid 已存在；300 题开发报告不是盲测 |
| Web Search / Tavily | EXPERIMENTAL | `SearchQueryBuilder`、`QueryGuard`、`TavilySearchProvider` 只在显式联网意图调用；有 Fake/离线覆盖，无本轮真实外呼证据，不宣称实时可用 |
| M06 MCP / OCR / DB | EXPERIMENTAL | `MCPToolPlanner` / `MCPHost` 调用 stdio Database/OCR servers；OCR 先候选、用户确认后写入并读回。loopback B6 HTTP 验收已通过；Inspector GUI、真实生产双用户及运维验收缺失 |
| M08 编排 | EXPERIMENTAL（公网关闭） | `OrchestrationCommands/Queries` 与自有 SQLite；仅有界 `rename_session → list_sessions`，含有限澄清/确认/恢复。API 组合根只有 development 且显式 `M08_LOCAL_ENABLED` 时启用执行 Adapter；production 不开放该编排写路径 |
| M09 建议 | INCLUDED（用户显式 opt-in） | `FollowUpSuggestionService.get_follow_up_suggestions` 是只读 Query，最多 3 条离线确定性建议；默认关闭，点击只预填问题，不创建任务/执行命令 |
| Auth | BLOCKED（正式发布门槛） | `AuthService.authenticate` 验证 Access Token 并 issuer+subject 映射 Actor；Streamlit 已 native OIDC/Bearer 接线且缺配置 fail-closed。真实 IdP、两名真实用户、浏览器会话安全、公网部署均未验收 |
| 部署与数据恢复 | BLOCKED（正式发布门槛） | Dockerfile/Compose/Caddy 草案存在，但没有真实构建、VPS、TLS、限流、备份恢复或重启演练证据 |

业务模块边界冻结为 **业务模块自身 + Command API + Query API**。每个模块拥有自己的规则、状态、持久化和事务；调用方使用 DTO/公开 service contract。API 可做 composition root 和身份依赖注入，不直接访问跨模块 Repository。Auth-C bearer 请求中 UI 不声明 user_id；API 映射 Actor 后，资源 owner 检查仍在所属模块/公开接口边界完成。不同 SQLite 文件间不宣称原子事务或 exactly-once。

## 最初阶段四目标逐项映射

状态只表示已找到的代码和报告证据。标为 BLOCKED 的正式门槛不能被本机单测或 Fake 服务替代。

| 原阶段四目标 | 源码 / 公开接口 | 当前证据和结论 |
|---|---|---|
| M07 创建、继续、查询、恢复会话 | `ConversationCommands.create_session/rename_session`; `ConversationQueries.get_session/list_sessions/get_messages`；FastAPI `/sessions` 与 `/messages` | 已实现，真实 SQLite/HTTP 证据见 M07 与 M08 报告；生产跨用户 OIDC 仍 BLOCKED |
| M07 多轮上下文继承、数据边界、多用户隔离 | `get_context_snapshot(actor, session_id)`；Conversation/UserState/M08 各自状态拥有者 | 有界上下文与本机隔离测试已通过；真实 OIDC 双用户全资源验证 BLOCKED |
| M07 长对话预算或摘要、重启恢复 | ContextSnapshot 最近 20 条/12,000 字符；SQLite 持久化 | 裁剪和重启恢复已测；摘要机制 DEFERRED，不得称为已实现 |
| M07 迁移/回滚、异常原子性 | Conversation 现有 schema 和 Command 事务 | M07 未改业务 schema；跨 Auth/M08/Conversation SQLite 无共同事务，未知写入采用 Query 核对；严格 exactly-once BLOCKED/不承诺 |
| M08 上下文理解、意图和复杂度判断 | 原 `IntentRouter` 三分类；M08 有限规则适配 | 只有 `rename_session` 及固定双步骤识别；没有任意意图解析或通用复杂度规划，通用能力 DEFERRED |
| M08 缺参追问、跨轮继承和提案修订 | `M08ChatAdapter`、Orchestration Commands/Queries | rename 缺标题澄清、原提案续接、修订使旧确认失效已由 HTTP/状态测试覆盖（见 M08-B 报告） |
| M08 确认、授权、幂等、失败与恢复 | 状态机、确认键、ConversationRenameExecutor、Conversation Query 核验 | rename 两步真实 loopback HTTP、重复确认、重启及跨用户 404 已测；仅覆盖该执行器，公网 M08 执行 BLOCKED |
| M08 连接 CRM/UserState、Knowledge/RAG、MCP 和任意 Tool Registry | 所属业务 Commands/Queries 与 MCP Host | M08 没有这些执行器；既有 Chat 自身可调用 RAG/Web/MCP 受控流程。CRM task Command 与通用工具注册表 MISSING；M08 通用调用 DEFERRED |
| M09 相关问题建议、可关闭、不写状态 | `SuggestionQueries.get_follow_up_suggestions`；Chat `include_suggestions`；UI opt-in 控件 | 本地 HTTP、关闭、去重/数量/状态抑制及只预填交互已验收；M09 included，但不代表通用生成式推荐 |
| M10 原六模块兼容、文件类型、API/UI/数据库异常 | Agent、UserState、Chat、RAG、Router、MCP/OCR、Parser Registry、FastAPI、AppTest | 当前回归与 loopback acceptance 通过；独立 API Smoke 1 项；文件解析支持 TXT/MD/PDF/DOCX。生产 UI 浏览器和生产数据库生命周期未验收 |
| M10 DeepSeek/Tavily/MCP 真实联通和证据 | `DeepSeekLLM`、`TavilySearchProvider`、`MCPHost` | MCP 本机 stdio/HTTP 测试通过；DeepSeek/Tavily 未真实外呼；MCP Inspector GUI 未验收，均 NOT VERIFIED |
| M10 Router 独立验收 | `scripts/router_human_eval.py` + 人工冻结数据 | 数据结构有效；150/150 `unreviewed`，无人工真值/冻结 hash/独立成绩；BLOCKED。开发集 300/300 不能替代 |
| v1.0 公网认证和部署 | Auth bearer/JWKS + Streamlit OIDC UI + Compose/Caddy | 认证代码和 fail-closed 测试存在；无真实 IdP、公网两账户测试、Compose/Caddy 演练及恢复验收，BLOCKED |

## v1.0 发布任务（依赖顺序）

此表是执行顺序与验收定义；日常勾选状态仍记录在 `RELEASE_CHECKLIST.md`，当前未通过项在 `RELEASE_BLOCKERS.md`。

| 顺序 | 任务 / 依赖 | 交付物 | 验证命令 / 操作 | PASS 标准 | 阻塞条件 |
|---|---|---|---|---|---|
| 0 | 仓库归属与发布基线（所有后续提交前） | 仓库所有者确认记录、目标 repo、发布 allowlist、已确认的旧 CRM 删除处理 | `git rev-parse --show-toplevel`; `git remote -v`; `git status --short`; `git diff --stat`; `git diff --cached --stat` | HEAD、目标 remote、变更归属和敏感数据审查均明确；发布只包含 Deutschpath 获准文件 | 目标发布副本 `origin` 已核实为 `unified_deutschpath_agent`；源开发目录仍有 CRM-agent remote 与大量历史变更且未触碰。提交前仍须审查本副本差异与敏感文件；禁止从源目录搬运 `.git` |
| 1 | 完成真实 OIDC 应用配置（先于双用户测试） | provider issuer、API audience/scope、JWKS/metadata、client ID/secret、HTTPS callback/logout、账户责任人和 secrets 注入方案 | FastAPI/Streamlit 的真实浏览器 OIDC 登录；确认 Access Token `iss/aud/exp` 与 API 设置一致；不记录 token | 两个受控测试账号都能走真实登录、Streamlit server-side bearer 请求通过 API 验签；缺配/错误 audience/过期 fail closed | 当前无真实 Provider 或域名；fake RSA/JWKS 不算真实联通 |
| 2 | 两个真实账号端到端权限验收（依赖 1） | 跨用户安全测试记录，覆盖 Conversation、UserState、附件、RAG 私人命名空间、M08/M09、OCR/MCP | `.venv\Scripts\python.exe -m pytest tests\unit\test_auth.py tests\integration\test_auth_http.py -q`；另对真实环境执行登录后 API/UI A/B 数据访问矩阵 | A/B 互不可读写；匿名、伪造 X-User-ID、过期/篡改/错 aud 均拒绝；自身资源正常；登录重启后映射/数据稳定 | 上述 pytest 是 fake/local 证据，不能替代真实浏览器/IdP/附件/RAG/MCP 双账号验收 |
| 3 | 复现候选依赖与容器构建（依赖范围冻结） | 精确依赖 lock/SBOM、固定基础镜像 digest、Compose/Caddy 版本和构建记录 | `docker compose -f deploy/compose.yaml config`; `docker compose -f deploy/compose.yaml build` | 全新隔离环境可按固定版本构建；无真实密钥进入镜像；health checks 就绪 | 当前无 lockfile、镜像为浮动 patch、Compose 未运行；需确认部署平台和 secrets 注入 |
| 4 | Provider 实际连通（依赖 1；外呼单独授权） | DeepSeek/Tavily 请求、响应状态、延迟、超时/错误和引用来源的脱敏记录 | UI 本机设置的 DeepSeek 真实连接；`.venv\Scripts\python.exe scripts\verify_tavily_live.py` | 真实服务成功返回且降级/错误表现可接受，不泄露密钥；对外信息边界正确 | 可能计费，必须由用户另行授权；Fake Provider、配置了 Key、`/health` initialized 均不算 PASS |
| 5 | Router 150 题独立盲测（可与任务 4 并行；先人工冻结再运行模型） | 双人独立标签、分歧裁决、题目独立性审核、冻结 CSV/manifest/SHA-256 和独立报告 | `.venv\Scripts\python.exe scripts\router_human_eval.py audit`; 依指南完成双人标注与 freeze；`... router_human_eval.py evaluate --manifest <manifest> --router rules`；Hybrid 只在获准外呼后运行 | frozen hash 一致；150 项齐全；Accuracy ≥147/150，并报告 Macro F1、各类 P/R/F1、混淆矩阵、mixed_sources 及错误分析 | 当前 0/150 reviewed，8 个 overlap 候选待人工检查；不得自动造标签、预测泄漏或在独立集上调参 |
| 6 | MCP Inspector GUI（依赖隔离专用业务 DB） | Inspector 版本/启动命令、工具 Schema、preview/confirm/readback/拒绝访问真实截图 | 已有本机回归：`.venv\Scripts\python.exe scripts\mcp_b6_http_acceptance.py`；另由验收者启动 MCP Inspector 执行 GUI 步骤并归档截图 | GUI 连接的是专用临时 DB；确认前无写入，确认后读回匹配，未授权/跨用户拒绝 | Inspector GUI 未验收；本机自动 HTTP/stdio 不替代 GUI 证据；不得连真实用户 DB |
| 7 | 隔离生产拓扑演练（依赖 1、3） | Linux VPS 或等价隔离部署记录、TLS/域名、反代/WebSocket、限流/请求上限/预算与安全检查 | `docker compose -f deploy/compose.yaml config`; `docker compose -f deploy/compose.yaml up -d`; `docker compose -f deploy/compose.yaml ps`; `curl -fsS https://<domain>/health` | Caddy HTTPS 有效；FastAPI 无公网端口；OIDC callback、WebSocket 登录和 API 内网正常；拒绝越权，速率/上传限制实测 | Compose/Caddy 仅草案；域名、服务器、代理信任和安全参数未确定或未授权，不可公网开放 |
| 8 | SQLite/Chroma/附件备份恢复（依赖 3、7） | 一致性/锁等待结果、脱机备份、异地保存配置、隔离恢复演练及核验记录 | 临时 SQLite 副本用 Python `sqlite3.Connection.backup()` 后执行 `PRAGMA integrity_check`；重建隔离 Compose 卷并核对 SQLite、Chroma 和附件样本 | 恢复后的 DB `integrity_check=ok`，已知样本可读；Chroma/附件与会话对应；锁等待、停止/重启和备份年龄达部署目标 | 既有仅为临时 SQLite backup API 演示，非 VPS 全量恢复；缺负载目标、异地介质或数据保留责任人 |
| 9 | 发布候选集成签署（依赖所有 P0/P1） | 冻结范围签署、全量报告、截图清单、已关闭 blockers、候选构建产物 | `.\scripts\run_tests.ps1`; `.venv\Scripts\python.exe -m pytest tests\integration\test_api_smoke.py -q`; M08-B/C、M09、MCP acceptance；`python -m compileall -q app ui scripts tests`; `git diff --check`; `git diff --cached --check` | 发布候选同一提交/构建上复测成功；所有 INCLUDED 可用，BLOCKED 项关闭；安全审查通过；保留 `0.1.1.dev0` 直到单独发布授权 | 当前工作树未形成可审查候选，所有真实 OIDC/Router/外部 Provider/Inspector/部署恢复门槛均未关闭 |

任务 4 的 DeepSeek/Tavily 外呼与任务 5 的 Hybrid Router 都可能计费；没有明确授权时仅做离线/Rules 验收，不调用真实服务。所有公网启用、数据库迁移和仓库发布操作继续按各自授权流程执行。

## 当前冻结结论

- 范围定义：**PASS**（按当前真实实现冻结；产品/技术草案文件本轮不可得）。
- 技术路线：**已冻结方向，版本可复现性 NOT VERIFIED**（缺 lock、镜像 digest 和 Compose 实测）。
- v1.0 公网就绪：**BLOCKED**。P0 为仓库归属/发布范围确认、真实 OIDC 与双用户权限验收、Router 独立人工验收；P1 为真实 DeepSeek/Tavily、MCP Inspector GUI、生产容器/HTTPS、安全控制与完整备份恢复。M08 泛化任务规划不在 v1.0 承诺范围。
- 本轮不修改任何数据库/业务代码，不改变版本，不执行 Git 写操作。


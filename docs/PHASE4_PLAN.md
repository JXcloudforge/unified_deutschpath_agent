# 阶段四实施计划（模块边界版）

日期：2026-10-13。目标仍为未来正式版 `1.0.0`；本计划本身不表示阶段三/四验收通过。

v1.0 公网范围与依赖顺序以唯一规范 [`V1_RELEASE_SCOPE.md`](V1_RELEASE_SCOPE.md) 为准。本计划记录 M07–M10 的工程状态，不扩大产品承诺；M08 泛化任务规划已明确延期。

## 实施顺序与依赖

| 顺序 | 模块 | 依赖和职责 | 验收条件 |
| --- | --- | --- | --- |
| Audit | 边界审计 | 识别业务状态拥有者、公开接口、越界 Repository/SQL 访问 | `docs/architecture/MODULE_BOUNDARIES.md`、`PUBLIC_CONTRACTS.md`、ADR 完整并与源码一致 |
| M07 | Conversation 历史与上下文 | Conversation owns Session/Message；ChatWorkspace 经 HTTP；API 用 Conversation Commands/Queries；Agent 收到受限快照 | **初始实现完成**：DTO/Protocol、用户隔离、重启恢复、多轮继承、长上下文裁剪、空会话、只读查询、旧 HTTP 契约和依赖检查通过；无 schema 迁移 |
| M08 | 意图状态与任务协调 | 复用 Router/Agent/Tool；历史与会话归属从 M07 Query 获取；真实业务写入走所属模块 Command；任务状态只由确定模块拥有 | **M08-C 有界双步骤闭环 PASS**：仅支持本地 rename_session → list_sessions；复杂规划和其他业务写入未完成 |
| M09 | 后续问题建议（可选） | `app.suggestions` 只读 Query；读取 M07 Context Snapshot、只读 M08 状态 | **PASS**：默认关闭；最多 3 条离线建议；只预填输入框；失败不阻断回答。详见 `docs/PHASE4_M09_ACCEPTANCE.md` |
| M10 | 集成与验收 | 汇总各模块契约、全量回归、真实 Provider、人工 Router 集和截图 | 记录 PASS/FAIL/NOT VERIFIED、测试环境、结果、修复复测、风险与真实截图清单；任何未实测外部服务均不标通过 |

阶段三原有正式门槛继续阻塞正式发布：Router 独立 150 题人工标注/冻结及 98% 指标、DeepSeek/Tavily 实时验证、MCP Inspector GUI、可信身份与生产运维验收需要各自独立证据。工程 300 题开发集不替代盲测。全部 v1.0 硬门槛未通过前保持 `0.1.1.dev0` 或经核准的候选版本。
## M10 状态（2026-10-13）

本机 M10-A 回归与 M08-B/C、M09、MCP B6 loopback HTTP 验收本轮复测通过；具体环境、退出码和限制见 `docs/PHASE4_M10_ACCEPTANCE.md`。M10-B Router 独立集因 150 条人工标注全部 `unreviewed` 而 NOT VERIFIED；DeepSeek/Tavily 有本地配置但本轮未进行可能计费的外呼；MCP Inspector GUI 尚待人工验收。M10-C 补入 API 上传 owner/类型/大小边界，可信认证与公网部署仍 BLOCKED。版本保持 `0.1.1.dev0`。

M09 设计与验收：见 `docs/architecture/M09_SUGGESTIONS.md` 和 `docs/PHASE4_M09_ACCEPTANCE.md`。M09 不改变 M08 的能力或验收范围。

## M10 Auth 增量（2026-10-13）

- v1.0 多用户 OIDC 产品目标已确定。新增 `app.auth`，验证 issuer/audience 的 OIDC API Access Token，并用 Auth 自有 SQLite 将 issuer+subject 映射到随机稳定 user_id，默认角色为服务端 member。
- FastAPI 私有路由统一依赖可信 ActorContext；production 不接受 X-User-ID fallback。development 仅直接 loopback 可用本地 header。Auth-C 已接入 Streamlit 原生 OIDC gate 和 Bearer API Client，并由本机契约/AppTest 覆盖；真实 provider 未配置，公网 UI 链路仍未通过。
- Fake RSA/JWKS、临时身份 SQLite、HTTP 用户隔离和 Streamlit Bearer 客户端均有离线证据。真实 IdP、两真实用户、浏览器会话安全、VPS 和恢复演练仍为阻塞项；详见 `docs/PHASE4_M10_AUTH_ACCEPTANCE.md` 与 `docs/PHASE4_M10_AUTH_UI_ACCEPTANCE.md`。
- 部署草案位于 `deploy/`，未开放公网。

## M07 已执行范围

- `ActorContext` 仅代表 `X-User-ID` 指定的本机用户分区，明确未认证。
- `ConversationCommands` 和 `ConversationQueries` 由既有 `ChatService` 实现；Repository 收回 `app.chat` 内部。
- Session、Message、ContextSnapshot 使用不可变 DTO；查询先按 actor 检查 session 所有权。
- Context Builder 将历史限制为最近 20 条且最多 12,000 字符；这是字符界限，不是精确 token 预算。摘要持久化未做。
- API 适配器迁移到 Command/Query，现有 HTTP 路径、序列化字段与主要错误码维持兼容。
- 不改变 SQLite schema，不执行用户库迁移。

## M08 接口依赖准备

M08 依赖 M07 Conversation Commands/Queries 和既有 IntentRouter，并以独立 SQLite 管理计划与步骤。M08-C 受限识别 rename_session → list_sessions；CRM task Command、通用 Tool Registry 和复杂任务规划仍缺失。执行器声明清单见 docs/PHASE4_M08C_ACCEPTANCE.md。

## M08 执行记录（2026-10-13）

- 新增 `app.orchestration` DTO、Command / Query、独立 SQLite 状态服务，包含路由快照、澄清提案、等待确认、取消、executor 调用、异常记录和一次性确认键。
- 新数据库 `orchestration.sqlite3` 与现有 `*.sqlite3` 忽略规则匹配；未迁移既有用户库。
- 状态归属与独立持久化决策记录于 `docs/adr/ADR-m08-orchestration-state.md`。
- M08-A 当时离线状态机单测 8 项通过。其余当前状态由下方 M08-B 增量记录更新。
- 详细验收矩阵见 `docs/PHASE4_M08_ACCEPTANCE.md`。

### M08-B 增量记录

- API 通过 `M08ChatAdapter` 接入现有 `POST /sessions/{id}/messages`；普通问答回退旧 ChatService。动作路径保存每轮消息一次，不改 URL/既有字段，仅增加可选编排信息。
- 首个执行器 `ConversationRenameExecutor` 调用公开 `rename_session` Command，并以公开 `get_session` Query 精确核验。缺名追问和补充沿用同一 orchestration；提案修订旋转确认键。
- 独立 `orchestration.sqlite3` 与 Chat SQLite 无共同事务；重复/未知结果通过 Query 核对，不自动重放。不能保证 exactly-once。
- 默认开关关闭；只在 development 且直接 loopback/无代理转发头时接入；production mutation 全部拒绝，身份未认证。
- 测试结果：16 个 M08 聚焦测试通过；真实 loopback HTTP 重启闭环通过；全量 222 passed、1 skipped、0 failed；独立 API Smoke 1 passed；compileall 与 diff-check 通过。具体命令和限制见 `docs/PHASE4_M08_ACCEPTANCE.md`。
- M08-B 仅是最小真实业务闭环；CRM、学习任务、多意图、通用工具规划及生产认证仍属未完成。

### M08-C 增量记录

- M08 自有 SQLite 新增步骤表；现有 Conversation/CRM 数据库和业务 schema 未修改。旧单动作提案仍能规范化为单步骤。
- 仅解析明确的 rename_session 后 list_sessions 目标；整体计划需确认。Conversation Command 执行后以 Conversation Query 核验，成功后才调用只读列表 Query。
- 步骤记录参数、依赖、状态、结果和错误。Command 失败阻止后续步骤；后续 Query 失败记为 PARTIAL；不确定 Command 查询核对后才允许继续，不自动重放。
- 真实 loopback HTTP 测试覆盖提案持久化、服务重启后确认、两步结果与会话名读回。完整测试证据见 docs/PHASE4_M08C_ACCEPTANCE.md。
- **复测结果：** M08 聚焦单测/契约/集成 23 passed；全量 `scripts/run_tests.ps1` 为 229 passed、1 skipped、0 failed；M08-B、M08-C 与 MCP B6 HTTP acceptance 均退出码 0；API Smoke 1 passed；compileall 与 `git diff --check` 通过。唯一跳过为 Windows symlink 限制。
- **状态边界：** 上述结果只验收固定 rename_session → list_sessions 的本地双步骤闭环，不代表通用 M08 完成。生产身份、外部 Provider 实测及 Router 独立人工集继续阻塞 v1.0。

## M07 执行记录（2026-10-13）

- **归属：** Conversation / `app/chat` 唯一拥有会话、消息、附件元数据及历史快照。FastAPI 是 adapter；ChatWorkspace 保持 API Client 依赖。
- **Command：** `create_session`、`rename_session`、`send_message`、`append_assistant_message`、`upload`。
- **Query：** `get_session`、`list_sessions`、`get_messages`、`get_context_snapshot`。
- **依赖变化：** `app/api/main.py` 从 `chat.repository` 直接读/写迁移到 `ChatService` DTO/接口。`ChatRepository` 不再从 `app.chat` package export；`ChatService.from_path` 在 Conversation 内部构建 SQLite Repository。FastAPI 健康检查和 MCP 完成路径从组合根消费 Agent/LLM，而不访问 ChatService 内部字段。
- **兼容：** 保留原有 Session、Message、send result HTTP JSON 字段与路由；既有 UI API Client 不变。SQLite schema 和正式本地数据库未变更。
- **真实验证：** 基线为 200 passed, 1 skipped；M07 后全量为 206 passed, 1 skipped。含版本/UI 文档的聚焦契约/健康/Chat/架构测试为 33 passed。隔离 Uvicorn/stdio MCP E2E 通过：session/upload/OCR/confirm 为 200，跨用户确认 404，确认前 0 行、确认后 3 行读回验证，正常关闭。`python -m compileall -q app ui scripts tests` 退出码 0。
- **边界：** ActorContext 的 Header 身份未认证；历史上限以字符估算，不是精确 token 预算；不实现摘要。API 构造 UserState Repository 和直接写上传字节仍记录为后续边界，不纳入 M07。
- **回滚：** 只需回滚 M07 代码/文档变更，并恢复 API 旧版 repository 调用组合；数据文件和 schema 无需回滚。当前 Git 有历史 staged/unstaged 内容，执行回滚时须只选择 M07 文件，不能 reset 整个工作树。
- **阶段状态：** M07 初始工程实现 PASS；M08-C 有界双步骤闭环 PASS，但通用 M08 能力仍未完成；M09 后续问题推荐 PASS；M10 正式集成验收待执行。阶段三正式独立 Router/真实 Provider/Inspector/认证门槛仍未完成。

## 后续审计项

1. User State：API 组合根当前 import/构造 `UserStateRepository`；迁移到 User State 内部工厂/API，并保持 `/users/me/*` 兼容。
2. Attachment 文件存储：API 当前直接把上传文件写入 `ROOT/uploads`；先决定文件字节与附件元数据由哪个模块共同拥有，再切换，不要只为抽象搬迁目录。
3. Actor 身份：正式部署前加入可信认证依赖，以认证主体而非任意 Header 构造 ActorContext。
4. 会话归档/永久删除：维持已记录的 schema 评审和跨 Chroma/MCP/OCR 清理要求；不属于本次 M07。


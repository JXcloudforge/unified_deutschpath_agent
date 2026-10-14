# M08-C 有界多步骤编排验收

日期：2026-10-13。版本：0.1.1.dev0。本报告仅评估“改名当前会话，然后列出会话”这一确定性双步骤工作流，不代表通用自主规划或生产认证。

## C0 能力注册与现状审计

| 能力 | 所属模块 | 类型 / 参数 | 副作用 | 授权与确认 | 离线可测 | M08-C 真实执行器 |
|---|---|---|---|---|---|---|
| rename_session | Conversation | Command；ActorContext + session_id + title | 是 | owner Query；用户明确确认；生产可信身份仍未具备 | 是 | 是；ConversationRenameExecutor |
| list_sessions | Conversation | Query；ActorContext | 否 | 用户分区过滤 | 是 | 是；ConversationListSessionsQuery |
| search_knowledge | RAG | Query；namespace + query + top_k | 否 | RAG namespace 边界 | 是 | 否；现有 Agent/RAG 路径可用，未注册为计划步骤 |
| web_search | Web | Query；query + max_results | 否 | QueryGuard 与 Provider 配置 | 有 Fake Provider 测试 | 否；M08 不调度该能力，真实联网另行验收 |
| save_learning_event / update_user_state | User State / CRM | Command；各自 DTO | 是 | 当前 X-User-ID 未认证；M08 未提供 CRM 执行器 | 是 | 否 |
| OCR 确认写入 | MCP Host / Database MCP | 已有受控 workflow；operation_id + reviewed rows + confirmed | 是 | Host user/session 绑定和明确确认 | 有 stdio 集成测试 | 否；保留既有 MCP Host 路径 |
| create_learning_task | 无正式拥有者/接口 | Command 不存在 | — | — | 否 | 否，不虚构 |

清单由 app/orchestration/capabilities.py 提供为轻量审计声明；它不是动态通用 Tool Registry。当前 M08 仅将 Conversation 两项纳入真实执行适配。

## 执行流程

用户多意图输入 → Conversation get_context_snapshot 校验归属 → 确定性解析固定两步计划 → M08 保存计划与步骤 → 整体确认 → Step 1 rename_session Command → Conversation get_session Query 核验 → Step 2 list_sessions Query → 保存两步结果并反馈。

任一步骤失败或结果不确定时停止依赖步骤；写 Command 不自动重放。

## 计划和步骤状态

- 计划沿用现有 orchestration_id 作为 plan_id；revision 与确认键绑定完整提案 JSON，修订后旧确认失效。
- 步骤表 orchestration_steps 存储 step_id、action_type、owner_module、Command/Query、参数 JSON、前置依赖、状态、结果引用、错误和顺序。
- 计划状态沿用 NEEDS_CLARIFICATION、AWAITING_CONFIRMATION、EXECUTING、SUCCEEDED、FAILED、UNCERTAIN、CANCELLED；新增 PARTIAL 表示至少一步完成而后续步骤失败。
- 步骤状态为 PENDING、RUNNING、SUCCEEDED、FAILED、UNCERTAIN、BLOCKED。步骤按依赖顺序串行运行；依赖未成功则阻止后续步骤。
- M08 数据迁移仅在自己的 SQLite 上新增 CREATE TABLE IF NOT EXISTS orchestration_steps。不修改 Conversation/CRM schema。旧版不确定记录升级时，其可能已提交的首个 Command 会保守标记为 UNCERTAIN，不会重放。

## 失败和恢复

- Command 失败：计划为 FAILED，后续步骤为 BLOCKED。
- 已有步骤成功、后续 Query 失败：计划为 PARTIAL，已成功步骤及 Query 失败各自保留状态，回复清楚列出完成和失败内容。
- 同步重复或并发确认：SQLite 条件更新只允许一个请求领取计划；另一个请求观察 EXECUTING 并返回处理中，不启动第二份写入。
- 进程启动时遗留 RUNNING/EXECUTING 转为 UNCERTAIN。Command 步骤只通过目标模块提供的 reconcile Query 核对；读 Query 可安全重跑。无法核实时停止并等待人工核查。
- 已写入 Command 与 M08 步骤状态分属不同 SQLite 事务，不能保证严格 exactly-once。若 Query 与提案不匹配，不自动重放。
- 取消仅允许在执行前；等待中的步骤转为 BLOCKED 并记录取消原因。

## 依赖方向与契约

ChatWorkspace → 现有 HTTP → API 组合根 → M08ChatAdapter → OrchestrationService。M08 通过 Conversation Commands/Queries 执行业务；Repository 和两个 SQLite 均只由其拥有模块访问。Router 继续产生现有 rag / web_search / no_tool 决策，M08 确定性规则只接受精确支持的重命名 + 列表组合，不另建 Router，也不依赖 LLM 给出可信执行计划。

真实调用为：

1. ConversationQueries.get_context_snapshot(actor, session_id) 校验会话拥有权。
2. OrchestrationService.start_orchestration(...) 调用原 IntentRouter 并持久化计划归属和路由快照。
3. 确认前只保存消息/计划；M08 消息 Command 保留新会话的默认标题，避免 Chat 首条消息自动标题逻辑提前改变目标业务状态。
4. 确认后 M08 先持久化 EXECUTING 与步骤 RUNNING，执行器调用公开 ConversationCommands.rename_session，再经 ConversationQueries.get_session 核验。
5. 只有 Step 1 核验成功，执行器才调用公开 ConversationQueries.list_sessions；结果只保存会话标题列表，不复制会话实体。
6. 两个步骤结果均返回在现有消息响应的可选 orchestration.steps DTO 内；普通聊天响应和 HTTP 路径保持兼容。

## 测试证据

| 分层 | 命令 | 结果 |
|---|---|---|
| Unit / contract / integration | `.venv\Scripts\python.exe -m pytest tests\unit\test_orchestration_service.py tests\integration\test_m08_chat_integration.py -q` | exit 0；23 passed，0 failed，2 warnings |
| M08-B HTTP 回归 | `.venv\Scripts\python.exe scripts\m08_b_http_acceptance.py` | exit 0；真实 loopback HTTP，普通聊天/澄清/重启后确认/重复确认成功，跨用户读取 404，标题读回正确 |
| M08-C HTTP E2E | `.venv\Scripts\python.exe scripts\m08_c_http_acceptance.py` | exit 0；loopback HTTP 提案持久化并重启后确认；rename_session 和 list_sessions 均 SUCCEEDED；Query 结果 1 项；重复确认 HTTP 200 且未重复写入 |
| MCP HTTP 回归 | `.venv\Scripts\python.exe scripts\mcp_b6_http_acceptance.py` | exit 0；真实 Uvicorn/stdio MCP；确认前 0 行、确认后 3 行，跨用户 404，优雅关闭 |
| 全量离线回归 | ` .\scripts\run_tests.ps1` | exit 0；229 passed，1 skipped，0 failed；skip 为 Windows 账户无法创建 symlink 的 OCR/MCP 用例 |
| API Smoke | `.venv\Scripts\python.exe -m pytest tests\integration\test_api_smoke.py -q` | exit 0；1 passed，2 warnings |
| 编译与差异格式 | `.venv\Scripts\python.exe -m compileall -q app ui scripts tests`、`git diff --check` | 均 exit 0；compileall 无错误；差异检查有 Git LF→CRLF 提示，无空白错误 |

HTTP 测试使用临时数据目录和 FakeLLM，不证明 DeepSeek、Tavily、MCP Inspector 或生产认证的真实联通。

## 验收矩阵

| 项目 | 状态 | 限制 |
|---|---|---|
| 明确多意图解析与双步骤真实执行 | PASS | 真实 HTTP E2E 验证两步骤持久化、顺序执行和结果读回 |
| Command 前要求确认；Query 依赖 Command 成功 | PASS | 确认前不改名；改名 Query 验证后才列出会话 |
| 缺参跨轮继承和提案修订 | PASS | M08 聚焦测试覆盖，确认键随修订更新 |
| Command 失败、第二步 Query 失败与部分完成 | PASS | 测试覆盖失败隔离和 PARTIAL；写入失败不自动重放 |
| 重复/并发确认、跨用户、服务重启 | PASS（限定本地未认证身份模型） | 重复确认、并发与重启测试通过；X-User-ID 仍未认证 |
| 不确定 Command 查询核对后续跑 | PASS（本地 SQLite 模型） | 无法匹配时人工核查，不盲目重放 |
| 复杂多意图、CRM 写入、通用 Tool Registry、无限制规划 | NOT VERIFIED / 不支持 | 明确作为后续工作 |
| 正式生产身份、Router 独立人工集、在线 Provider | NOT VERIFIED | 继续阻塞 v1.0 |

## 回滚

M08 步骤数据仅位于独立 orchestration.sqlite3；新增表为 additive。回滚代码不需要改变现有 Conversation schema，旧单动作提案仍可从 JSON 兼容装载为单个步骤。不得删除或重建现有 M08 数据库。

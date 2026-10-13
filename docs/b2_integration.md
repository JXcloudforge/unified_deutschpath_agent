# B2 历史能力复用与整合报告

版本目标：Deutschpath Unified Agent v0.1.0-beta。主工程保持 04；本批仅整合 CRM/User State 与最小 UI，不接入旧 Agent Loop，不实施 MCP。复用标记：KEEP、REUSE、ADAPT、NEW、DEFER、DISCARD。

## A. 历史代码复用矩阵

| 功能 | 来源文件 | 目标文件 | 决策 | 修改与测试 |
|---|---|---|---|---|
| Agent Loop / State / Checkpoint | `01_agent/src/deutschpath/agent/{loop,state,checkpoint}.py` | 保留 04 Orchestrator | DEFER | Loop 属于独立完整执行链；Checkpoint 只有占位声明。B2 不接入；B6 审计见 [b2_tool_reuse.md](b2_tool_reuse.md)。 |
| 工具 Registry / Function Calling / Provider | `01_agent/src/deutschpath/tools/`、`llm/` | 当前无运行时迁移 | DEFER | 作为 B6 输入；不能替换 04 `LLMClient.answer(prompt)` 或三分类 Router。 |
| CRM CEFR 与校验 | `02_crm_agent/app/db/repository.py`、`app/api/models.py` | `app/users/models.py`、`service.py` | ADAPT | 适配 CEFR 标准化、非空文本、用户 ID 校验；保留 04 nullable 状态语义和四字段模型。`tests/test_sqlite.py` 的边界用例经适配后验证。 |
| CRM LearningEvent | `02_crm_agent/app/models/customer.py`、`app/db/repository.py` | `app/users/models.py`、`repository.py` | ADAPT | 去掉旧 `customer_id`/metadata，映射 04 现有 `user_id`/五列事件表；SQL 参数化，按用户隔离、倒序读取并限制 1–100。 |
| CRM API 调用方式 | `02_crm_agent/app/api/routes.py`、`api/models.py` | `app/api/main.py` | ADAPT | 复用薄路由和 Pydantic 校验边界；改用 04 `UserStateService` 和当前 `X-User-ID`，不迁移旧 CRM API/Router。 |
| Session 列表 | `03_deutsch_chat/src/deutsch_chat/persistence/repositories.py::list_sessions` | `app/chat/repository.py`、`app/api/main.py` | ADAPT | 同一 04 Chat SQLite 表和 dict 契约，复用按 user_id 过滤、`updated_at DESC, id DESC` 排序；新端点只读会话。 |
| UI 会话切换/用户状态清理 | `03_deutsch_chat/src/deutsch_chat/ui/sidebar.py`、`ui/state.py` | `ui/streamlit_app.py` | ADAPT | 复用选择会话与切换用户时清理会话/上传标记的做法，适配 04 单页状态键；不迁移完整旧 UI 或登录流程。 |
| HTTP 超时/错误与上传 | `03_deutsch_chat/src/deutsch_chat/ui/api_client.py`、`tests/integration/test_attachments.py` | 04 `ui/api_client.py`、`streamlit_app.py` | KEEP | 04 已有请求超时、错误消息、聊天/附件、history 客户端及对应测试，本轮保留这些实现。 |
| Stage 2/3 主流程 | 04 `app/agent/orchestrator.py`、`routing/`、`rag/`、`web/`、`chat/` | 同文件 | KEEP | 不重写 Orchestrator、RAG、Router、Tavily 或 EvidenceAggregator；FakeLLM 新测试验证状态上下文及 RAG 路径。 |
| UI Profile 面板 | 四工程均无可直接移植的完整 Streamlit CRM 面板 | 04 `ui/streamlit_app.py` | NEW | 仅新增侧栏表单和最近事件显示，调用现有 ApiClient；AppTest 覆盖保存、失败保留草稿、用户切换。 |

实现迁移部分没有新依赖。直接复用旧 CRM 文件作为运行模块会同时引入旧 customer/profile 表、CustomerState 和 SQL Agent；本批只适配少量规则与查询，未复制平行数据库。

## B. 文件变更清单

| 04 路径 | 决策 | 说明 |
|---|---|---|
| `app/users/models.py` | ADAPT | UserState 保持不变；增加 ProfileUpdate、LearningEventIn、LearningEvent 和 CEFR 集合。 |
| `app/users/repository.py` | KEEP + ADAPT | 保留表、get、UPSERT；适配事件返回读回和限量历史查询。 |
| `app/users/service.py` | ADAPT | 统一校验后的部分更新，支持 null 清空和事件历史。 |
| `app/api/main.py` | ADAPT | 增加 profile/events API；新增只读 GET `/sessions`。不改现有 HTTP 路由。 |
| `app/chat/repository.py` | ADAPT | 适配 03 session list 查询到已有 04 表。 |
| `ui/api_client.py`、`ui/streamlit_app.py` | KEEP + ADAPT + NEW | 保留现有请求、错误、附件和聊天代码；增加状态 API 方法、侧栏表单和会话选择器。 |
| `scripts/http_acceptance.py` | ADAPT | 保留已有 B1 HTTP 检查；增加可选 `--crm`、`--verify-crm-user` 场景。 |
| `tests/unit/test_user_state.py`、`test_ui_profile.py` | NEW | CRM 单测和 UI/API Client 测试；覆盖 02 移植用例及 04 新增边界。 |
| `tests/integration/test_stage2_flow.py`、`test_chat_service.py` | ADAPT | 增加真实现有 Orchestrator/FakeLLM/RAG 状态上下文、多用户及 session 历史断言。 |
| `docs/b2_tool_reuse.md` | NEW | 01/02 运行时代码、测试和 B6 接口审计；不含工具实现。 |
| `docs/b2_integration.md`、`README.md` | NEW / ADAPT | 本报告及 B2 API、安全和本地验收说明。 |

04 工程此前在仓库父级状态中显示为未跟踪目录，因此父级 Git diff 不会逐文件呈现此次改动；本批未暂存或提交。请验收工作区中的文件内容。

## C. CRM 功能完成表

| 字段/功能 | 读取 | 更新/写入 | SQLite 持久化 | 隔离/排序 |
|---|---|---|---|---|
| current_level | PASS | PASS，CEFR A1–C2 规范化 | PASS，原 `user_states` 表 | 按 `user_id` |
| target_level | PASS | PASS，CEFR A1–C2 规范化 | PASS，原表 | 按 `user_id` |
| learning_goal | PASS | PASS，最多 2000 字符；null 清空 | PASS，原表 | 按 `user_id` |
| learning_preferences | PASS | PASS，最多 2000 字符；null 清空 | PASS，原表 | 按 `user_id` |
| learning_events | PASS | PASS，event_type/item/result 参数化写入 | PASS，原 `learning_events` 表 | 按 user_id；created_at/id 倒序；limit 1–100 |

不新增表或 schema 迁移。未注册用户查询返回全空 UserState（HTTP 200），保留 04 原行为。旧 02 `LearningProfile` 另有 daily_minutes、topic、weakness、strength、vocabulary 和 event metadata；04 schema 没有这些列，本批未迁移这些字段或旧 CRM 数据。

## D. 统一 API

身份继续从 `X-User-ID` header 读取。body 不接受 user_id。示例：

```http
PATCH /users/me/state
X-User-ID: local-learner
Content-Type: application/json

{"current_level":"a1","target_level":"B1","learning_goal":"Explain Dativ","learning_preferences":"Simple examples"}
```

响应为 `{"user_id":"local-learner","current_level":"A1","target_level":"B1","learning_goal":"Explain Dativ","learning_preferences":"Simple examples"}`。字段可部分更新，省略字段保留原值，显式 null 清空。空 PATCH、非法等级、空白字符串、超长文本和未知字段均返回 422；缺少/空 header 返回 401。

| 方法/端点 | 结果 |
|---|---|
| GET `/users/me/state` | UserState；初始字段为 null。 |
| PATCH `/users/me/state` | 验证并保存部分状态。 |
| POST `/users/me/events` | HTTP 201，返回含 id 和 created_at 的事件。 |
| GET `/users/me/events?limit=10` | 当前用户最近事件，按时间和 id 倒序。 |
| GET `/sessions` | 当前用户 session 清单，最近更新优先。 |

例如 POST `{"event_type":"practice","item":"Dativ","result":"completed"}` 返回事件 id、传入字段、header 中的 user_id 和 created_at。真实请求/重启读回结果见 E、G。

**安全边界：** `X-User-ID` 是本地 Beta 的调用者自报标识，当前没有认证或授权。不要暴露到不可信网络；v1.0 必须加入认证主体与服务端对象级授权。

## E. Streamlit

04 唯一入口 `ui/streamlit_app.py` 增加轻量侧栏：当前/目标等级、学习目标、学习偏好、保存按钮和最近 10 条事件。增加同一用户下的会话选择/新建；切换用户清除旧 session、profile draft 和上传 fingerprint。后端失败时显示错误，成功保存后刷新确认状态；失败不会覆盖已确认资料或草稿。仍使用既有 `Stage2ApiClient`、FastAPI 和请求超时约定。

21 个 UI/API Client 单测通过；前端进程启动成功，实际 `Stage2ApiClient` 已连接真实 Uvicorn 验证 profile、events、session list、附件上传、聊天及历史读回。AppTest 用模拟后端检查交互和错误状态。**浏览器页面实际操作：BLOCKED**，Codex 浏览器自动审查因账户使用额度拒绝本机页面访问，本轮没有改用其他浏览器或 CDP。

## F. Agent Context

没有改 Orchestrator。新增 FakeLLM 测试用 UserStateService 更新两个用户状态，在普通 NO_TOOL 与德语知识 RAG 请求中读取 `current_level=A1; target_level=B1`、goal 和 preferences；随后重新打开 SQLite Repository 更新 Alice 状态，并验证同一 Orchestrator 后续 Prompt 读取新值、Bob 的 Prompt 不含 Alice 信息。两种路径都通过；RAG 路径也断言已有知识证据进入 Prompt。

## G. 测试

| 检查 | 状态 | 本轮结果 |
|---|---|---|
| 修改前非 TestClient 基线 | PASS | 77 passed，6.37s。 |
| CRM Repository/Service 单测 | PASS | 37 passed，1.54s。 |
| UI/API Client 定向测试 | PASS | 21 passed，3.76s（包含 Streamlit AppTest）。 |
| 完整非 TestClient 回归 | PASS | 129 passed，12.04s，1 条 Chroma 弃用警告。 |
| compileall (`app ui scripts tests`) | PASS | 无语法错误。 |
| 真实 HTTP 与 CRM 扩展 | PASS | health/session/messages/RAG/web controlled failure、profile/events、多用户、validation、session list、attachment 均通过；`scripts/http_acceptance.py --base-url http://127.0.0.1:18770 --crm`。 |
| 后端重启持久化 | PASS | 重启同一临时数据目录后，profile 200、2 events、1 session 读回成功。 |
| Chroma close/lifecycle | PASS | 包含在 129 项全量非 TestClient pytest 中。 |
| TestClient smoke | BLOCKED | 已知 Windows Proactor/AnyIO 启动阻塞，未计入 pytest 通过数；HTTP 由真实 Uvicorn 验收。 |
| 真实浏览器交互 | BLOCKED | 自动审查因账户用量限制拒绝 localhost 页面访问。 |
| 真实 DeepSeek/Tavily | NOT TESTED | 本轮离线 FakeLLM/deterministic embedding；web path 验证为受控失败，不宣称联网成功。 |

正式 `data/` 中 15 个现有 SQLite/Chroma 文件 SHA256 前后相同。所有本轮真实 HTTP 使用 `.http-acceptance-runtime/` 独立临时数据目录。

## H. 兼容性

原 Session、Message、Attachment API 保持原请求/响应；`GET /sessions` 只增加列表能力。真实验收覆盖历史读取、附件上传、聊天、RAG prompt 和 web 离线受控失败；Stage 3 路由和 EvidenceAggregator 文件未修改。Chroma 生命周期回归保持通过。

## I. 遗留问题

- Beta 目前使用调用者自报 `X-User-ID`；没有认证、授权或身份与 session 所有权的可信绑定。
- 02 的 customer/profile 多表、metadata、额外学习偏好字段和用户历史数据没有合并到 04。导入旧 DB 前需要独立映射、备份、回滚和明确迁移授权。
- unknown user 继续返回空状态；事件表不要求先建 profile，保持 04 原 schema 行为。
- 01 Agent Loop/Checkpoint 不接入主链；旧 checkpoint 未实现。MCP、工具规划与真实模型 Function Calling 保持未实现。
- 浏览器页面手工验收被浏览器自动审查阻挡；AppTest 和实际 ApiClient→Uvicorn 验收已通过。

## J. B3 / B6 复用准备

B3 继续保留 04 `UnifiedOrchestrator`、RuleBased/LLM/Hybrid Router、`RouteDecision.mixed_sources`、RAG、Tavily Provider、EvidenceAggregator 和其现有测试；三分类 Router 不加 MCP intent。

B6 的候选组合：以 01 `ToolRegistry` 做唯一工具目录，适配 02 `ToolExecutor` 的执行前重验证、受控失败处理及 01 Function Calling 编码/解析；通过薄 Adapter 接入同一 04 Provider/Orchestrator。Checkpoint 是占位、旧 FunctionCaller 绑定旧 CRM Router、旧 executor 默认工厂会初始化独立 CRM DB；这些均不能直接接入。SQL Guard 还不等于读取表级授权。详细来源、失败边界、测试清单见 [B6 复用审计](b2_tool_reuse.md)。B3–B7 本轮未实施。

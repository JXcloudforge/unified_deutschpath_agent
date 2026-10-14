# 业务模块 Command / Query 合约

更新日期：2026-10-13。参数和结果描述对齐当前 Python 服务，不将 SQLite 行、Chroma 对象或 ORM 泄露给调用方。M08-B 通过现有 Chat 消息端点集成；仅动作响应附加可选 `orchestration` 对象，普通响应保持原结构。

## Auth

Owner: `app.auth`. API Access Token 验证与 OIDC 主体映射，不拥有业务数据。

- DTO: immutable `ActorContext(user_id, identity_source, authenticated, roles, issuer, subject)`; `VerifiedPrincipal(issuer, subject, expires_at, scopes)`; `IdentityRecord(user_id, issuer, subject, enabled, roles, created_at)`. DTO 不包含 token、email 或 ORM row。
- Auth facade: `authenticate(access_token: str) -> ActorContext`. 校验签名（RS256/ES256 allowlist）、issuer、API audience、expiration、subject 和 Access Token marker，再经身份映射返回 actor。无效凭据 `AccessTokenError`；禁用账户 `IdentityDisabledError`；未配置/不可用由 HTTP adapter 映射 503。
- Commands: `resolve_or_create_identity(VerifiedPrincipal)`；server-admin only `set_identity_enabled(actor, user_id, enabled)`、`set_identity_roles(actor, user_id, roles)`。
- Queries: `get_identity(actor, user_id)`，仅本人或已验证 server admin；他人无权限 `IdentityAccessDenied`，不存在 `KeyError`。
- Persistence: Auth 独占 `identity_mappings` SQLite，issuer+subject 复合键，user_id 全局唯一。默认 member 角色来自服务端；access token claims 不授予 admin。
- HTTP boundary: `get_actor_context` 验证 Bearer；production header-only 请求 401。X-User-ID 仅 development、直接 loopback、无 forwarded headers 时可创建未认证本地 Actor。真实 OIDC 未配置，因此 production 请求 fail closed。
- Compatibility: 旧本地账号不自动映射/认领；现有 HTTP paths 与成功 DTO 不变。生产 `Stage2ApiClient(base_url, access_token=..., on_unauthorized=...)` 只发送 Bearer、不发送 X-User-ID；development 兼容原 user_id 参数。401 将 Client 置为失效并调用可选 UI 回调，不重试。
- Streamlit production gate: `st.login(provider)` 后仅服务端取得显式暴露的 `st.user.tokens.access`；缺少 Authlib、OIDC 配置、API audience、登录态或 token 时停止渲染私人工作区。生产 redirect URI 必须为 HTTPS；示例配置位于 `.streamlit/secrets.toml.example`，真实 `secrets.toml` 被 Git 忽略。

## Suggestions (M09)

Owner: `app.suggestions.FollowUpSuggestionService`. The module is read-only and has no repository, database, or Command API.

- Query: `get_follow_up_suggestions(actor: ActorContext, session_id: str, *, maximum: int = 3) -> tuple[FollowUpSuggestion, ...]`.
- DTO: immutable `FollowUpSuggestion(suggestion_id, question, category, reason)`; no persistence entity escapes.
- Dependencies: public `ConversationQueries.get_context_snapshot`; optional `OrchestrationQueries.get_latest_orchestration`. Context limits and owner checks remain owned by Conversation. M09 only reads orchestration status and suppresses output for clarification, awaiting confirmation, executing, or uncertain operations.
- Rules: clamp results to 0–3; only return candidates when the latest user question and assistant answer exist and a supported language-learning topic matches. Deterministic offline strategy currently covers Ausbildung, language levels, grammar, and vocabulary. No LLM, Router, web provider, CRM Command, MCP operation, or business write is called.
- Errors: API treats this optional Query as best effort and omits `suggestions` if an exception occurs; it preserves the already-produced answer.
- Privacy: actor/session isolation is delegated to Conversation Query and M08 Query; no history text is persisted in M09.

## Orchestration (M08)

Owner: `app.orchestration.OrchestrationService`. Its private SQLite repository owns orchestration metadata only in a separate local `orchestration.sqlite3`; it does not own Conversation, CRM, RAG, or MCP business data.

- Commands: `start_orchestration(actor, session_id, user_input, missing_fields=())`; `submit_clarification(actor, orchestration_id, answer, missing_fields=())`; `propose_action(actor, orchestration_id, proposal)`; `revise_pending_action(actor, orchestration_id, proposal)`; `confirm_pending_action(actor, orchestration_id, confirmation_key)`; `resume_uncertain(actor, orchestration_id)`; `cancel_pending_action(actor, orchestration_id)`.
- Queries: `get_orchestration_status(actor, orchestration_id)`; `get_pending_action(actor, session_id)` (raises on multiple candidates); `get_latest_orchestration(actor, session_id)`; `get_route_decision(actor, orchestration_id)`.
- DTOs: immutable `Orchestration`, `OrchestrationStep`, and `RouteSnapshot`; steps expose action, owner, Command/Query kind, parameter snapshot, earlier dependencies, status, result reference, error and order. No database rows escape. Confirmation keys and actor IDs are removed from Chat HTTP responses.
- Executor: `OrchestrationExecutor.execute(actor, session_id, orchestration_id, idempotency_key, proposal) → result_reference`; target modules own actual business validation, authorization, and write transactions.
- Permissions/errors: queries and commands scope every record by `ActorContext.user_id`; missing and foreign IDs both raise `KeyError`. Illegal transitions, stale confirmation, ambiguous candidates, or absent executor raise `ValueError`. Current `X-User-ID` actor remains unauthenticated.
- Transactions/idempotency: conditional SQLite transaction claims `AWAITING_CONFIRMATION → EXECUTING` and consumes the key for the full ordered proposal. At most four acyclic, earlier-step dependencies are accepted. Step state/result commits occur in M08-owned SQLite. A failed dependency blocks later steps; prior success plus later failure is `PARTIAL`. `resume_uncertain` only reconciles writes via an explicitly provided domain Query; read-only queries may be rerun. Separate Chat/M08 transactions cannot guarantee exactly-once.
- Chat adapter Commands: `append_user_message(actor, session_id, content, preserve_session_title=False)` stores a user turn without starting a second Agent response; M08 sets `preserve_session_title=True` so Chat default-title behavior does not mutate business state before plan confirmation. Existing `append_assistant_message` stores the adapter response. `ConversationRenameExecutor` invokes `rename_session(actor, session_id, title)` then `get_session(actor, session_id)` and requires exact title match. `ConversationListSessionsQuery` calls `list_sessions(actor)` and stores a title-only result snapshot.
- Security: API integration defaults off (`M08_LOCAL_ENABLED=false`); enabled only when `APP_ENV=development`, direct peer is loopback, and proxy forwarding headers are absent. All mutation routes fail closed under `APP_ENV=production` because `X-User-ID` is not trusted authentication. This is a local experiment gate, not production authorization.
- Compatibility/migration: isolated M08 SQLite file and `CREATE TABLE IF NOT EXISTS`; no existing user database is migrated. Existing `POST /sessions/{id}/messages` path is unchanged; successful action responses may include additive `orchestration` status. Ordinary chat remains on ChatService.

## Conversation / Chat

公开 DTO 位于 `app/chat/contracts.py`：`ActorContext`、`ConversationSession`、`ConversationMessage`、`ConversationContextSnapshot`、`SendMessageResult`。DTO 为不可变 dataclass；HTTP 适配器显式序列化为既有 JSON 字段。

`ActorContext` 由 `app.auth` 定义并供 Conversation 复用。`from_local_header(user_id)` 仅表示 development loopback 的未认证本地分区值；OIDC actor 由 Auth 验签、audience/issuer/expiry 检查并完成映射后产生。Chat Queries/Commands 每次仍须执行该 actor 的 session owner 检查。真实 OIDC 与 Streamlit 登录尚未验收。

| 接口 | 类型 | 输入 → 输出 | 规则 / 错误 / 事务 |
| --- | --- | --- | --- |
| `create_session(actor)` | Command | ActorContext → ConversationSession | 在 Conversation 内创建空会话；空 Actor 在 DTO 构造阶段 `ValueError` |
| `rename_session(actor, session_id, title)` | Command | ActorContext + ID + 标题 → ConversationSession | 1–100 字符；仅 owner；无会话 `KeyError`，标题非法 `ValueError`；单条 SQLite 更新 |
| `send_message(actor, session_id, content)` | Command | ActorContext + ID + 文本 → SendMessageResult | 校验非空、读取受限上下文、写入用户消息、调用 Agent、保存回答；会话不存在 `KeyError`、空输入 `ValueError`、Agent 失败 `RuntimeError`。为兼容当前行为，Agent 失败时用户消息保留 |
| `append_assistant_message(actor, session_id, content)` | Command | ActorContext + ID + 服务端生成文本 → ConversationMessage | 仅用于可信服务端工作流保存助手结果；空文本 `ValueError`，非 owner/会话不存在 `KeyError`；单条事务提交 |
| `append_user_message(actor, session_id, content, preserve_session_title=False)` | Command | ActorContext + ID + 用户文本 → ConversationMessage | M08 已处理动作时保存当前用户轮次，不触发第二次 Agent；可显式阻止首条消息自动命名；非空、owner scoped、单条事务提交 |
| `upload(actor, session_id, path)` | Command | ActorContext + ID + 已接收文件路径 → `{filename,file_type,characters}` | Conversation 校验归属并保存附件元数据，再请求 RAG 索引；解析错误沿 FileService 语义返回。跨 Chat SQLite 与 Chroma 不使用分布式事务 |
| `get_session(actor, session_id)` | Query | ActorContext + ID → ConversationSession | owner scoped；不存在或非 owner 均 `KeyError`，避免泄露其他用户会话存在性 |
| `list_sessions(actor)` | Query | ActorContext → `list[ConversationSession]` | 仅返回该用户的会话，按最近更新时间排序；只读 |
| `get_messages(actor, session_id)` | Query | ActorContext + ID → 有序 `list[ConversationMessage]` | owner scoped；不存在或非 owner `KeyError`；只读 |
| `get_context_snapshot(actor, session_id)` | Query | ActorContext + ID → ConversationContextSnapshot | 通过公开 Conversation Query 获取历史，再由纯 context builder 裁剪；最多 20 条、12,000 字符；保留最近消息尾部；只读 |

上下文字符限制是确定性的大小上限，不是 tokenizer 精确 token 预算。当前轮用户消息作为独立输入传给 Agent，因此不会被历史裁剪丢弃；系统指令也不从历史读取。摘要存储不是 M07 当前实现，未增加数据库字段或迁移。

`ConversationCommands` 和 `ConversationQueries` Protocol 描述调用方依赖面。`ChatRepository` 仅在 `app.chat` 内部；`app.chat` package 不导出 Repository。`ChatService.from_path` 是 API 组合根的构造入口，内部创建持久化实现。

## 其余现有模块接口

`UserStateService.from_path(path: str | Path) -> UserStateService` 是模块初始化工厂，由 User State 内部构造 SQLite Repository。API 组合根通过此工厂装配服务，不 import Repository。现有 Service Command / Query 的输入输出和 HTTP 路径不变。

FastAPI 附件入口契约：接受 `.txt`、`.md`、`.pdf`、`.docx`，单文件最大 20 MiB；先以 Conversation `get_session(actor, session_id)` 验证归属，再读取最多 `MAX_ATTACHMENT_BYTES + 1` 字节并写入本地暂存目录，最后调用 Conversation `upload` Command。错误分别为不支持类型 415、超限 413、会话不存在/非 owner 404。超限、类型错误和 owner 失败不创建暂存文件。Starlette multipart 解析器先行接收请求，因此应用层限制不等于反向代理/HTTP Server 请求体上限，部署仍需配置传输层限制。

| 模块 | Commands（改变状态） | Queries（只读） | 权限、错误与事务边界 |
| --- | --- | --- | --- |
| User State / CRM | `update_user_state(user_id, **values)`、`save_learning_event(...)` | `get_user_state(user_id)`、`list_learning_events(user_id, limit)` | Service 校验用户/模型，Repository 写入 SQLite；API 组合使用 `from_path`，`X-User-ID` 仍是未认证标识，Service 内 repository 属性仍可见 |
| RAG | `index_documents(namespace, documents)` | `search(namespace, query, top_k)`、`context_for_session(...)` | RAG Service 拥有 embedding/store 规则；名称空间隔离；Chroma 自身管理持久化 |
| Files | 无业务状态 Command | `parse(path) → ParsedDocument` | Parser Registry 按扩展名选解析器；API 附件适配层校验 20 MiB 请求文件上限；长期文件存储所有权待定义 |
| Router | 无业务状态 Command | `route(message, RoutingContext) → RouteDecision` | 输出仅 `rag`/`web_search`/`no_tool`；错误/降级由 Router/Orchestrator 明确处理；不拥有任务持久化 |
| Web | 无业务状态 Command | `search(query, max_results) → WebSearchResponse` | QueryGuard 在外发边界过滤；Provider 抛出明确 WebSearchError 子类；密钥配置不表示联通 |
| MCP Planner | 无数据提交 Command | `plan(...) → MCPToolPlan` | 仅产生受限操作计划；不提交业务数据 |
| MCP Host | stage image、preview、confirm/commit 等受控操作 | pending workflow、latest image 等状态读取 | Host 做用户/session 绑定与一次性授权；Database MCP 负责自己的 SQLite 事务与只读检查；OCR 输出不可信 |
| LLM | 无业务状态 Command | `answer(prompt) → str` | Agent 注入 `LLMClient` Protocol；FakeLLM 和真实 Provider 独立标注 |

## HTTP 兼容契约

M07/M08/M09 不改 POST/GET /sessions、PATCH /sessions/{id}、POST/GET /sessions/{id}/messages、附件与 OCR 路径。发送请求可选增加 `include_suggestions: bool = false`；仅显式开启且有候选时，普通聊天响应额外包含 `suggestions`。旧客户端和默认关闭响应兼容。M08 已处理动作仍可额外包含 orchestration，其步骤 DTO 包含步骤状态与结果，不暴露确认键/Actor ID；动作结果优先于建议。

错误映射：未认证或无效 bearer 401；禁用账户 403；OIDC 缺配置/不可用 503；不存在/非 owner 的会话 404；非法标题或空输入 422；Agent 故障 502。production 无 X-User-ID fallback。Repository 异常不跨越业务/API 边界。更换 SQLite 实现只需替换 Chat 模块内部 Repository，外部服务 JSON paths 不变。


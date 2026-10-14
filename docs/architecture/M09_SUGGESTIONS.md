# M09 后续问题推荐

更新日期：2026-10-13。M09 是可选、只读、离线可运行的推荐 Query，不属于 Router、任务规划器或长期记忆。

## 职责和数据边界

- M09 唯一职责：从当前会话最近一轮用户问题和 Agent 回答中，生成少量可供用户选择的后续问题。
- Conversation（M07）拥有消息和会话；M09 只调用 `ConversationQueries.get_context_snapshot(actor, session_id)`，使用其已裁剪 DTO，不 import Repository 或 SQL。
- M08 拥有编排计划状态；M09 可选调用 `OrchestrationQueries.get_latest_orchestration(actor, session_id)` 读取状态，只在澄清、等待确认、执行中或不确定时抑制推荐，不修改状态。
- M09 不调用 Router、LLM、CRM Command、MCP 或 Knowledge 内部数据库。推荐只是文字建议，不代表事实、授权或已执行动作。
- 推荐无持久化；不建立独立数据库，也不写 Conversation 消息。

## Query 契约

`FollowUpSuggestionService.get_follow_up_suggestions(actor: ActorContext, session_id: str, *, maximum: int = 3) -> tuple[FollowUpSuggestion, ...]`

返回不可变 DTO：`suggestion_id`、`question`、`category`、`reason`。请求上限钳制在 0–3；缺少完整用户问题/助手回答、无可靠主题、上限为 0 或处于 M08 阻塞状态时返回空元组。跨用户会话由 Conversation Query 按 ActorContext 拒绝。读取 M08 状态失败时作为可选查询错误向 API 抛出，由 HTTP 适配器安全省略建议，不影响已生成的答案。

内部 `SuggestionStrategy` 可替换。当前 `DeterministicSuggestionStrategy` 只匹配 Ausbildung、德语水平、语法和词汇主题，不调用 DeepSeek 或联网 Provider。规则返回问题文本，不陈述实时要求；当前天气等不能验证的实时问题不会产生伪造事实。

## Chat/API/UI

- `POST /sessions/{session_id}/messages` 接受可选 `include_suggestions: bool`，默认 `false`。
- 用户响应维持原 `user_message` / `assistant_message`；启用且有结果时新增 `suggestions` 列表。关闭时 Query 不会运行。推荐异常只记录安全日志，回答仍返回；M08 已处理的操作响应不调用 M09。
- Streamlit 提供默认关闭的选项。最多显示三条；按钮只把问题填入 chat input，并清除卡片，用户仍需自行提交。关闭后不显示卡片、不请求 M09。
- `scripts/m09_http_acceptance.py` 使用临时目录和真实 loopback Uvicorn 验证旧请求兼容、显式开启、会话持久化无额外消息及跨用户拒绝；模型是本地 FakeLLM。

## 错误、权限和事务

M09 没有 Command 或事务。API 在既有 HTTP 请求的服务端 ActorContext 下调用，Conversation 和 M08 Query 都执行各自现有用户分区检查。当前身份仍来自未认证的 `X-User-ID`，因此本 Query 不增加任何生产授权能力。推荐异常不会改变原回答的状态码或持久化结果。

## 兼容

旧 HTTP 客户端不发送 `include_suggestions` 时行为和 JSON 主要字段不变；Streamlit API Client 仅在 UI 开关开启时附加此字段。既有成功响应不含 `suggestions` 时仍可正常解析。M09 不修改数据库 schema、版本号、Conversation/M08 状态机或 Router 评测语义。

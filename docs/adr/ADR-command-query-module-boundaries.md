# ADR：以业务模块 Command / Query 封装持久化边界

- 状态：已采纳，阶段四增量实施
- 日期：2026-10-13

## 背景

Unified Agent 已有清晰的主要服务，例如 ChatService、UserStateService、RAGService、Router、Web Provider 和 MCP Host，但部分调用方仍能通过公开属性访问持久化实现。当前最明显的是 FastAPI 从 `chat.repository` 直接列出、改名和读取会话，校验 OCR 会话所有权，并写入确认后的助手消息。ChatWorkspace 本身已通过 Stage2ApiClient 访问 HTTP，并未直接访问 SQLite。

这类耦合使 API 路由了解 Conversation Repository 和 SQLite 返回值；以后更换存储、增加权限检查或上下文策略时，调用方可能绕过模块业务规则。

## 决策

每个拥有业务状态的模块对外提供有类型的 Command 与 Query 服务契约。模块内部保留 Repository、SQL、事务和领域规则。命令仅由所属模块提交；查询执行同样的 owner/访问检查并返回不可变 DTO。API/ChatWorkspace 通过其现有 HTTP/服务适配器消费契约。

M07 作为首个迁移案例：Conversation 模块提供 `ConversationCommands`/`ConversationQueries` Protocol、显式 `ActorContext`、不可变 Session/Message/Context DTO 和预算化 `get_context_snapshot`；FastAPI 改用 ChatService，不再读写 Chat Repository。UI HTTP endpoint 和 JSON 字段兼容。`X-User-ID` 来源显式标为未认证本地命名空间，不能据此宣称生产授权。

## 考虑过的方案

1. **调用方继续直接使用 Repository。** 改动少，但 SQL/事务与数据访问绕开 Conversation 所有权，不接受。
2. **新建第二套 Conversation/Memory 服务和表。** 会复制既有 Session/Message 模型，产生双写与迁移复杂度，不接受。
3. **拆分微服务、独立数据库或事件总线。** 当前为本机应用，没有部署/一致性需求支撑此成本，不采用。
4. **本次重构所有模块。** UserState 组合根、API 文件落盘等边界值得后续处理，但大面积迁移会扩大回归面；本轮以 Chat 的真实直接耦合为范围。

## 取舍与风险

- DTO 与 Protocol 增加少量契约代码，但 Conversation 内 Repository 可替换，且 API 不再了解 SQLite。
- ActorContext 只携带本地 header user ID，不提供 authentication。API 绑定到 loopback 的限制依然有效；正式外部部署必须接入可信身份校验，并从已认证主体创建 ActorContext。
- Chat、CRM 共用 `stage2.db` 文件，但分别拥有自己的表及 Repository。共享 SQLite 文件不等于共享业务写入权。
- Chat 上传还跨 Chat SQLite 与 Chroma；当前没有分布式事务。M07 不扩大该流程，异常补偿和附件存储所有权留作后续边界工作。
- 历史裁剪按字符而不是模型 tokenizer token 估算；它提供稳定上界，不能承诺精确模型 token 量。
- 增量迁移不增加 schema，保留现有表/行，降低回滚风险。

## 后续演进

按 `docs/architecture/MODULE_BOUNDARIES.md` 与 `docs/PHASE4_PLAN.md` 的次序迁移。先完成 Chat 的契约、依赖检查与兼容测试，再单独评审 CRM、附件文件存储和其他已记录的边界。每个模块只在确有状态写入和读取需要时添加 Command/Query；纯函数工具和 Provider 不强行套完整 CRUD。


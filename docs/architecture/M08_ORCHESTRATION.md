# M08 多轮意图与任务编排

## 职责与依赖

M08 仅拥有跨轮编排元数据：路由快照、原始输入、澄清状态、确认提案、执行阶段、错误和结果引用。聊天记录归 M07 Conversation；业务任务属于提供正式 Command 的目标模块；知识与实时信息分别使用既有 RAG/Web 路径。

调用方向：`OrchestrationService → ConversationQueries + IntentRouter + 显式注入的执行器`。Repository/SQLite 只在 M08 内部。Rules Router 仍是 `rag / web_search / no_tool` 三类，没有增加第二 Router。审计未发现通用 Tool Registry 或学习任务创建 Command。MCP Host 的私有工具表和 OCR 人工确认流程只管理自己的能力。

## 接口与 DTO

公开入口为 `OrchestrationCommands`、`OrchestrationQueries`。不可变 DTO 为 `Orchestration`、`RouteSnapshot`，不暴露 SQLite Row。Commands：`start_orchestration`、`submit_clarification`、`propose_action`、`revise_pending_action`、`confirm_pending_action`、`cancel_pending_action`。Queries：`get_orchestration_status`、`get_pending_action`、`get_route_decision`。缺参字段当前由编排策略调用方给出；项目尚无领域参数抽取器，故没有开放不可信 HTTP 字段让客户端决定缺参是否完成。

## Chat/API 集成（M08-B / M08-C）

当且仅当 APP_ENV=development 且显式设置 M08_LOCAL_ENABLED=true 时，API 组合根才构造 M08ChatAdapter。POST /sessions/{id}/messages 先用 Conversation Query 校验会话归属，再让适配器处理受支持的本地动作；未识别的普通聊天返回原 ChatService，继续使用原 Router/Agent/RAG/Web 路径。适配器支持 rename_session 单动作及固定的 rename_session → list_sessions 组合，通过原消息接口输出附加 orchestration 字段，不新增 HTTP 路径。

调用链：`HTTP → ActorContext(未认证本地 namespace) → Conversation Query → M08 Query/状态判断 → Conversation Command(保存用户消息/rename_session) → Conversation Query(结果核验) → Conversation Command(保存助手回复)`。确认、澄清和提案修订每轮各保存一条用户消息和一条助手回复；编排元数据只存 M08 自己的 SQLite。执行器接收显式注册的 Conversation Commands/Queries，不访问 Repository。

确定性识别支持单动作改名，以及精确限定的“把当前会话改名为 X，然后列出我的会话”双步骤计划。双步骤结构、参数、依赖和结果由 M08 自己存储；确认绑定完整提案版本。标题缺失时追问，下一轮继续同一计划。仅注册真实 Conversation `rename_session` Command 与 `list_sessions` Query。其他多意图或未支持动作明确拒绝/澄清；LLM 输出不构成执行计划或授权。

## 状态机

```text
CREATED → NEEDS_CLARIFICATION → READY → AWAITING_CONFIRMATION → EXECUTING → SUCCEEDED
              ↕                                  ↘ CANCELLED       ↘ FAILED
              CANCELLED
AWAITING_CONFIRMATION → EXECUTING → UNCERTAIN
UNCERTAIN → SUCCEEDED（仅 Query 读回匹配后核对）
READY → CANCELLED
```

确认键绑定整个计划提案的修订版本；提案修订会替换步骤并清除旧键。每个步骤有独立 PENDING/RUNNING/SUCCEEDED/FAILED/UNCERTAIN/BLOCKED 状态。Command 失败阻止依赖 Query；前置步骤成功而后续 Query 失败时计划记录为 PARTIAL。多条待处理记录时查询报歧义，不猜测。仅支持受限确定性双步骤，不提供任意任务分解器。

## 授权、幂等与失败

所有命令和查询按 ActorContext 用户分区检查，并再次通过 Conversation Query 校验会话归属。当前 ActorContext 来自未认证 Header，不能用于生产授权。API 的所有写入在 `APP_ENV=production` 时 fail-closed；M08 默认关闭，即使在 development 打开也拒绝非直连 loopback 或包含 forwarded headers 的请求。旧的会话改名 PATCH 同样只允许 loopback development。该门禁不是生产身份认证 PASS。

确认以条件更新原子领取计划并消费确认键。同进程并发确认遇到 EXECUTING 时返回处理中。development API 单进程启动时将遗留的 EXECUTING/RUNNING 标记为 UNCERTAIN。不确定的 Command 只能通过目标模块提供的 Query 核对；核实成功后允许继续剩余的已确认只读步骤。不确定的 Query 可以安全重跑。无法核实时保持待核查，绝不自动重放写入。已完成步骤不会再次执行。两个 SQLite 不共享事务，严格 exactly-once 无法保证；无法核实时需要人工检查。

## 持久化与迁移

状态存放于独立 orchestration.sqlite3，由忽略规则覆盖。M08-C 仅新增自有 orchestration_steps 表，使用 CREATE TABLE IF NOT EXISTS，不改现有 Chat/CRM 表。旧版单动作提案可兼容装载为一个步骤。真实 loopback Uvicorn 验证计划跨重启后继续执行；临时 SQLite 测试验证不确定 Command 通过 Query 核对后继续只读步骤。

选择独立状态所有权及持久化的取舍见 [M08 ADR](../adr/ADR-m08-orchestration-state.md)；有界顺序计划与故障恢复见 [M08-C ADR](../adr/ADR-m08-bounded-sequential-plan.md)。

## 覆盖和遗留

M08-C 覆盖范围是 rename_session → list_sessions。自然语言识别采用确定性规则，不消费完整历史做通用语义理解。学习任务/CRM Command、任意工具规划、其他多意图、真实联网调度及可信生产认证仍未实现。参见 docs/PHASE4_M08_ACCEPTANCE.md 和 docs/PHASE4_M08C_ACCEPTANCE.md；阶段三独立 Router 集和外部服务门槛仍阻塞正式发布。

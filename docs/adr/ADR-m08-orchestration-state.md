# ADR: M08 编排状态的独立所有权与持久化

- 状态：已采纳（仅限 M08 基础状态服务；端到端方案仍待验收）
- 日期：2026-10-13

## 背景

M07 拥有会话和消息，MCP Host 拥有 OCR 确认工作流。审计没有发现可供跨业务复用的任务状态模块、通用 Tool Registry 或学习任务创建 Command。将编排状态塞入 Conversation 会混淆会话历史与任务生命周期；直接写 CRM/MCP 表会绕过目标模块规则。

## 决策

M08 独占自身路由快照、澄清、确认提案、尝试状态、错误和结果引用。它通过公开 `ConversationQueries` 校验/读取会话快照、通过既有 `IntentRouter` 产生 RouteDecision、并且只能调用显式注入的 `OrchestrationExecutor`。M08 使用独立本地 `orchestration.sqlite3`；Repository/SQLite 对外隐藏。状态变更以事务和期望状态条件更新实现。确认键绑定提案修订并在执行认领时单次消费。无 executor 时 fail-closed。

## 备选方案

1. 把任务状态放进 Chat SQLite/消息 JSON：拒绝，Conversation 不应拥有任务生命周期，且会将任务状态与历史持久化耦合。
2. 复用 MCP Host 的 `mcp_workflows`：拒绝，该表和 Host API 只属于 OCR/Database 工作流，不能扩展为通用任务存储。
3. 直接使用现有 CRM：拒绝，未发现目标任务表或公开 Command；UserState/learning_events 不代表任务管理。
4. 新增微服务、消息队列或分布式事务：拒绝，当前没有容量或一致性需求支持这些成本。

## 后果与风险

- 新增一个本地状态文件，无需迁移用户 Chat DB；忽略规则覆盖 `*.sqlite3`。
- 两个 SQLite 不构成跨模块事务。业务 executor 必须通过目标模块公开 Command，且自行实现权限与幂等；不能据 M08 的状态键推断业务提交已发生。
- 进程若在 `EXECUTING` 中退出，当前没有自动结果核对/恢复 Command；状态不可盲目重放。需在接入真实副作用前补齐核对流程。
- 目前 ActorContext 仍来自未认证的本地 Header；此实现只适用于受限本地测试，不能开放生产写入。
- 当前状态服务未接入 Chat/API，M08 工程封板仍受 CRM Command、领域规划和多轮语义集成阻塞。

## 演进

当目标任务模块和可信 Actor 契约明确后，通过 executor adapter 调用其公开 Command；由 M10 契约/集成测试验证权限、幂等、超时与重启恢复。若任务需要跨请求并发/多进程部署，再评估持久化实现；当前不引入事件总线或分布式事务。

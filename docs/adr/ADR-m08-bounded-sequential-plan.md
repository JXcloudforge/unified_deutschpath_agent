# ADR: M08 有界顺序计划与步骤恢复

- 状态：已采纳（仅适用于受限 M08-C 工作流）
- 日期：2026-10-13

## 背景

M08-B 将一个确认动作与 Conversation Command 连接起来。下一步只需协调一个明确的 Command 和一个依赖它的 Query。Conversation 与 M08 各自拥有独立 SQLite，因此两模块无法共用事务。

## 决策

计划继续由 OrchestrationService 拥有，在 M08 SQLite 添加自有步骤表。每个提案版本在整体确认后串行执行，步骤保存 action、所属模块、Command/Query 类型、参数、前置依赖、状态、结果和错误。

首个多步骤能力只接受确定性解析的 rename_session → list_sessions。执行器分别调用公开 Conversation Command 和 Query。Query 只能在 rename Command 经 get_session 核验成功后运行。Conversation 默认会对第一条消息自动命名；M08 保存提案轮次时显式保留原标题，避免确认前改变目标业务数据。

执行器在进程中以条件状态更新领取一次计划。执行结果未知时，对写步骤调用所属模块 Query 核对；核对成功才继续已确认计划中的只读步骤。失败或不确定不会自动重放写入。已完成步骤不重跑，失败的依赖步骤记为 BLOCKED，部分完成记为 PARTIAL。

schema 升级仅在 M08 自有数据库添加 orchestration_steps 表，使用 CREATE TABLE IF NOT EXISTS。旧版单动作 JSON 兼容映射为一步，不修改 Conversation/CRM schema。

## 取舍

- 顺序执行较简单、可审计，足以验证 Command → Query 依赖；不引入并发调度、消息队列或通用规划框架。
- 四步上限与只能依赖前置步骤限制了状态和恢复复杂度。
- 独立 SQLite 的事务提交边界意味着不能承诺 exactly-once；未知写入必须停止等待 Query 核查。
- 原 Router 不变；M08 的局部确定性语法不影响旧 Router 评测语义。
- 本地 M08 开关默认关闭；loopback gate 不代表生产身份认证。

## 后续演进

增加动作前，先确认目标模块已公开、经过测试的 Command/Query 及权限语义，再注册适配器并补充恢复 Query。CRM 学习任务、MCP 副作用、RAG/Web 编排和多意图规划不由此 ADR 自动授权。

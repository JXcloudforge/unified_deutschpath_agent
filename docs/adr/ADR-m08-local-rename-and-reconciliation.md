# ADR: M08 本地重命名闭环与不确定结果核对

- 状态：已采纳（限定 M08-B；不代表生产认证或通用编排）
- 日期：2026-10-13

## 背景

M08-A 有独立持久化状态机，但缺少 HTTP/Conversation 业务闭环。Conversation 与 M08 各自拥有 SQLite，跨库事务不可用。生产 Actor 仍来自未认证的 `X-User-ID`。

## 决策

复用现有 `POST /sessions/{id}/messages`，由 API 组合根在显式 `M08_LOCAL_ENABLED=true` 且 `APP_ENV=development` 时装配 `M08ChatAdapter`。adapter 只处理确定性识别的 `rename_session`，提案须有用户确认；执行器只通过 Conversation Commands/Queries 调用 `rename_session` 并读回核验。其他 Chat 请求回到原 ChatService。

M08 默认关闭。直接 loopback peer 且没有 forwarded headers 是开发门禁；production HTTP mutation 因身份未可信而拒绝。执行前以条件更新领取提案。若 Command 结果不确定，恢复时 Query 业务状态：匹配则记录核验成功，不匹配或不可读则要求人工核查，不重试写入。

## 取舍与风险

- 保持 HTTP 路径、普通聊天路径和 Conversation schema 不变；动作响应仅增加可选字段。
- 两份 SQLite 不共享事务，确认键只能保证 M08 提案单次领取；无法承诺严格 exactly-once。
- 本地 peer gate 不应被视为生产身份认证；部署代理也不能伪造可信客户端 IP。当前配置仍是实验性开发能力。
- 自然语言规则范围有限；多意图、复杂规划和 CRM/学习任务不在决策范围内。

## 后续演进

增加动作前，先确认目标数据所有模块和公开 Command/Query，再提供独立、显式注册的执行器与参数/授权契约；补充执行失败和恢复测试。不创建第二套 Router 或共享 Repository。需要生产启用前，应先由可信认证层创建 ActorContext 并重新审查 HTTP 写入策略。

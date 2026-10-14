# 阶段四问题修复与工程优化记录

本记录将 M07–M10 的实际实现与验收报告归纳为课程提交材料，不把计划项或历史候选集成绩表述成正式生产通过。

| 问题 / 风险 | 修复或设计处理 | 验证证据 | 边界 |
|---|---|---|---|
| ChatWorkspace 原先与 Conversation 存储实现有直接耦合风险 | 会话、消息、改名及历史访问经 Conversation Commands/Queries；UI 使用 API Client/HTTP | M07 / architecture acceptance；API 与架构测试 | UserState/附件长期字节所有权仍需继续审查 |
| 重启后对话历史与上下文延续 | SQLite 持久化会话与消息，Context Snapshot 以 20 条和 12,000 字符为界 | Conversation contract、M08/M09 HTTP acceptance | 限制按字符而非精确 Token；无持久化摘要 |
| 缺少参数时误执行或跨轮提案丢失 | M08 对会话改名支持澄清、跨轮补齐、确认键随提案修订旋转 | `tests/unit/test_orchestration_service.py`、M08-B/C acceptance | 仅支持白名单动作；不是通用规划器 |
| 业务命令成功但编排状态可能未知、重复确认可能造成重复写入 | Command 前持久化执行状态；确认领取有条件更新；命令后以 Conversation Query 读回；重启中的 RUNNING 进入 UNCERTAIN，不盲目重放 | M08-B/C 并发、重复确认、重启与 HTTP 测试 | 两个 SQLite 无共同事务，不保证严格 exactly-once |
| M08 将状态标记成功不能证明实际业务操作成功 | `ConversationRenameExecutor` 调公开 `rename_session` Command，再调用 `get_session` Query 验证实际标题；双步骤 Query 只在首步骤核验成功后执行 | M08-C loopback HTTP 报告 | 真实公网身份尚未通过；M08 mutation production 关闭 |
| M09 建议可能打断主回答或误触发写操作 | 默认关闭、只读 DTO、最多 3 条；异常不遮盖回答；按钮只预填输入框 | M09 HTTP/AppTest 与只读状态比较 | 确定性策略覆盖有限学习主题 |
| M09 关闭功能时新增请求关键字破坏旧 Chat Client mock/契约 | 关闭时继续走原三参数接口；只有显式开启才传 `include_suggestions` | M09 acceptance 中首次回归修复记录；兼容性测试 | 不改变旧 HTTP 必需字段 |
| 身份不能依赖任意客户端 `X-User-ID` | Auth 验证边界、production fail-closed、Streamlit Bearer Client 接线 | Fake RSA/JWKS 与本机 HTTP/UI 契约 | 无真实 IdP；本机模拟不等于生产认证 |
| Router 开发集成绩可能误被宣传为独立验收 | 明确三类标签 `rag/web_search/no_tool`；150 题独立集的双标、裁决和 hash freeze 工具拒绝缺失裁决 | Router evaluator 单测 | 150 项仍 unreviewed；任何 300 题结果均为工程开发证据 |
| 仅按完整测试套件结果无法覆盖独立 API Smoke | 全量脚本显式排除 Smoke，发布说明要求单独运行与统计 | `docs/PHASE4_M10_ACCEPTANCE.md` 与 README 命令 | 本次副本 Smoke 独立结果待本报告更新 |

## 调用和验收链

```text
ChatWorkspace → Stage2ApiClient → FastAPI Actor dependency
  → Conversation Query / Context Snapshot
  → existing IntentRouter and UnifiedOrchestrator
  → optional RAG / Web / MCP flow
  → Conversation Command persists answer
  → optional M09 read-only suggestions

Explicit bounded M08 action:
  M08 proposal → user confirmation → Conversation rename Command
  → Conversation get_session Query verifies title
  → optional list_sessions Query → persist M08 result
```

测试分类和真实 Provider 限制详见 `docs/PHASE4_M08_ACCEPTANCE.md`、`docs/PHASE4_M08C_ACCEPTANCE.md`、`docs/PHASE4_M09_ACCEPTANCE.md`、`docs/PHASE4_M10_AUTH_UI_ACCEPTANCE.md`。

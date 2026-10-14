# M08 工程验收记录

日期：2026-10-13。版本仍为 `0.1.1.dev0`。下方“M08-B 最小真实业务闭环”是本轮增量验收；早期 M08-A 记录保留作为历史，不再作为当前 Chat/API 集成状态。

## M08-B 最小真实业务闭环

### 公开调用链和范围

现有 `POST /sessions/{session_id}/messages` 在显式本地开关开启时，先经 `ConversationQueries.get_context_snapshot` 校验 actor/session 归属，再由 `M08ChatAdapter` 识别有限范围的 `rename_session`。Adapter 经 M08 Commands 管理澄清/提案/确认状态，经 Conversation Commands 保存用户与助手轮次及调用 `rename_session`，再由 `ConversationQueries.get_session` 读回验证。普通问题返回既有 `ChatService.send_message`；HTTP 路径未变，动作成功响应仅增添可选 `orchestration` 字段。

数据证据层级：

- Fake executor / state machine：`tests/unit/test_orchestration_service.py`。
- 真实 Chat SQLite Commands/Queries + TestClient：`tests/integration/test_m08_chat_integration.py`。
- 真实 loopback HTTP + Uvicorn 重启 + 临时 Chat/M08 SQLite：`scripts/m08_b_http_acceptance.py`。FakeLLM 仅用于普通问答离线路径，不声称外部模型联通。

### 场景矩阵

| 场景 | 状态 | 本轮证据/边界 |
| --- | --- | --- |
| A 普通问题回到旧 Router/Chat 路径 | PASS | TestClient 与 loopback HTTP；FakeLLM/既有规则路由 |
| B rename 提案提取并等待确认 | PASS | 真实 HTTP 响应和 M08 持久化状态 |
| C 缺标题澄清、下一轮继承原提案 | PASS | TestClient + HTTP；原 orchestration ID 延续 |
| D 确认调用 Conversation Command 并 Query 读回 | PASS | TestClient 与 loopback HTTP 读取会话列表验证标题 |
| E 重复/并发确认不重放写入 | PASS | 同步重复确认及真实适配器并发测试；活动态只返回处理中，executor 调用一次 |
| F 提案修订使旧确认失效 | PASS | token 轮换及旧提案确认拒绝 |
| G 跨用户不能读取或确认 | PASS | TestClient Query 隔离与 HTTP 404 |
| H 服务重启后恢复待确认状态/遗留执行态 | PASS | Uvicorn 进程重启恢复待确认提案；单测验证遗留 `EXECUTING` 转 `UNCERTAIN` |
| I 多个待处理提案时拒绝模糊确认 | PASS | Orchestration Query/Service 单测；无自然语言合并 |
| J Command 失败不虚报成功 | PASS | 失败状态和非成功反馈测试 |
| K Command 提交后响应丢失/未知状态安全恢复 | PASS | Query 匹配后记录核验成功；不重复调用 executor |
| L 生产未认证身份写入禁止 | PASS（fail-closed gate） | API 单测；不构成生产身份认证通过 |
| M M08 关闭时兼容旧 Chat | PASS | 测试确认普通请求仍到原 ChatService |

### 本轮命令及结果

| 命令 | 结果 |
| --- | --- |
| `\.venv\Scripts\python.exe -m pytest tests/unit/test_orchestration_service.py tests/integration/test_m08_chat_integration.py -q` | 16 passed，0 failed，0 skipped；含 2 条上游弃用警告 |
| `\.venv\Scripts\python.exe scripts/m08_b_http_acceptance.py` | 退出码 0；真实 loopback Uvicorn 两进程重启；health/普通聊天/澄清/重启后确认/重复确认均 200，跨用户 404，Query 验证标题 `Deutsch final`，历史 14 条，未支持写操作被拒绝 |
| `\.\scripts\run_tests.ps1` | 退出码 0；222 passed，1 skipped，0 failed，74.76 秒。被跳过项：`tests/unit/test_ocr_mcp.py:104`，当前 Windows 账户不支持 symlink 创建 |
| `\.venv\Scripts\python.exe -m pytest tests/integration/test_api_smoke.py -q` | 退出码 0；1 passed，0 failed，0 skipped。单独运行，不计入上面的全量套件数字 |
| `\.venv\Scripts\python.exe scripts/mcp_b6_http_acceptance.py` | 退出码 0；真实 Uvicorn + stdio MCP，health/session/upload/OCR/confirm 均 200，跨用户 404，确认前 0 行、确认后 3 行 verified，正常关闭 |
| `\.venv\Scripts\python.exe -m compileall -q app ui scripts tests` | 退出码 0 |
| `git diff --check` | 退出码 0；有 Git LF/CRLF 转换提示，不是 whitespace error |

### 身份、幂等和恢复边界

`M08_LOCAL_ENABLED` 默认 `false`；M08 adapter 只在 `APP_ENV=development` 组合。启用后仍要求直接 loopback peer 且没有 forwarding headers。`APP_ENV=production` 时所有 HTTP mutation fail-closed，因为现有 `X-User-ID` 不是可信身份。M08 状态库和 Conversation SQLite 分别提交，无法提供严格 exactly-once。状态停在 `EXECUTING/UNCERTAIN` 时，重复确认只调用 Conversation Query 核对目标名称；匹配则记录核验成功，不匹配或查询失败则保持需核查状态，不自动重新写入。

### M08-B 判定

**M08-B 最小真实业务闭环验收通过。** 本轮 HTTP/SQLite 闭环、并发领取与启动恢复、项目全量套件及独立 Smoke/静态检查均完成。此结论不扩展到 CRM/学习任务写入、通用 Tool Registry、复杂任务分解、多个动作规划、真实 DeepSeek/Tavily 调度、可信生产认证。阶段三 Router 150 题独立人工验收、真实外部 API、MCP Inspector GUI 和生产身份仍阻塞 v1.0。

M08-C 的受限双步骤验收单独记录于 docs/PHASE4_M08C_ACCEPTANCE.md，不改变本文件对 M08-B 范围的描述。

## M08-A 历史记录

## M08-0 审计

| 能力 | 状态 | 证据/限制 |
| --- | --- | --- |
| Rules / Hybrid Router | EXISTS | `IntentRouter.route(message, RoutingContext) → RouteDecision`，三分类 `rag/web_search/no_tool`。 |
| Agent 通用多步任务规划 | MISSING | `UnifiedOrchestrator` 路由后处理 RAG/Web/LLM 答复，不维护通用多步状态。 |
| 通用 Tool Registry | MISSING | `MCPHost.TOOL_REGISTRY` 是 MCP Host 私有目录，不是跨业务 Registry。 |
| CRM task Command | MISSING | 有 UserState Command，但未发现学习任务创建 Command。 |
| Conversation Query | EXISTS | M07 `get_context_snapshot(actor, session_id)`，最多 20 条/12,000 字符。 |
| 待确认操作 | EXISTS（限定用途） | MCP Host 仅处理 OCR 候选经人工核对后的数据库写入。 |
| 缺参/通用任务状态 | NEEDS_EXTENSION | 本次增加通用状态容器和显式澄清 Command；自然语言字段提取、对话集成缺失。 |
| Router 独立评估 | NEEDS_EXTENSION | 开发集不替代 150 题人工独立验收。 |

## 实现及测试证据

新增 `app.orchestration` DTO、Commands/Queries、独立 SQLite Repository 和状态服务。SQLite 事务条件更新处理状态，Proposal revision 确认键单次消费。执行异常记为 `FAILED`，不自动重试。未注册执行器拒绝确认执行。没有更改已有用户数据库。

`python -m pytest tests/unit/test_orchestration_service.py -q`：8 passed，0 failed，0 skipped。测试使用 Fake Conversation Query/Router/Executor 和临时数据库，不代表模型、外部服务或目标业务 Command 的真实联通。

## 测试矩阵

| 场景 | 状态 | 说明 |
| --- | --- | --- |
| 普通知识路由、只读 Query | PASS（单测） | 复用既有 Rules Router。 |
| 两任务并发候选拒绝歧义 | PASS（状态 Query 单测） | 未验证自然语言多意图拆分。 |
| 缺参澄清/跨轮原提案继承 | PASS（契约单测） | 缺参字段由调用者给定，没有自动提取器或 Chat 闭环。 |
| 单工具/CRM 任务创建 | NOT VERIFIED | 缺少通用 Registry 和目标 Command。 |
| 匹配确认、重复确认、取消 | PASS（Fake 单测） | 未接入真实业务副作用。 |
| 参数变化后旧确认失效 | PASS（单测） | 修订提案轮换确认键；旧键拒绝。HTTP 流程未接入。 |
| 重启恢复、跨用户隔离、只读无副作用 | PASS（临时 DB 单测） | 生产认证仍未实现。 |
| 工具异常/超时 | PASS（Fake 单测） | 写入失败状态，不自动重试未知结果。 |
| 混合来源/联网不可用 | NOT VERIFIED（超出 M08-B 范围） | 本轮仅连接重命名 Conversation Command，不负责联网/混合来源任务调度。 |
| M07 长上下文快照参与意图理解 | NOT VERIFIED | 当前查询快照做授权边界验证，未使用消息内容做任务语义组装。 |

## 本轮集成回归记录

- `scripts/run_tests.ps1`：214 passed、1 skipped、0 failed，退出码 0，74.96 秒；skip 原因是 Windows symlink 创建受限；一条 Chroma 上游弃用警告。
- `python -m compileall -q app ui scripts tests`：退出码 0。
- `git diff --check`：退出码 0；Git 显示工作树中若干文件存在 LF/CRLF 转换提示。
- `.\\.venv\\Scripts\\python.exe scripts/mcp_b6_http_acceptance.py`：退出码 0；真实 loopback Uvicorn 与 stdio MCP，health/session/upload/OCR/confirm 均 200，跨用户确认为 404，确认前 0 行、确认后 3 行验证，正常关闭。
- 历史 M08-A 阶段的说明：全局解释器曾运行失败，项目虚拟环境复测通过。该旧 Smoke 当时仅覆盖 MCP/Conversation；当前 M08 API 闭环由本节列出的 `scripts/m08_b_http_acceptance.py` 单独覆盖。

## M08-A 当时的封板阻塞（状态更新）

1. 定义学习任务归属模块及正式 Command（输入、授权、返回、幂等语义）。
2. 实现可信认证 ActorContext；不得把 `X-User-ID` 当作生产授权。
3. Chat/API 的受限 `rename_session` 多轮闭环已由 M08-B 实现；跨轮通用语义理解和缺参抽取仍未实现。
4. 不需要为了 M08-B 引入通用 Registry；若未来增加目标业务动作，应先有正式 Command/Query，并实现适配器与故障核对契约。
5. 多意图拆分、其他真实目标 Command、广泛 M07/RAG/Web/MCP 调度及完整 API 场景仍未验证。
6. 单独完成 Router 150 题冻结独立验收及阶段三真实服务门槛。

回滚只移除 M08 新文件及文档；当前没有生产调用方。M08 独立状态库可保留归档，不影响现有会话历史。不得对真实 Chat DB 做迁移试验。

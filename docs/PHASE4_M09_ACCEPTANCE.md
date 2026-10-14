# M09 后续问题推荐验收

日期：2026-10-13。版本保持 `0.1.1.dev0`。M09 是可选的只读推荐能力；其实现与本次复测证据记录在此。

## 现状审计

| 项目 | 审计结论 | 证据 / 处置 |
|---|---|---|
| Conversation Query 与上下文快照 | EXISTS | `get_context_snapshot` 返回不变 DTO，按用户校验并限制最近 20 条/12,000 字符；M09 复用 |
| Orchestration Query | EXISTS | `get_latest_orchestration` 按 actor/session 读取；M09 只读取状态 |
| Chat/API 响应 | NEEDS_EXTENSION | 既有发送结果可选扩展，增加默认 false 的 `include_suggestions` 和仅有建议时的 `suggestions` |
| Streamlit 快捷问题 | MISSING | 增加默认关闭开关和“填入输入框”按钮；不自动提交 |
| 既有推荐服务或配置 | MISSING | 无；新增小型 `app.suggestions`，不增加 DB 或依赖 |
| 用户偏好持久化 | MISSING | 不新增存储；UI 运行期偏好默认关闭 |

## 实现与调用链

API 收到普通 Chat 消息 → Conversation 保存问题和真实回答 → 请求显式开启推荐时，M09 Query 读取有界 Conversation Context Snapshot → 可选 M08 Query 检查活动状态 → 离线确定性策略产生最多三条 DTO → API 将可选字段与原答案一起返回 → UI 展示问题按钮 → 用户点击只预填输入框 → 用户明确提交后才发新 Chat 请求。

策略支持 Ausbildung、德语等级、语法和词汇学习主题；无可靠主题返回空列表。没有 DeepSeek Key 也不影响主对话，因为当前策略不调用 LLM。天气等实时问题无相应推荐，避免编造实时信息。

## 测试证据

| 类型 | 命令 | 结果 |
|---|---|---|
| M09 单元 / UI 契约 / TestClient HTTP 集成 | `.venv\Scripts\python.exe -m pytest tests\unit\test_suggestions.py tests\integration\test_m09_suggestions_http.py tests\unit\test_ui_contracts.py -q` | exit 0；28 passed，2 warnings |
| M09 真实 HTTP E2E | `.venv\Scripts\python.exe scripts\m09_http_acceptance.py` | exit 0；loopback Uvicorn；默认响应无推荐、显式开启返回 3 条匹配 Ausbildung 的建议；会话历史仅 4 条，跨用户读取 404 |
| 全量回归 | ` .\scripts\run_tests.ps1` | exit 0；244 passed，1 skipped，0 failed；skip 为 Windows 账户无法创建 symlink 的 OCR/MCP 用例 |
| API Smoke | `.venv\Scripts\python.exe -m pytest tests\integration\test_api_smoke.py -q` | exit 0；1 passed，2 warnings |
| M08-B HTTP | `.venv\Scripts\python.exe scripts\m08_b_http_acceptance.py` | exit 0；真实 loopback Uvicorn；普通聊天、澄清、跨用户拒绝和重启后确认通过 |
| M08-C HTTP | `.venv\Scripts\python.exe scripts\m08_c_http_acceptance.py` | exit 0；真实 loopback Uvicorn；重启后两步骤成功，名称读回正确 |
| MCP B6 HTTP | `.venv\Scripts\python.exe scripts\mcp_b6_http_acceptance.py` | exit 0；真实 Uvicorn/stdio MCP；确认前 0 行、确认后 3 行，跨用户拒绝 |
| 编译 / 差异 | `.venv\Scripts\python.exe -m compileall -q app ui scripts tests`；`git diff --check`、`git diff --cached --check` | 均 exit 0 |

测试区分本地 SQLite 服务、FastAPI TestClient 合成 HTTP 链路、真实 loopback Uvicorn HTTP 与 Streamlit AppTest 组件交互。真实 M09 HTTP 使用本地 `FakeLLM`，证明 API 请求/会话/持久化/响应链路，不证明 DeepSeek/Tavily 等外部服务或生产认证。

## 验收矩阵

| 条目 | 状态 | 说明 |
|---|---|---|
| 离线相关推荐、重复去除、0–3 数量、上下文限制 | PASS | 单测覆盖规则、截断、空上下文及重复过滤 |
| 关闭推荐不调用服务；缺少 API Key 时主聊天正常 | PASS | HTTP Spy 验证默认关闭不调用；确定性策略没有 API Key 依赖 |
| 实时信息不伪造 | PASS | 不支持的实时主题返回空列表 |
| 澄清、确认、执行中、不确定状态优先 | PASS | M08 状态 Query 只读抑制；HTTP 覆盖待确认状态 |
| 无业务写入和跨用户隔离 | PASS | SQLite 状态前后对比无变化；外部 Actor 不能读取会话快照 |
| 推荐异常回退、HTTP 兼容、UI 点击填入 | PASS | 旧响应可解析；异常不影响回答；真实 HTTP 与 Streamlit AppTest 点击后只预填输入框 |
| 生产认证、Router 独立人工集、DeepSeek/Tavily 实测、MCP Inspector | NOT VERIFIED | 继续列为 M10/v1.0 阻塞项 |

## 遗留与回滚

当前只覆盖四类确定性主题，其他主题可以通过替换/扩展 `SuggestionStrategy` 加入；不应改动 Router 意图定义。回滚可移除 `app/suggestions`、请求适配、Streamlit 控件和相应测试/文档；无数据库迁移，旧客户端契约保持可用。M10 应补真实 UI 截图、生产身份与全发布门槛验收证据。

## 回归中发现与修复

首次全量回归出现 2 个既有 Streamlit Chat 测试失败：关闭推荐时新 UI 仍向旧 API Client mock 传递 `include_suggestions=False`，破坏三位置参数的调用兼容。修复为仅在明确开启时传入新增关键字参数；关闭状态继续调用既有三参数接口。两个原失败用例和 M09 HTTP/UI 定向复测通过，随后全量回归为 244 passed、1 skipped、0 failed。

# M10 系统验收报告

> 历史快照说明：下方 Git remote 与工作树信息描述 2026-10-13 的开发源目录，不适用于独立发布副本。发布副本从 `https://github.com/JXcloudforge/unified_deutschpath_agent.git` 正常 clone，保留目标仓库历史与正确 origin。

日期：2026-10-13。验收版本：`0.1.1.dev0`。本报告记录 M10 第一轮的历史测试快照；不构成 v1.0.0 正式验收。后续 Auth-C 和当前冻结范围分别见 [`PHASE4_M10_AUTH_UI_ACCEPTANCE.md`](PHASE4_M10_AUTH_UI_ACCEPTANCE.md) 与 [`V1_RELEASE_SCOPE.md`](V1_RELEASE_SCOPE.md)。

## 环境与工作树

- Windows PowerShell；Python `3.14.6`；FastAPI `0.141.1`；Streamlit `1.65.0`；httpx `0.28.1`。
- 分支 `main`；remote `origin` 仍指向 `https://github.com/JXcloudforge/CRM-agent.git`，名称/地址与 Deutschpath 工程不一致，发布前必须核实目标仓库。
- 起始工作树已有大量 staged、unstaged、untracked 与删除项，包括旧 `02_crm_agent` 树的删除。此次不清理、不暂存、不提交；现存用户数据也不纳入 Git 操作。
- `.env` 与运行数据由 `.gitignore` 忽略；检查到真实本地 `.env` 配置了 DeepSeek/Tavily 密钥，但没有读取或输出密钥。本轮没有发起外部 API 请求。

## 模块与数据边界审计

| 模块 | 状态及证据 |
|---|---|
| Conversation / Chat | PASS：ChatService Commands/Queries 拥有会话、消息、附件元数据；SQLite 重启恢复和隔离 HTTP 案例通过。上传文件本体暂存仍由 API 路径承载，长期归属及失败清理需后续设计。 |
| Agent / Orchestration | PASS（限定范围）：Agent 协调 Router、RAG、Web、LLM、UserState；M08 自有 SQLite 持久化提案/步骤。真实 M08-B/C loopback HTTP 通过。通用任务规划、CRM 写入和任意工具规划未实现。 |
| Rules / Hybrid Router | PASS（离线路径）；独立验收 NOT VERIFIED：规则输出 `rag/web_search/no_tool`，Hybrid 可接入 LLM。300 开发集记录不能替代 150 人工盲测。 |
| RAG / Chroma | PASS（离线测试及现存 Chroma SQLite 完整性）；无外部联网含义。向量索引文件不应提交。 |
| UserState / CRM | PASS（本地单测）；API 组合已迁移到 `UserStateService.from_path`，不再直接 import/构造 Repository。身份仍是未认证本地分区键。 |
| MCP Host / OCR | PASS（隔离 HTTP/stdio）：B6 确认前 0 行，确认后 3 行读回，跨用户拒绝。MCP Inspector GUI NOT VERIFIED。 |
| Suggestions | PASS：只读、默认关闭、最多 3 条、HTTP/UI 集成历史证据；无写入。 |
| FastAPI / Streamlit | PASS（本机 Smoke 和 pytest/AppTest）；不代表公网部署/身份系统完成。 |
| SQLite / Chroma | PASS：本机 `stage2.db`、`mcp_host_state.sqlite3`、`chroma/chroma.sqlite3` 以只读 URI 执行 `PRAGMA quick_check`，均返回 `ok`。未在真实用户 DB 上执行迁移或写操作。 |

## 本轮测试证据

| 命令 | 结果 |
|---|---|
| `.\scripts\run_tests.ps1` | exit 0；245 passed、1 skipped、0 failed；2 个依赖弃用警告。唯一 skip：Windows 账户不能创建 symlink。 |
| `.\.venv\Scripts\python.exe -m pytest tests\integration\test_api_smoke.py -q` | exit 0；1 passed。 |
| `.\.venv\Scripts\python.exe scripts\m08_b_http_acceptance.py` | exit 0；真实 loopback Uvicorn，澄清、重启确认、重复确认、跨用户拒绝、普通 Chat 均通过，改名读回正确。 |
| `.\.venv\Scripts\python.exe scripts\m08_c_http_acceptance.py` | exit 0；真实 loopback Uvicorn，双步骤 `rename_session → list_sessions`，重启/重复确认/Query 读回通过。 |
| `.\.venv\Scripts\python.exe scripts\m09_http_acceptance.py` | exit 0；真实 loopback，建议 3 条、消息历史持久、跨用户 404、旧响应兼容。使用本地 FakeLLM。 |
| `.\.venv\Scripts\python.exe scripts\mcp_b6_http_acceptance.py` | exit 0；真实 Uvicorn 与本机 MCP 子进程，OCR upload/confirm、跨用户拒绝、数据库读回、graceful shutdown 通过。 |

修复后最终全量结果为 245 passed、1 skipped、0 failed。文档章节曾短暂造成版本中心契约测试失败；将 CHANGELOG 的最新章节恢复为 Maintenance 摘要后，全量复测通过。

## 安全修复与边界

- API 上传现在先 Query 检查会话 owner，仅接受 TXT/MD/PDF/DOCX，应用读取上限 20 MiB，并在验证前不落盘。回归覆盖非 owner、非法扩展名、超限均没有新增暂存文件。
- UserState 服务新增 `from_path` 工厂，API 组合根不再接触 Repository 构造。
- 传输层仍须设置 request body 上限，因为 multipart 可能在路由读取前被 Starlette spool；公网身份认证、授权和可信隔离未实现，当前 `X-User-ID` 不可作为生产安全边界。
- 没有数据库 schema 迁移，因此不需要用户数据库迁移/回滚；只在 pytest 临时目录测试持久化。SQLite 备份建议使用 SQLite backup API 或停机复制 DB 与 WAL/SHM，并在恢复副本上 quick_check；本轮没有覆盖生产备份介质的恢复演练。

## 状态矩阵

| 关卡 | 结论 | 说明 |
|---|---|---|
| M10-A 本地回归与模块集成 | PASS（本机） | 全量、Smoke、M08-B/C、M09、MCP B6 均复测。 |
| M10-B Router 150 独立验收 | NOT VERIFIED | 150 条人工标注全部 unreviewed，未冻结；禁止推算准确率。 |
| M10-B DeepSeek / Tavily 实测 | NOT VERIFIED | 密钥存在但本轮未授权外呼/计费；本地 Fake/Mock 不作真实证据。 |
| M10-B MCP Inspector GUI | NOT VERIFIED | 自动化协议/HTTP 已测；需人工 GUI 截图和工具 schema 核对。 |
| M10-C 公网身份与部署安全 | BLOCKED | 缺可信认证、授权策略和公网部署/运维证据。 |
| M10-D v1.0 发布范围 | BLOCKED | 见 `RELEASE_BLOCKERS.md`；版本保持 `0.1.1.dev0`。 |

## 人工证据清单

截图只采真实运行：`artifacts/m10/full-test-run.png`、`router-dev-300.png`、`router-independent-150.png`（冻结后）、`chat-multiturn.png`、`m08-confirmed-write.png`、`m09-suggestion-prefill.png`、`api-streamlit-running.png`、`mcp-inspector-tools.png`、`deepseek-tavily-live.png`（真实调用后）、`github-release.png`（授权发布后）。不得用报告表格/Mock 输出代替截图。

MCP Inspector 手动步骤：启动相应 stdio server（Database/OCR 入口见 `docs/database_mcp.md`），用 MCP Inspector 指向当前 Python 与 server module/脚本；截图显示 tools/schema；对 OCR 先 preview 验证数据库仍为 0 行，再执行明确确认并调用只读 Query 检查写入和隔离。GUI 运行前使用专用临时数据库，不连接 `data/` 真实用户库。


## 最终复测补充

- 定向：.\.venv\Scripts\python.exe -m pytest tests\unit\test_user_state.py tests\integration\test_api_smoke.py -q：39 passed；包含上传 owner/扩展名/大小拒绝和无落盘断言。
- .\.venv\Scripts\python.exe -m compileall -q app ui scripts tests：exit 0。
- git diff --check 与 git diff --cached --check：均 exit 0；只有 Git 的 LF/CRLF 提示，无空白错误。
- 临时 SQLite backup API 演练：恢复副本 PRAGMA quick_check=ok，示例数据 1 行读回。
- 修复后再次复测四项 loopback acceptance，命令和详细响应摘要见报告结尾。

## M10-B Router 与功能范围

- 已存档的 `evals/v011_hybrid_300_final.json` 显示开发集 300/300、Accuracy 1.0、Macro F1 1.0、mixed_sources 1.0；这是工程开发/调试证据，数据与规则可能存在开发耦合，本轮没有重跑会覆盖报告的脚本，也没有把它当独立验收。
- 独立工作表 `evals/v011_human_annotation_worksheet.csv`：150 行，150 行 `review_status=unreviewed`，0 行具备任一 annotator/adjudicated 标签。独立 Accuracy、Macro F1、分类 Precision/Recall、混淆矩阵全部 NOT VERIFIED。人工指南要求分歧裁决及冻结 SHA-256；相似样本中 8 项 token overlap 仍需人工复核。
- INCLUDED（本地预发布）：离线 Chat、文件解析与本地 RAG、Rules Router、M07 会话/历史、多用户逻辑分区、M09 可选建议、已测试的本机 MCP 确认流程。
- EXPERIMENTAL：M08 本地 loopback 的 `rename_session` 和 `rename_session → list_sessions`；DeepSeek/Tavily 若配置也仍需实时验收。
- DEFERRED：通用多意图规划、CRM 写入型任务、任意 MCP 调度、持久化对话摘要、生产级用户/会话删除补偿。
- BLOCKED：公开服务身份、已冻结 Router 盲测指标、外部 Provider 实测、Inspector GUI、生产部署与恢复演练。未满足这些发布门槛前不得将当前工程描述为可公网正式服务。

## 最终复测摘要

| 证据 | 本轮最终结果 |
|---|---|
| 全量自动回归 | `scripts/run_tests.ps1` exit 0；245 passed、1 skipped、0 failed。 |
| API Smoke | 独立命令 exit 0；1 passed、0 failed。 |
| M08-B HTTP | exit 0；普通 Chat、澄清、重启确认、重复确认、跨用户 404、unsupported write 拒绝。 |
| M08-C HTTP | exit 0；重启确认，`rename_session` 和 `list_sessions` 两步 SUCCEEDED，查询读回标题。 |
| M09 HTTP | exit 0；本地 FakeLLM，建议 3 条、历史持久、跨用户拒绝、兼容旧响应。 |
| MCP B6 HTTP | exit 0；OCR 上传，确认前 0 行，确认后 3 行，数据库读回验证、跨用户 404、正常关闭。 |
| compileall / Git 差异 | compileall exit 0；`git diff --check`、`git diff --cached --check` 均 exit 0。Git 显示 LF/CRLF 警告，不是 whitespace error。 |
| 数据库备份临时演练 | Python SQLite backup API 临时副本 `quick_check=ok`，1 行数据恢复读回。不是生产备份介质验收。 |

测试警告为 Chroma 对 `asyncio.iscoroutinefunction` 的弃用警告与 Starlette TestClient/httpx 弃用警告；唯一 skip 是 Windows symlink 权限条件。

真实截图尚未生成。本报告只列出可复现人工截图名，不冒充屏幕证据。MCP Inspector、DeepSeek、Tavily 与生产部署等待各自具备前提和独立证据。

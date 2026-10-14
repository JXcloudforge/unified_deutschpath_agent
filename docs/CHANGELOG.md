# Changelog

This file records repository evidence and current working-tree state. A line
does not imply a Git commit or release tag unless one is listed explicitly.

## Maintenance — M10-Auth-C Streamlit OIDC UI / API 接入 — 2026-10-13（预发布）

- production Streamlit 增加原生 OIDC 登录门禁；缺少 OIDC secrets、Authlib、HTTPS redirect 或 API audience 时在受保护工作区前 fail closed。真实 IdP 尚未配置，登录未验收。
- `Stage2ApiClient` 增加 server-side Bearer 支持；认证请求不发送 `X-User-ID`。API 401 让本 Client 失效并触发重认证状态，不自动重试。development 继续保留原 loopback User ID 路径。
- 增加 `.streamlit/secrets.toml.example`（Auth0 仅为可替换样例）和 UI auth helper/测试；真实 secrets 不入库。UI 用 `iss+sub` 哈希隔离 session state，不能用于授权。
- `streamlit[auth]>=1.55,<2.0` 已加入项目依赖声明。离线 Fake OIDC/JWKS 与 AppTest 只能验证软件边界；真实 provider、Cookie/CSRF 会话、logout/revocation 和公网 HTTPS 仍 NOT VERIFIED。版本保持 `0.1.1.dev0`。

## Maintenance — M10 第一轮系统验收 — 2026-10-13（仍为预发布）

- 复核全量离线回归为 245 passed、1 skipped、0 failed；独立 API Smoke 1 passed；M08-B、M08-C、M09、MCP B6 隔离 HTTP 验收退出码均为 0。最终修复后复测已经通过。
- API UserState 组合改用 `UserStateService.from_path`，避免组合层直接构造 Repository。
- 附件先验证 Conversation owner，只接受 TXT/MD/PDF/DOCX，限制读取 20 MiB；拒绝类型、大小与 owner 的集成测试增加。传输层 body limit 和上传临时文件异常清理仍需部署/架构补足。
- 本地 SQLite/Chroma 的只读 `PRAGMA quick_check` 均为 `ok`。没有对用户数据执行迁移或写入。
- Router 150 题仍全部未标注，真实 DeepSeek/Tavily 未调用，MCP Inspector GUI 未验收，可信生产身份与公网部署未验收；均不得视为 PASS。
- 版本保持 `0.1.1.dev0`；无 commit、tag 或 push。

## Maintenance — M10-P0 仓库/身份/Router 阻塞项准备 — 2026-10-13

- Git 审计确认 HEAD 仍是 CRM 工程提交，remote 仍指向 `CRM-agent.git`；归属和 98 条旧目录 unstaged 删除意图未验证，未改 Remote。
- 新增身份传播审计、A 本地单用户/B OIDC 多用户方案比较和 Proposed ADR；没有实施身份迁移。隔离实测伪造 `X-User-ID` 可读取测试数据 HTTP 200，生产认证仍为 P0 FAIL。
- 新增 Router 双份人工标注、合并/分歧裁决、SHA-256 冻结与冻结后评估 CLI；原 150 题仍为 0/150 人工标注，未生成冻结物。
- 本轮全量：254 passed、1 skipped、0 failed；Router 工具单测 9 passed；API Smoke 1 passed；M08-B/C、M09、MCP B6 HTTP 验收退出码 0；生产 mutation 负向测试 1 passed；compileall 和 diff-check exit 0。
- 版本仍为 `0.1.1.dev0`；无数据库改动、远程操作或外部 Provider 调用。

## v0.1.1.dev0 — development candidate — 2026-10-13

### M08-A 编排基础与 M08-B 最小真实业务闭环

- 新增多轮编排 DTO、Command / Query、独立 SQLite 状态存储、提案确认键及状态转换。
- M08-A 提供独立编排状态、确认提案与状态转换。M08-B 将限定的 `rename_session` 动作接入现有 Chat API：缺参澄清、修订、确认后调用 Conversation Command，并通过 Query 读回核验。
- 本地集成默认关闭；development 只接受直连 loopback；production 写操作 fail-closed。两份 SQLite 无共同事务，未知结果仅查询核对、不自动重放，不能保证 exactly-once。
- 不支持 CRM/学习任务创建、通用 Tool Registry、复杂多意图规划或可信生产身份；M08-B 不代表完整 M08 封板。证据见 `docs/PHASE4_M08_ACCEPTANCE.md`。
- **本轮验证：** M08 聚焦 16 passed；全量 `scripts/run_tests.ps1` 为 222 passed、1 skipped、0 failed；独立 API Smoke 1 passed；真实 M08 loopback HTTP 重启闭环与既有 MCP HTTP Smoke 均退出码 0；compileall 和 `git diff --check` 通过。唯一 skip 是 Windows symlink 权限限制。版本仍为 `0.1.1.dev0`。
- 版本保持 `0.1.1.dev0`。

### M08-C — 有界多步骤编排

- 在 M08 自有 SQLite 增加步骤记录；支持最多四步的结构契约，但目前仅注册并解析 rename_session → list_sessions 双步骤能力。
- 整体计划确认后串行调用真实 Conversation rename_session Command 和 list_sessions Query；Query 依赖 Command 成功及标题读回验证。单步和双步骤都保留独立执行结果。
- Command 失败阻断依赖步骤；后续 Query 失败保留前一步成功并记录 PARTIAL。并发确认只允许一份执行，重启恢复从 UNCERTAIN 状态查询核对，不盲目重放写入。
- M08 仍默认关闭且受 development loopback gate 保护；生产写操作仍 fail-closed。版本继续为 0.1.1.dev0。
- M08-C 验收细节和真实 HTTP 证据见 docs/PHASE4_M08C_ACCEPTANCE.md。
- **M08-C 最终验证：** `tests/unit/test_orchestration_service.py` 与 `tests/integration/test_m08_chat_integration.py`：23 passed；全量 `scripts/run_tests.ps1`：229 passed、1 skipped、0 failed；API Smoke：1 passed；M08-B、M08-C 与 MCP B6 本地 HTTP 验收脚本均退出码 0；compileall 与 `git diff --check` 退出码 0。跳过项为 Windows symlink 权限限制。真实外部 Provider 和生产认证仍未验证。

### M09 — 后续问题推荐

- 新增 `app.suggestions` 只读 Query 和不可变 `FollowUpSuggestion` DTO；复用 Conversation 的有界上下文 Query，并只读检查 M08 活动状态。
- 当前确定性离线策略覆盖 Ausbildung、语言等级、语法、词汇；最多返回三条，无可靠主题则为空；不调用 LLM、联网、CRM 或 MCP，不写业务状态。
- Chat 请求通过 `include_suggestions` 显式选择，默认 false；推荐错误不会影响答案。Streamlit 默认关闭，点击只预填问题，不会自动发送。
- **验证：** M09 单元/HTTP/UI 契约 28 passed；真实 M09 loopback Uvicorn E2E 退出码 0；全量 245 passed、1 skipped、0 failed；API Smoke 1 passed；M08-B、M08-C、MCP B6 loopback 验收、compileall、diff-check 均通过。跳过是 Windows symlink 限制。证据见 `docs/PHASE4_M09_ACCEPTANCE.md`。版本仍为 `0.1.1.dev0`。

### B7 — v0.1 内测第七次工程更新 — 2026-10-13

- **文档：** 将根 README 改为基于当前代码和入口的中文说明，补充 M01–M06 迭代索引、B7 状态、调用链、数据边界、安装/启动/测试命令与 v1.0 门槛。
- **版本中心：** 在本版本记录和本节记录 B7；Streamlit 继续从现有 `pyproject.toml`、迭代 manifest、CHANGELOG、功能状态和发布说明读取数据。B7 不新增 SemVer 版本号。
- **安全：** 复查 `.gitignore` 与 `.env.example`；模板只包含空密钥占位。本地 `.env`、运行数据库和默认数据目录被忽略。
- **验证：** B7 真实回归结果写入 `docs/history/b7-freeze-20261013.md`；不得用既往数字替代本次记录。
- **阶段三未决：** Router 独立人工集、真实 DeepSeek/Tavily 联通、MCP Inspector 与生产身份验证仍需各自独立证据；未据此宣称正式发布。
- **Git：** 未创建提交、Tag 或 Release，未修改远程、未 Push；当前 `origin` 仍指向历史 CRM-agent 仓库。

### 阶段四 M07 — Conversation Commands / Queries — 2026-10-13

- **接口：** 新增显式未认证本地 `ActorContext`、Conversation Commands/Queries Protocol 与不可变 Session、Message、ContextSnapshot、SendResult DTO；Repository 留在 Chat 模块内部。
- **边界：** FastAPI 会话、历史、OCR 所属权和助手结果持久化改走 ChatService。ChatWorkspace 继续通过既有 API Client 和 HTTP JSON 契约工作，路径和主要字段保持兼容。
- **上下文：** 通过 Conversation Query 读取历史，再使用纯 Context Builder 限制最近 20 条和 12,000 字符；不改 schema。字符限制不是精确 token 预算，摘要持久化未实现。
- **验证：** 当前全量回归 **206 passed, 1 skipped**；真实 Uvicorn/stdio MCP HTTP E2E 确认前 0 行、确认后验证 3 行、跨用户确认 404、优雅关闭。
- **限制：** ActorContext 仍以本机 `X-User-ID` 为 namespace，未认证；会话归档、摘要存储、M08 任务状态机和正式阶段四验收仍未完成。版本继续为 `0.1.1.dev0`。

### Final engineering freeze supplement — 2026-10-13

- **Documentation:** added retrospective M01–M06 technical records and a
  controlled `docs/iterations/manifest.json`; the README now contains the
  evolution index and State → Reasoning → Action diagram.
- **UI:** the system-information panel reads release history and six
  expandable milestones from repository-controlled manifest data. It shows
  concise feature/technology/chain/problem/status fields, not source files.
  Version remains sourced from `pyproject.toml` through `app/version.py`.
- **Verification:** current non-TestClient suite **200 passed, 1 skipped**;
  `compileall` passed. Isolated real-Uvicorn HTTP covered health, sessions,
  chat, RAG, offline Web fallback, CRM, and attachments. OCR → explicit review
  and confirmation → Database MCP write → query verification passed with three
  rows. Existing FastAPI OpenAPI and Streamlit health passed; launcher
  identity/preflight passed without stopping existing services.
- **External providers:** DeepSeek and Tavily were configured in the existing
  backend, but no external request was made in this freeze run; live status is
  **NOT TESTED** here. Historical P0 results remain historical evidence.
- **Git:** no commit, push, tag, index, or remote change. Target GitHub
  repository was checked read-only and appeared empty at this review; `origin`
  still points to the legacy CRM-agent repository. See
  `docs/releases/GITHUB_PUBLISH_CHECKLIST.md` before publication.

- **Maintenance:** removed verified generated pytest/acceptance directories from
  the main project and old 04 test runs, plus the archived 03/04 virtual
  environments. Workspace file usage fell from about 2.60 GiB to about 0.55 GiB
  (net reduction about 2.05 GiB). Formal data, root `.env`, and current `.venv`
  were kept. Unique historical credentials, databases, uploads, and nested Git
  metadata were preserved in the existing external backup root before removal
  of eligible work copies. This cleanup removed 02 fully; ACL-protected 01 and
  04 residuals and the 03 work copy remain.
- **Added:** `scripts/run_tests.ps1` runs the non-TestClient suite with pytest
  cache disabled and an isolated GUID directory under the system temp folder.
  It removes only its own run directory; `-KeepFailedArtifacts` explicitly
  preserves that directory on failure.
- **Tests:** 197 passed, 1 skipped in 83.82 seconds; `compileall` passed.
  A fresh isolated real-Uvicorn HTTP run passed health, session/chat, CRM,
  attachment, RAG, and controlled offline Web behavior. OCR → approval →
  Database MCP E2E passed with three verified rows and graceful shutdown. The
  live Streamlit health endpoint returned 200. Pytest left no owned temp run.
- **Known limits:** stale listeners on 8765/8501 were gracefully stopped after
  confirming their project process paths; 8000 was not touched. The isolated
  `.p1-2-browser-acceptance` databases were empty, its logs were retained in
  `docs/history/`, and its data directory was removed. The 03 legacy work copy
  remains because 21 generated test directories are inaccessible under their
  current Windows ACLs. The ZIP was absent from the main root; the existing
  `../Deutschpath_agent_archive/legacy/03_deutsch_chat.zip` remains unchanged.
- **Git:** no commit or tag was created; existing staged/unstaged state and
  the legacy `agent` gitlink state were left untouched.

- **Added:** session title search and persistent rename in the local Streamlit
  interface; the FastAPI route scopes updates to the supplied local user ID.
- **Changed:** the application version now comes from `pyproject.toml` and is
  shown by FastAPI and Streamlit as `v0.1.1.dev0`.
- **Changed:** the local editable package metadata now matches `pyproject.toml`;
  refreshed with `pip install -e . --no-deps --no-build-isolation` and no
  dependency changes.
- **Changed:** one recommended `start.bat` coordinates the existing backend and
  frontend launch scripts and checks project ownership, health, and ports.
- **Maintained:** generated a source-focused external archive copy of all four
  historical project directories; every copied file was rechecked by SHA256.
- **Tests:** 197 passed, 1 skipped in the final non-TestClient suite; the skip
  is Windows symlink creation unavailable in the active account. `compileall`
  passed. Isolated real Uvicorn/HTTP, Streamlit health, launcher identity, and
  OCR→confirmation→Database MCP acceptance passed.
- **Known limits:** archive/restore UI awaits an additive database migration;
  live browser interaction and external provider connectivity are separate
  acceptance items. Formal independent 98% Router acceptance is not verified.
- **Git:** no commit or tag was created. Existing staged/unstaged work remains;
  the Windows TestClient smoke remains excluded and is not counted as passed.

- **Added:** release records for `v0.1.0-beta.1` and `v0.1.1.dev0`. The
  Streamlit settings sidebar now displays version and release notes from a
  fixed document allowlist; the version remains sourced from `pyproject.toml`.
- **Fixed:** `start.bat` readiness checks now inspect the server process under
  its PowerShell service window. The previous check inspected only the
  PowerShell wrapper and falsely timed out after successfully starting FastAPI.
- **Tests:** this final cleanup run passed 199 tests with 1 Windows symlink
  skip; compileall, real-Uvicorn HTTP/CRM, isolated OCR→approval→Database MCP
  E2E, and `start.bat` current-version checks passed. The full test run used and
  removed its own system-temp data directory.
- **Evidence:** cleanup sizes, protected-data checks, ACL-limited historical
  leftovers, and startup acceptance are recorded in
  `docs/history/final-cleanup-20261013.md`.

## v0.1.0-beta — B0–B7 integration record

The repository retains the historical B0–B7 evidence in
`docs/v0.1_beta_acceptance.md`, `docs/v0.1_migration_manifest.md`, and the
stage-specific audit documents. That record describes the beta integration of
the Agent, CRM/User State, chat API and UI, Stage 2 RAG, Stage 3 routing and
web evidence, Database MCP, OCR MCP, and the MCP Host workflow. Historical
reports are preserved as written; their test totals are not substituted for
the current maintenance run.

## v0.1.1 — earlier worktree changes

Earlier v0.1.1 P0/P1-1/P1-2 changes exist in the current working tree and
historical evaluation files. The P1-2 archive-field migration proposal is in
`docs/p1_2_archive_migration.md`. No formal release tag was found or created.

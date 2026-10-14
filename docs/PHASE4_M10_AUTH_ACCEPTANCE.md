# M10 Auth / 多用户安全验收记录

日期：2026-10-13。版本保持 `0.1.1.dev0`。本文件最初记录 Auth-C UI 接入前的 Auth/API 安全基线。Streamlit 登录接线的后续现状以 [`PHASE4_M10_AUTH_UI_ACCEPTANCE.md`](PHASE4_M10_AUTH_UI_ACCEPTANCE.md) 为准；本文件仍是 Auth API/Fake JWKS 的证据，不表示真实 OIDC 或公网验收通过。

## 验收矩阵

| 项目 | 状态 | 证据 / 缺口 |
|---|---|---|
| 无 Token 与伪造 `X-User-ID` 访问私有 HTTP | PASS（TestClient） | 均返回 401；生产模式验证 |
| 签名、issuer、audience、expiry、Access Token 标记校验 | PASS（Fake RSA/JWKS resolver） | 本地生成密钥；不代表外部 IdP |
| issuer+subject 持久映射、同 subject 跨 issuer 隔离、禁用账号 | PASS（临时 SQLite） | 重开 repository 后映射稳定 |
| 不同用户会话隔离、资源不存在性保护 | PASS（本地 HTTP） | B 用户读 A 消息返回 404 |
| Query 与 Command 归属授权 | PASS（现有 Conversation 服务契约 + HTTP） | UserState 按 Actor user_id 分区；Conversation Query/Command owner scoped |
| Streamlit OIDC 登录与 Access Token 到 API | NOT VERIFIED（代码接线已实现） | Auth-C 已增加原生 OIDC gate、server-side Access Token 取用和 Bearer API Client；真实 IdP/audience、浏览器登录与双用户公网链路仍待测，见 Auth UI 报告 |
| MCP 公网绕过认证 | PASS（暴露面审计） | 当前 MCP 为 FastAPI 内部调用/stdio 子进程，无公网 MCP HTTP endpoint；VPS 仍需网络隔离 |
| M08 跨轮认证与公网授权 | NOT VERIFIED | 当前编排适配器仅在 development+loopback 启用；生产 M08 需独立复验 |
| 真实 OIDC 登录、HTTPS 与账户停用联通 | NOT VERIFIED | 尚无 IdP 配置或公网上线环境 |
| Docker/SQLite 并发、持久卷、灾备恢复演练 | NOT VERIFIED | 草案尚未在 Linux VPS 验证 |

## 本轮离线复测记录

环境：Windows 11 PowerShell，项目 `.venv` Python 3.14.6、FastAPI 0.141.1、Streamlit 1.65.0、PyJWT 2.15.1；无真实 OIDC 凭据或外呼。

- `.\scripts\run_tests.ps1`：最终全量离线回归 **260 passed, 1 skipped, 0 failed**，2 warnings。skip 是 Windows 当前账户无法创建 symlink；warnings 为 Chroma 和 Starlette/httpx 弃用提示。
- `.\.venv\Scripts\python.exe -m pytest tests\unit\test_auth.py tests\integration\test_auth_http.py -q -p no:cacheprovider`：**6 passed, 0 failed**（RSA verifier、issuer/audience/expiry/签名、映射隔离、生产 HTTP 隔离、所有路由依赖静态检查、无配置 fail-closed）。
- `.\.venv\Scripts\python.exe -m pytest tests\integration\test_api_smoke.py -q -p no:cacheprovider`：**1 passed**。
- `.\.venv\Scripts\python.exe -m compileall -q app ui scripts tests`：退出码 0。
- `git diff --check` 与 `git diff --cached --check`：均退出码 0；Git 输出仅有工作树已有的 LF/CRLF 提示。
- `docker compose -f deploy/compose.yaml config`：未设置变量时按预期拒绝；以非敏感占位域名/issuer/audience/JWKS 环境变量再次解析成功。没有构建或启动容器。
- `.\.venv\Scripts\python.exe scripts\m08_b_http_acceptance.py`：loopback Uvicorn 闭环成功，跨用户 404、重启后确认、重复确认均符合预期。
- `.\.venv\Scripts\python.exe scripts\m08_c_http_acceptance.py`：重启后两步 `rename_session` / `list_sessions` 均 SUCCEEDED，读回标题正确。
- `.\.venv\Scripts\python.exe scripts\m09_http_acceptance.py`：真实 loopback HTTP 返回 3 条 opt-in 建议；跨用户 404，旧响应兼容。
- `.\.venv\Scripts\python.exe scripts\mcp_b6_http_acceptance.py`：loopback HTTP 上传/OCR/确认通过，3 行写入并读取验证，跨用户 404，Uvicorn 正常退出。

完整回归含 Chroma `asyncio.iscoroutinefunction` 与 Starlette TestClient/httpx deprecation warnings；Windows symlink 权限导致 `tests/unit/test_ocr_mcp.py:104` 的 1 项既有 skip。

## 公共身份契约

FastAPI 通过 `get_actor_context` 解析 `Authorization: Bearer`，由 Auth 验证后生成不可变 ActorContext。只有本地 development 且直连 loopback 的请求可使用 `X-User-ID` 测试分区；production 无 header fallback。每个目标业务模块仍以 Actor user_id 做资源所有权检查。`/health` 是明确公开端点。

## 入口安全审计矩阵

| 入口/资源 | 当前身份入口 | 服务端资源边界 | 本轮结论 |
|---|---|---|---|
| FastAPI `/users/me/state`, `/users/me/events` | `get_actor_context`；旧 X header 仅 dev loopback | UserState Service 只接收已解析 Actor 的内部 user_id | HTTP Actor 已统一；旧本地 UI 不可用于公网 |
| `/sessions`, `/sessions/{id}`, `/messages` | `get_actor_context` | Conversation Command/Query 按 Actor 检查 owner；foreign session 为 404 | 本地 token HTTP 隔离通过 |
| `/attachments`, `/ocr/*` | `get_actor_context` | 先查 Conversation session owner；MCP Host 再绑定 owner+session | API 前置授权存在；OCR 多用户真实 IdP 链路未验证 |
| RAG 私人检索 | 无独立公网检索路由；Chat 经所属 session 操作 | Conversation 先验证 owner，Agent/RAG 按 session namespace 查 | API 路径已复用 owner；无外部穿透测试 |
| M08 orchestration | HTTP 集成仅 development+loopback 启用 | M08 Query/Command 使用 actor.user_id 过滤状态 | 公网 M08 未启用，跨轮 OIDC 未验证 |
| M09 suggestions | Chat response 的可选 Query | actor/session 的 Conversation Snapshot 与 M08 状态 | 复用 Actor；跨账户 OIDC 覆盖待补 |
| MCP | FastAPI 内 OCR Host 调用；stdio MCP Server | API 校验 Actor/session，Host 校验 owner/session/operation | 未发现公网 MCP HTTP endpoint；部署须禁止旁路暴露 |
| Streamlit | 实际 venv Streamlit **1.65.0**；Auth-C production gate 使用 OIDC → server-side Access Token → Bearer | API production 独立拒绝 header-only 并验 Bearer；development 保留本机 User ID | **公网仍阻塞**：接线已实现、真实 IdP 和 audience 未配置，真实登录/双账户/CSRF 与 logout 边界未验证。见 [官方认证指南](https://docs.streamlit.io/develop/concepts/connections/authentication) 和 [st.user token 文档](https://docs.streamlit.io/develop/api-reference/user/st.user)。|

身份传播为 `Streamlit -> FastAPI get_actor_context -> Auth token verifier -> Auth identity mapping -> ActorContext -> 所属业务 Command/Query -> owner-scoped store`。内部 MCP 子进程不获得浏览器原始凭据；当前没有网络 MCP 身份入口。

## 仍需真实验收

1. 创建托管 OIDC 应用，固定 issuer、Deutschpath API audience/scope、回调 URL 和账号生命周期责任人。
2. 在隔离环境验收已接入的 Streamlit 原生 OIDC 与 Bearer 发送；不把 ID Token 当 API Access Token。确认有效期、logout、CSRF、CORS 与服务端 token 保管策略；项目实现与离线证据见 Auth UI 报告。
3. 在测试 IdP 建立两个账户，验证 Conversation、UserState、附件、M08 和私人 RAG 跨用户隔离；验证账号禁用及密钥轮换。
4. 在隔离 VPS 完成 Caddy TLS、Compose 内网、SQLite 并发和完整 `/data` 恢复演练。
5. 完成限流、请求体限制、AI 成本预算、日志脱敏、监控与安全复核。

旧本地 user_id 不自动绑定新 IdP。正式认证仍为发布阻塞项，不能由 Fake Token 测试解除。

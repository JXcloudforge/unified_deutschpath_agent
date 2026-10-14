# M10-Auth-C Streamlit OIDC UI / API 接入验收

日期：2026-10-13。版本仍为 `0.1.1.dev0`。本报告区分离线契约证据与真实身份服务验收。

## 实现范围与调用链

production UI 调用链：

```text
Browser → Streamlit st.login(provider) → server-side st.user.tokens.access
       → Stage2ApiClient Authorization: Bearer → FastAPI get_actor_context
       → Auth 验签/issuer/audience/expiry 校验和 issuer+subject 映射
       → 业务模块按 ActorContext 检查资源归属
```

生产入口在渲染私人工作区前检查 `streamlit[auth]` runtime、`[auth]` 配置、HTTPS redirect、OIDC provider、API audience、登录态和 Access Token；任一缺失则停止。登录后用户 ID 输入控件不呈现，Client 不发 `X-User-ID`。OIDC `iss+sub` 哈希只用于清理/分区 Streamlit session state，不参与 API 请求或授权。

Client 收到 Bearer 401 时丢弃本实例 token、标记会话需重新认证、回调 UI 并抛出 `ApiReauthenticationRequired`；同一 Client 后续请求不会再发送。无自动重试，避免不确定写请求被重放。development 分支保留 loopback User ID/X-User-ID 兼容，但 FastAPI production 仍拒绝 header-only 身份。

## 配置

`.streamlit/secrets.toml.example` 是无密钥 Auth0 示例，provider section 可替换。部署需填入真实 client ID/secret、OIDC metadata URL、面向 API 的 audience、HTTPS `redirect_uri` 和至少 32 字符的随机 cookie secret，并将 `expose_tokens="access"`。实际 `.streamlit/secrets.toml` 被 Git 忽略。项目依赖声明为 `streamlit[auth]>=1.55,<2.0`。

`st.logout()` 清理 Streamlit 登录 cookie 和应用 session 状态；Streamlit 文档说明它不会自动清除 IdP 登录状态。项目不承诺 token 撤销，待真实 IdP 的 logout/revocation 方案确认。

## 测试证据

| 范围 | 证据 | 状态 |
|---|---|---|
| Auth helper / 配置 fail-closed | `tests/unit/test_ui_authentication.py`：配置约束、占位符、token 读取、缓存 scope、production AppTest 门禁 | PASS |
| API Client 契约 | `tests/unit/test_ui_contracts.py`：Bearer 无 X-User-ID、development 兼容、401 后失效且不重试 | PASS |
| Auth verifier / HTTP | `tests/unit/test_auth.py`、`tests/integration/test_auth_http.py` Fake RSA/JWKS 与本机 HTTP | PASS（Fake/本机证据） |
| 真实 OIDC 登录及 token exchange | 未提供 IdP 配置、client secret 或实际 audience | NOT VERIFIED |
| 双真实账户公网隔离、浏览器 Cookie/CSRF、撤销、Tailscale/HTTPS | 无部署环境和真实账户 | NOT VERIFIED |
| DeepSeek/Tavily | 本轮未调用 | NOT RUN |

Auth/UI focused command：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\unit\test_ui_contracts.py tests\unit\test_ui_authentication.py tests\unit\test_auth.py tests\integration\test_auth_http.py -q
```

当前记录：30 passed、0 failed，进程退出码 0。测试只使用离线数据与 Fake OIDC/JWKS。

在项目 venv 安装声明所需的 Authlib 后（`Authlib 1.8.0`，Streamlit `1.65.0`），最终全量 `scripts/run_tests.ps1` 结果为 **269 passed、1 skipped、0 failed**，退出码 0。API Smoke 为 **1 passed**；另在 Auth HTTP 先导入 FastAPI 应用的测试顺序下组合运行，通过修复测试临时 `ROOT` 隔离验证，不再受模块缓存顺序影响。`compileall`、`git diff --check`、`git diff --cached --check` 均退出码 0。M08-B、M08-C、M09、MCP B6 loopback HTTP 验收脚本均退出码 0；其证据只表明既有本机业务闭环仍工作，不是外部 IdP 验收。

既有链路输出摘要：M08-B 普通对话/缺参/重启确认/重复确认均 200、跨用户 404、未支持写入被拒；M08-C 的 `rename_session` 与 `list_sessions` 两步均 `SUCCEEDED` 且重启可恢复；M09 opt-in 返回 3 条建议且跨用户 404；MCP B6 上传/OCR/确认与读回均 200，跨用户 404，确认后数据库 `verified`。独立 API Smoke 为 1 passed。Authlib 安装后，UI auth focused tests 为 24 passed；完整 Auth/API focused 组最终为 30 passed。

## 剩余阻塞与回滚

- 当前 venv 已安装 Authlib 1.8.0，`pyproject.toml` 声明 `streamlit[auth]>=1.55,<2.0`；目标部署镜像仍需按锁定依赖安装并核验。未配置 IdP 时没有触发真实登录。
- 必须由 IdP 管理员创建 OIDC 应用并提供 issuer、API audience/scope、metadata URL、client secret、允许的 callback/logout URL；随后验证真实 Access Token 的 audience 与 API JWKS 设置一致。
- 需要设计浏览器写请求的 Origin/CSRF 防护以及 IdP logout/revocation 行为。Bearer 由 Streamlit server-side 发出降低浏览器暴露面，但不能替代部署层 CSRF/Origin 验收。
- 需在隔离环境验收双账户资源隔离，覆盖 Conversation、UserState、附件、M08/M09 和 MCP/OCR；之后才进行公网 HTTPS 和真实账户验收。
- 回滚可以恢复 `ui/streamlit_app.py`、`ui/api_client.py`、`ui/authentication.py`、依赖声明和新增配置模板/测试文档；API 契约仍兼容 development 的原 `user_id` 参数。未修改业务数据或数据库。

**结论：Auth-C 离线实现与 fail-closed UI 接入 PASS；真实 OIDC 和公网登录闭环 NOT VERIFIED。不可据此宣布 v1.0 认证验收通过或开放公网。**

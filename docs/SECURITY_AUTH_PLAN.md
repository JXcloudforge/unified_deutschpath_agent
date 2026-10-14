# 可信认证实施方案

状态：v1.0 公网多用户 OIDC 目标已确认；Auth Access Token 验证及 issuer/subject 映射已实现并由离线测试覆盖。Auth-C 已把 Streamlit 原生 OIDC 登录 gate 和 Access Token → Bearer API Client 接入 production UI；真实 IdP 登录、双真实用户、浏览器 CSRF/session 与部署验收仍未完成，当前仍禁止公网服务。代码/测试状态见 [`PHASE4_M10_AUTH_UI_ACCEPTANCE.md`](PHASE4_M10_AUTH_UI_ACCEPTANCE.md)。

## 已确定与待配置事项

产品形态：公网 HTTPS 多用户正式版。尚需选择并配置 OIDC provider、API audience/scope、域名、账户运维责任人、生产部署环境及 secret store。当前仅默认 `member` 角色；租户能力未设计。

## 方案比较

| 项目 | A. 单用户本地正式版 | B. 公网/组织多用户版 |
|---|---|---|
| 信任边界 | 同一台受控 Windows 主机、同一 OS 登录用户；API 与 UI 仅 loopback，不承诺同机恶意进程隔离 | 由可信 IdP/OIDC 提供身份；公网用户必须登录，服务器验证 issuer、audience、签名、过期及授权声明 |
| Actor | 服务端配置的单一本地 principal；删除任意用户选择器的身份效力，不能接受任意 `X-User-ID` | 后端根据已验证 issuer+subject 映射 stable `user_id`，客户端 ID 仅作资源 ID并经 owner/capability Query 校验 |
| 浏览器会话 | 本机同源，短生命周期 server session；Host-only、HttpOnly、SameSite cookie；Origin 校验和写请求 CSRF token；数据目录用 OS ACL | 首选 OIDC Authorization Code + PKCE，后端建立 server-side session；Secure/HttpOnly/SameSite cookie、CSRF token、严格 Origin/CORS allowlist、HTTPS |
| 撤销/密钥 | 本地随机 secret 由受支持的 OS credential storage 提供；不得自行发明签名/token 方案 | Session TTL、服务端撤销/全局 logout；短期访问凭证，refresh token 安全保管或不用；IdP 密钥轮换按标准库机制处理 |
| 权限 | 单个本地账户可用的固定能力；不提供多用户角色 | IdP scopes/roles 经服务端白名单转为 capability；每个数据 owner 模块仍做资源授权 |
| 成本/风险 | 改造较小；不适合远程协作、共享主机或公网 | 支持多用户，但需 IdP、域名/TLS、会话存储、账号运维和安全响应 |
| 发布主张 | “本机单账户应用”，明确同机进程信任模型 | 在真实部署环境完成认证与授权审查后，才可称多用户服务 |

**决策：** 采用 B。Auth 使用标准 OIDC API Access Token 验证与 JWKS；项目不实现密码学或密码存储。具体 IdP 尚待配置。Streamlit production UI 已要求原生 OIDC 登录并将 server-side API Access Token 交给独立验证的 FastAPI；由于 IdP 和实际浏览器链路未验证，仍不得对公网开放。

## 最小实施顺序（决策后）

1. `app.auth` 定义 VerifiedPrincipal、ActorContext、OIDC 验证器与身份映射 Command/Query；真实 provider 配置由部署注入。
2. FastAPI `get_actor_context` 验证 bearer 并为私有路由注入可信 Actor；development 的本地 header 限制为直接 loopback，production 无 header fallback。
3. Streamlit 原生 OIDC gate 与 Bearer Client 已接线；配置真实 Provider 后验证 callback、API audience、401/过期和 browser session。API 每次独立验证面向 API audience 的 Access Token。
4. 私有 FastAPI 路由已统一使用 actor dependency；业务服务继续检查 owner。MCP/OCR HTTP 调用位于这些路由之后，stdio server 不暴露公网。
5. 本地测试覆盖匿名 401、header 冒充无效、A/B 会话隔离、过期/篡改/错误受众 token、禁用用户与 owner 404；真实 IdP 和撤销需补验。
6. 身份映射单独写入 Auth SQLite，旧业务数据不迁移；未来需独立备份/导入方案。
7. 生产部署仍须完成 TLS、受信代理、CSRF/session、请求限制、密钥轮换、日志去敏及恢复演练。

## 本轮兼容及边界

本轮 Auth 实现由 Auth 与 Auth-C 记录；未修改真实业务数据库。所有私有 API 路由使用可信 Actor dependency；production 无 header fallback。Streamlit 缺少真实 OIDC 配置或 API token 时 fail-closed。scope 与依赖发布任务见 [`V1_RELEASE_SCOPE.md`](V1_RELEASE_SCOPE.md)。

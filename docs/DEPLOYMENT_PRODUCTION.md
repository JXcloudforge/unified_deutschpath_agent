# 公网生产部署草案

状态：**设计草案，未部署、未开放公网**。目标形态为单 Linux VPS、Docker Compose、外部托管 OIDC：Caddy 提供 HTTPS，Streamlit 仅对 Caddy 暴露，FastAPI 仅在 Docker 内网可访问。

```text
Internet --HTTPS--> Caddy --HTTP--> Streamlit --private network--> FastAPI
                                             FastAPI --> OIDC JWKS / providers
                                  persistent /data volume: SQLite, Chroma, uploads, MCP state
```

## 部署草案

仓库 `deploy/Dockerfile` 使用项目 Python 依赖；Compose 只发布 Caddy 的 80/443 端口，API 不配置宿主机 `ports`，Streamlit 只加入代理网络，API 与 Streamlit 共享内部网络。单 API 副本是 SQLite/Chroma 的前提。`deploy/Caddyfile` 使用必填 `APP_DOMAIN` 自动 TLS；生产启动要求 `APP_ENV=production` 和完整 OIDC issuer、audience、JWKS 配置，禁止本地 header 身份。

Compose 仍是草案，不得据此直接开放公网。Auth-C 已实现 Streamlit 原生 OIDC/Bearer 客户端接线，但真实 IdP、浏览器会话安全和部署仍未验收。Streamlit 容器要求环境变量 `STREAMLIT_SECRETS_FILE` 指向宿主机只读配置文件，Compose 将它挂载到 `/app/.streamlit/secrets.toml`；以 `.streamlit/secrets.toml.example` 为模板，真实文件与密钥不得提交。Compose 内 UI 到 API 仅允许固定私网地址 `http://api:8765`；其他 production API 地址必须 HTTPS。FastAPI 不映射宿主机端口。

## 必须完成的运行控制

- 使用正式域名和可信托管 OIDC；限制 issuer/audience，验证 RS256/ES256 签名及 JWKS 轮换，密钥从部署 secret store 注入。
- Caddy 只代理 Streamlit；可信代理头由 Caddy 覆盖，FastAPI 不对公网开放。防火墙仅放行必要 SSH 和 80/443。
- Caddy 草案将 HTTP body 限制设为 25 MB（需 Caddy 2.10+ 的 `request_body`）；应用层附件限制为 20 MiB，OCR 路径仍需单独统一。还须配置超时、并发/速率限制与 AI 月度成本预算；现有代码尚无通用限流，未验收。Caddy 的 `request_body` 当前标记为实验功能，升级后需复核配置。[官方文档](https://caddyserver.com/docs/caddyfile/directives/request_body)
- OIDC callback 必须与 provider 控制台及 secrets 中的 HTTPS 域名完全一致；API audience 同时配置在 provider token 请求与 FastAPI verifier。`st.logout()` 不保证 IdP 全局登出或令牌撤销，需按选定 IdP 实测退出、过期与重新登录。跨站来源、WebSocket 与 CSRF 策略须在 Caddy/浏览器实际环境安全审查。
- `/data` 使用加密持久卷并限制容器用户权限；SQLite 单副本，验证 busy timeout、并发写入、停机一致性。Chroma、附件和 MCP 状态都纳入备份。
- 定期加密备份至异地存储，保存密钥分离；演练从备份恢复到隔离 VPS，并核对 SQLite integrity、会话附件和向量数据。
- 日志不得包含 Authorization、Cookie、上传内容或用户完整对话；监控健康、磁盘、内存、错误率、备份年龄和成本。
- 容器配置 restart policy、健康检查、只读根文件系统（评估后启用）、资源限制和最小 Linux capabilities；保护 Streamlit WebSocket 与 OIDC callback。
- 单实例达到明确并发/锁等待目标前保留 SQLite；超过目标先做负载与备份恢复验证，再单独 ADR 规划 PostgreSQL，不在本轮批量迁移。

## 验证状态

本机只有 Fake OIDC/JWKS 与 TestClient 证据。Docker 构建/Compose 生命周期、真实 OIDC、公网 HTTPS、VPS 备份恢复、限流/成本控制均 NOT VERIFIED。未购买服务器、域名或调用外部付费 API。

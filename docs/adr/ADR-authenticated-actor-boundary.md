# ADR：将可信身份验证与业务 Actor 权限分离

- 状态：Accepted（采用 OIDC 公网多用户目标；真实 IdP 部署仍待配置与验收）
- 日期：2026-10-13

## 背景

FastAPI 将调用方提供的 `X-User-ID` 转换成 Conversation 定义的 `ActorContext`。多个业务库以该值过滤 owner，但它没有认证来源；伪造 Header 可以冒充任意用户。拒绝生产写操作没有保护读取。认证代码若直接进入 Chat/CRM/M08 Repository，会令每个模块耦合 HTTP 与 IdP 细节。

## 决策

使用独立 `app.auth` 认证边界验证 OIDC API Access Token 签名、issuer、audience、expiry 与 Access Token 标记，并以 `(issuer, subject)` 映射 Auth-owned SQLite 稳定内部 `user_id`。FastAPI 依赖注入 ActorContext；业务模块通过各自 Query/Command 做资源 owner 校验。生产无 Header fallback。Streamlit 登录与 Bearer/BFF 集成单独实施和验收。

## 备选方案

- 继续信任 `X-User-ID`：改动最少，但任何调用者都能冒名，拒绝。
- 各模块自行校验 token：重复验证、策略分叉并耦合 IdP，拒绝。
- 直接接受客户端角色/用户 ID：可伪造，拒绝。
- 在项目内自建密码体系：扩大风险且没有必要，拒绝。
- 立即绑定某个托管 IdP：本轮不做；部署注入 issuer/audience/JWKS，业务模块不耦合 provider SDK。

## 取舍与风险

边界清晰且可替换认证方式，不要求微服务或分布式事务。Auth 为新主体分配 UUID，不自动认领本地旧数据。代价是迁移 Streamlit/API 调用契约并建立负向隔离测试。Cookie/CSRF/CORS、撤销和旧数据导入仍待真实登录设计。

## 后续

配置 IdP 后测试真实 JWKS 轮换、受众/过期/禁用用户；完成 Streamlit 登录、会话安全和双账户隔离，再进行 VPS 部署恢复演练。ADR 接受不解除发布阻塞。

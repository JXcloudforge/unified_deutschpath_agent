# 身份映射边界

日期：2026-10-13。Auth 模块管理身份提供方主体与 Deutschpath 稳定用户 ID 的映射，不接管 Conversation、UserState 或编排数据。

## 映射规则

`(issuer, subject) -> internal user_id` 使用复合主键。issuer 与 subject 均来自已验证的 OIDC API Access Token；email、name、客户端 header 和请求 body 不参与映射。内部 ID 使用随机 UUID，不从 subject 派生。相同 issuer/subject 跨重启保持稳定；issuer 不同的同名 subject 得到不同 ID。

Auth 独占 `identity_mappings` SQLite 表与 `AUTH_DATABASE_PATH`。首次映射在 `BEGIN IMMEDIATE` 事务中插入，唯一约束避免并发重复映射；映射记录 DTO 不暴露 SQL 行。默认角色由服务端写入 `member`，令牌角色声明不授予管理权限。禁用身份会拒绝后续认证。

## 公开契约

- `AuthService.authenticate(access_token) -> ActorContext`：先验证签名、issuer、audience、expiry、subject 和 Access Token 标记，再解析/创建身份。
- `IdentityMappingService.resolve_or_create_identity(VerifiedPrincipal) -> IdentityRecord`：认证适配器内部公开调用，不接受未经验证的 claims。
- `get_identity(actor, user_id)`：本人或可信 admin Query；不存在时 `KeyError`。
- `set_identity_enabled(actor, user_id, enabled)` / `set_identity_roles(actor, user_id, roles)`：仅已认证 server-managed admin 可调用；非法角色 `ValueError`，权限不足 `IdentityAccessDenied`。

业务模块只收到 `ActorContext(user_id, authenticated, roles, issuer, subject)`，继续在各自 Query/Command 中校验资源归属。Auth 不迁移或自动认领已有本地 ID；任何历史数据关联需单独导出映射、备份、冲突检查及回滚演练。

## 限制

当前角色管理只有模块契约，没有管理 UI/HTTP 接口；首次用户均为 member。SQLite 单实例是当前预期，身份库与各业务库不参加跨库事务。OIDC provider、audience、JWKS URL 尚未配置，真实登录 NOT VERIFIED。

生产 Streamlit 的 OIDC `iss+sub` 哈希仅作 UI session-state 缓存分区，不是内部 user_id，也不承担授权。生产 API Client 只发送 `Authorization: Bearer <access token>`，API 每次独立验签并从 Auth 映射内部 user_id。401 后当前 Client 清除凭据并要求重新登录；Streamlit logout 不承诺 IdP 全局登出或 token 撤销。

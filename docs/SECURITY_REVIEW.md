# M10 安全审查

日期：2026-10-13；审查范围为当前本机工程代码与运行配置，不是渗透测试或公网部署认证。

## 发现及处置

| 严重度 | 发现 | 处置/状态 |
|---|---|---|
| Critical（公开部署） | `X-User-ID` 是未认证的调用方输入；生产写接口 fail-closed，但读取仍按该值分区 | BLOCKED：不得对公网提供用户数据；须接可信身份并将所有 Query/Command 绑定认证主体 |
| High | 附件原先在 Conversation owner 校验前写入，无类型/体积上限 | 已修复：先校验 owner，只允许 TXT/MD/PDF/DOCX，读取上限 20 MiB；对应 HTTP 回归增加 |
| Medium | multipart 传输在 endpoint 前可能已 spool，应用限制不能覆盖网络/代理缓存资源 | BLOCKED（部署）：设置 HTTP Server/代理 body limit、超时、临时目录配额 |
| Medium | UserState API 组合根直接依赖 Repository 实现 | 已修复：使用 `UserStateService.from_path` 工厂；数据契约未变 |
| Medium | API 上传暂存文件在解析或 RAG 索引异常时可能留下孤儿文件；元数据与 Chroma 不共享事务 | 延期：定义文件所有权、补偿和清理策略，做失败注入后再作为正式运维能力 |
| Low | `.env`、数据库、Chroma、uploads、日志被 `.gitignore` 排除 | PASS（配置检查）；提交前仍需逐文件 review staged/unstaged diff |
| High | 可选外部 Provider 密钥配置不表示真实连接已验证 | NOT VERIFIED：本轮没有外呼，不将本地配置或 Mock 当在线证据 |

## 本机安全运行约束

- 仅在本机 loopback 运行；不通过局域网/公网暴露 FastAPI 或 Streamlit。
- M08 开关默认关闭；生产 mutation 路由拒绝写入。不要通过打开实验开关替代认证。
- API 密钥只保存在被忽略的 `.env` 或受保护环境变量，不进入截图、日志、报告或 Git。
- 使用 `STAGE2_DATA_PATH` 指定本地受控数据目录，并离线备份；不要将运行数据库加入仓库。
- 上传扩展名来自请求文件名，仅做解析路由，不构成 MIME/恶意内容检测。PDF/DOCX 等解析器的资源消耗仍需部署级限制。

生产认证、部署控制、真实外部服务和附件补偿策略的证据列于 `docs/RELEASE_BLOCKERS.md`。
可信 Actor 的调用图和方案比较见 `docs/architecture/AUTHENTICATION_BOUNDARY.md`、`docs/SECURITY_AUTH_PLAN.md`。当前设计尚未实施；伪造 `X-User-ID` 读取其他用户私有数据仍是发布阻塞。

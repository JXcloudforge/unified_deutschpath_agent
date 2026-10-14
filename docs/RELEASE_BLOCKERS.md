# v1.0 发布阻塞清单

截至 2026-10-13；版本保持 `0.1.1.dev0`。当前范围唯一规范为 [`V1_RELEASE_SCOPE.md`](V1_RELEASE_SCOPE.md)；M10 本机自动化通过不代表正式发布可用。M08 泛化规划已列为 DEFERRED，不是冻结范围内的功能阻塞。

| 优先级 | 阻塞项 | 发布影响 | 最小关闭证据 |
|---|---|---|---|
| P0 | Auth-C 已接入 Streamlit OIDC gate 和 Bearer API Client，但没有真实 IdP/域名；浏览器会话安全、双真实用户公网资源隔离、token expiry/logout/revocation 未验收 | 公网 UI 不可安全登录，阻止上线 | 真实 OIDC 联调、两用户覆盖私人资源、CSRF/Origin/过期/登出策略和公网 HTTPS 验收通过；详见 `docs/PHASE4_M10_AUTH_UI_ACCEPTANCE.md` |
| P0 | 代码已同步到从目标仓库 clone 的独立副本，但发布 diff 尚未由用户最终审查/提交；源开发目录的 CRM-agent remote 未复制或改动 | 未经审查的工作树不能成为课程提交 | 核对 `git remote -v`、`git diff --stat`、`git status --short` 与下述排除清单；仅按明确 allowlist 提交 |
| P0 | Router 150 条独立集仍 150/150 `unreviewed` | 未满足独立准确率门槛，不能声称 ≥98% | 人工独立标注、分歧裁决、冻结标签/哈希/流程后一次性报告；≥147/150 才满足 Accuracy 98% |
| P1 | DeepSeek/Tavily 真实外呼未执行 | 无外部服务可用性和来源证据 | 获准执行可能产生费用的请求；记录模型/查询、状态码、延迟、错误处理与来源，隐藏密钥 |
| P1 | MCP Inspector GUI 未验收 | GUI 工具发现、Schema 和确认流程缺真实可视证据 | 专用测试 DB 上人工运行 Inspector，截图并验证 preview/confirm/readback/跨用户 |
| P1 | Docker Compose/Caddy 仅有草案；无可复现 lock/image digest、HTTPS、请求体/速率限制、成本预算、持久卷、完整备份恢复及监控演练 | 不可称生产就绪 | 依 `V1_RELEASE_SCOPE.md` 任务 3、7、8 固定运行版本并通过隔离环境构建、部署、安全和恢复验收 |
| P2 | 附件字节长期所有权、解析/RAG 失败后的孤儿文件清理未闭环 | 可能留下运行目录冗余文件 | 选定 File/Conversation 所有权与补偿清理策略，增加失败注入测试 |

不得为满足数字门槛自动生成人工标签或在独立集上调参。依赖顺序、交付物、命令和 PASS 标准见 `V1_RELEASE_SCOPE.md`。P0/P1 关闭及人工证据完成后，重新跑发布回归并单独签署正式验收。

历史注意：目标仓库初始提交中曾包含未审阅 Router 工作表及历史样例；这些文件已从当前发布工作树移除或只保留空白题目表，但因保留 Git 历史，初始提交中的对象仍可查阅。不得把该已公开题库用于声称未泄漏的盲测。

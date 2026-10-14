# v1.0 公网正式版发布清单

当前状态：**NOT READY**。版本保持 `0.1.1.dev0`。范围分类、逐项交付物、命令、PASS 标准和阻塞条件统一记录在 [`V1_RELEASE_SCOPE.md`](V1_RELEASE_SCOPE.md)；本文件只记录执行勾选，不复制详细验收设计。阻塞现状见 [`RELEASE_BLOCKERS.md`](RELEASE_BLOCKERS.md)。

## 依赖顺序

- [ ] **0 — Git 来源与发布范围**：确认本副本来自 `unified_deutschpath_agent`，发布前逐项审查 allowlist 与 diff。原开发目录 `.git` 未复制，其 CRM-agent remote 保持未改。
- [ ] **1 — OIDC Provider 配置**：issuer、API audience/scope、JWKS/metadata、HTTPS callback、测试账户和 secrets 注入已准备。
- [ ] **2 — 两真实用户权限验收**：Conversation、UserState、附件、RAG、M08/M09、OCR/MCP 的互相拒绝与本人访问通过；Fake/JWKS 不替代真实联调。
- [ ] **3 — 可复现容器构建**：锁定依赖、基础镜像 digest、Docker Compose 与 Caddy 版本；隔离环境构建通过。
- [ ] **4 — DeepSeek/Tavily 实际联通**：仅在获准真实外呼后记录状态、延迟、错误处理和来源。
- [ ] **5 — Router 150 题盲测**：两人独立标注、人工裁决、题目独立性审核和 SHA-256 冻结；准确率至少 147/150 并完整报告其余指标。
- [ ] **6 — MCP Inspector GUI**：专用数据库上的工具 Schema、preview/confirm/readback、越权拒绝和真实截图通过。
- [ ] **7 — 隔离生产拓扑**：域名 HTTPS、OIDC callback/WebSocket、FastAPI 内网、上传限制、限流、成本预算与安全审查通过。
- [ ] **8 — 数据恢复**：SQLite、Chroma、附件/MCP 状态从备份在隔离环境恢复并核验；单实例并发/锁等待符合目标。
- [ ] **9 — 发布候选签署**：同一候选构建的全量测试、HTTP 集成、安全与所有发布阻塞项复验完成。

## 自动化复测命令

```powershell
.\scripts\run_tests.ps1
.\.venv\Scripts\python.exe -m pytest tests\integration\test_api_smoke.py -q
.\.venv\Scripts\python.exe scripts\m08_b_http_acceptance.py
.\.venv\Scripts\python.exe scripts\m08_c_http_acceptance.py
.\.venv\Scripts\python.exe scripts\m09_http_acceptance.py
.\.venv\Scripts\python.exe scripts\mcp_b6_http_acceptance.py
.\.venv\Scripts\python.exe -m compileall -q app ui scripts tests
git diff --check
git diff --cached --check
```

真实 OIDC、Router 人工盲测、Provider 外呼、MCP Inspector GUI、生产 TLS 和数据恢复要按 `V1_RELEASE_SCOPE.md` 执行并留存各自证据；上面的自动命令不能替代它们。版本变更、Commit、Tag、Release、remote 变更和 Push 仍需单独授权。

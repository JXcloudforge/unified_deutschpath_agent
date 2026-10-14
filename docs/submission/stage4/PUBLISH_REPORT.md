# 阶段四课程作业发布副本报告

日期：2026-10-14。应用版本：`0.1.1.dev0`，不是正式 `v1.0.0`。

## 仓库来源

- 开发源目录与发布目录是两个独立 Git 工作树。发布目录在目标仓库 `https://github.com/JXcloudforge/unified_deutschpath_agent.git` 上通过普通 `git clone` 建立，初始 HEAD 为 `8f6c070 Initial release: Deutschpath Unified Agent v0.1.1.dev0`。
- 发布副本 `origin` fetch/push 均指向上述 `unified_deutschpath_agent.git`；开发源目录的 `.git` 未复制，其旧 CRM `origin` 未修改。
- 本次仅建立未提交的发布候选工作区；没有执行 `git add`、commit、Tag 或 Push。

## 同步内容与排除

从开发源目录按预览白名单同步 **221 个源文件**：`app/`、`ui/`、`scripts/`、`tests/`、精选 `evals/` 数据和脚本、架构/验收/阶段文档、发布模板、启动入口及依赖声明。M07 Conversation、M08 Orchestration、M09 Suggestions、M10/Auth-C 的代码、测试和报告都在副本中。

包含的 Router 人工评估输入只有 150 行**空白标签**工作表和指南，保留其 `unreviewed` 状态，不含预测/裁决答案。300 题开发集指标只作为开发证据。

未从开发目录复制：`.git/`、`.env`、`.venv/`、缓存/`__pycache__/`、SQLite/Chroma 运行数据、上传、真实 Streamlit secrets、密钥/Token、用户会话与附件、日志、Router 近重复审查输出及 DeepSeek/Tavily 在线响应样例。路径与密钥扫描通过；`.streamlit/secrets.toml.example` 仅是占位模板。

为移除旧快照中的重复或不适合当前提交的材料，以下 7 个旧文件仅从发布副本当前工作树删除；原目标 Git 历史未被改写：

- `docs/history/final-cleanup-20261013.md`
- `docs/history/legacy-deletion-git-impact-20261013.txt`
- `evals/b3_router_review_annotation_guide.md`
- `evals/b3_router_review_candidates.csv`
- `evals/v011_deepseek_semantic_trial.json`
- `evals/v011_hybrid_live_baseline.json`
- `evals/v011_review_overlap.json`

目标仓库初始提交中曾有未审阅题目表及历史资料；当前工作树移除不等于从 Git 历史或 GitHub 缓存抹除。150 题标签尚未冻结，该公开题库不能再作为对开发人员保密的全新盲测集。

## 文档与课程证据

- 更新中文 `README.md`，如实说明 M07、有限 M08、M09、M10 的能力、启动、测试及生产限制。
- 同步 `docs/architecture/`、ADR、`docs/PHASE4_*`、`docs/V1_RELEASE_SCOPE.md`、`RELEASE_CHECKLIST.md`、`RELEASE_BLOCKERS.md`、技术栈和版本中心文件。
- 新增本阶段提交包：`README.md`（本目录）、`PROBLEM_FIXES.md` 与本报告；附阶段四 Mermaid 架构图和真实截图操作步骤。当前没有实际运行截图，不生成或伪造截图。
- 相对 Markdown 链接检查通过；README 命令拼写经逐项审查，`start_app.ps1 -CheckOnly` 已在副本通过。全新无系统包隔离环境的安装还未验证。

## 本次真实验证

| 命令 | 结果 |
|---|---|
| `scripts/run_tests.ps1` | exit 0；269 passed、1 skipped、0 failed；83.27 秒；2 条弃用警告。唯一 skip：Windows symlink 权限限制 |
| `python -m pytest tests/integration/test_api_smoke.py -q` | exit 0；1 passed、0 failed；2 条依赖弃用警告 |
| `scripts/m08_b_http_acceptance.py` | exit 0；loopback HTTP，普通 Chat、澄清、确认/恢复、重复确认及跨用户拒绝通过，改名 Query 读回匹配 |
| `scripts/m08_c_http_acceptance.py` | exit 0；`rename_session` Command 与 `list_sessions` Query 两步成功，确认重放不重复执行 |
| `scripts/m09_http_acceptance.py` | exit 0；opt-in 三条建议、旧响应兼容与跨用户拒绝通过 |
| `scripts/mcp_b6_http_acceptance.py` | exit 0；真实 Uvicorn/stdio MCP，确认前 0 行、确认后插入并读回 3 行、跨用户拒绝、正常关闭 |
| `scripts/start_app.ps1 -CheckOnly` | exit 0；Python、依赖、版本及默认端口预检通过；没有实际打开服务窗口 |
| `python -m compileall -q app ui scripts tests` | exit 0 |
| `git diff --check`; `git diff --cached --check` | 均 exit 0；Git 对 LF/CRLF 转换有提示，无空白错误 |
| `scripts/evaluate_intents.py` | 18/18；离线小样本，不是 Router 独立验收 |

回归在发布副本运行；为执行发布脚本建立了使用系统 site-packages 的 `.venv` 并安装 editable 项目。测试也生成了 `.pytest_cache/`、`__pycache__/` 和 `data/` 下 SQLite/Chroma 临时文件。这些路径均被 `.gitignore` 排除，`git status`/普通 `git add -A` 不会纳入它们，但本轮操作环境拒绝了递归清理命令，因此它们仍留在副本磁盘上；打包 ZIP 或复制整个目录前需人工清理这些本轮生成产物。该证据不能替代干净隔离安装、Docker build、真实 OIDC 或公网验收。

## 提交前清单

1. 打开真实截图指南逐项操作，并将截图存入课程受控提交系统；不把用户附件、Token、密钥或真实会话加入仓库。
2. 审查全部更改、删除与未跟踪文件；确认历史遗留盲测数据公开对评测的影响。
3. 在用户确认后才执行本地提交与 Push。示例命令如下；当前工作树尚未提交：

```powershell
cd <Deutschpath_agent_publish>
git remote -v
git status --short
git diff --stat
git diff --check
git add -A
git diff --cached --check
git diff --cached --stat
git commit -m "Prepare Deutschpath phase four course release"
git push origin main
```

不要使用 `git push --force`。目标仓库远端历史和首个提交被保留；本报告不代表可以发布公网 v1.0。

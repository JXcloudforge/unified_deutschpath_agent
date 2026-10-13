# Stage 3 课程最终验收

日期：2026-10-13  
项目版本：`0.1.1.dev0`  
验收范围：课程要求的 Router、真实 Web Search、RAG/Router/Web/LLM 联动。未开发业务功能。

## 三项课程考核状态

| 课程要求 | 状态 | 本轮证据与边界 |
|---|---|---|
| 三分类 Router 准确率 ≥98% | **NOT VERIFIED** | 本轮 Rules 在 300 条工程开发候选集上为 300/300；已有人类标注工作表 150 行，但 150 行均为 `unreviewed`，没有裁决或冻结，因此不得宣称正式 98% PASS。既存 Hybrid 开发集报告也是候选集成绩。 |
| 网络搜索真实获取在线信息 | **PASS** | 隔离 Uvicorn 的真实 HTTP 请求触发 Rules `web_search`，真实 Tavily 返回 5 条结果及原始 HTTPS 来源 URL；真实 DeepSeek 生成回答并包含来源段。未用 Fake 服务。 |
| RAG、Router、Web、LLM 协调运行 | **PASS** | 隔离真实 HTTP Mixed Sources 请求：附件上传 200、消息 200；Router=`web_search`、`mixed_sources=true`；诊断记录本地证据 1 条、网页证据 5 条，二者进入 LLM 上下文；回答包含本地与网页来源，历史读取到用户和助手共 2 条消息。 |

## 本轮真实运行

- Rules 当前 300 条开发集：300/300，Accuracy 1.000，Macro F1 1.000，mixed_sources 15/15；矩阵和数据集性质见 [ROUTER_EVALUATION.md](ROUTER_EVALUATION.md)。
- 实时普通 Web Search：真实 Tavily 返回 5 条结果；真实 DeepSeek 请求成功，回答含来源链接。
- Mixed Sources：真实 Tavily 搜索词为“德国目前Ausbildung签证的公开语言要求，指出学习计划还缺少什么”。搜索词不含附件里的学习安排。Tavily 返回 5 条结果，其中包含德国驻华使领馆的签证说明 PDF：<https://china.diplo.de/resource/blob/2382334/af2b5d3313afe75e4f3325f4a9399b88/pdf-merkblatt-natvisum-ausbildung-data.pdf>。
- Mixed Sources 响应含本地来源引用和网页 URL；服务器诊断确认 `local_count=1`、`web_count=5`、`llm_context=true`。附件正文未写入验收日志或发送给 Tavily。
- 隔离数据目录位于系统临时目录；正式 SQLite、Chroma、附件及端口 8000 未用于写入。
- 本轮 HTTP harness 有 4 个中断/完成后的隔离目录留在 Windows `%TEMP%`，名称为 `deutschpath-stage3-*`，合计约 1.15 MB，仅包含本轮临时 Chroma/SQLite/上传副本。当前执行策略拒绝递归删除系统临时目录内容，因此未强行绕过；可在确认无服务占用后由用户清理这些精确目录。项目根目录没有新增测试数据目录。
- `scripts/run_tests.ps1`：**200 passed, 1 skipped**。唯一跳过是 Windows 账户不能创建 symlink 的安全测试（`tests/unit/test_ocr_mcp.py:104`）。有一条 Chroma 上游 `asyncio.iscoroutinefunction` 弃用警告。
- `python -m compileall -q app ui scripts tests evals`：**PASS**。
- 自动化 pytest 排除了需另行使用真实服务的 `tests/integration/test_api_smoke.py`；本轮另以临时端口启动真实 Uvicorn 完成普通 Web 与 Mixed Sources HTTP 流程。

## 剩余缺口

正式 Router 98% 验收必须等人工独立标注、争议裁决、冻结 CSV 并记录 SHA-256 后再测。300 条开发集和其任何 Hybrid 对比不得用作独立盲测。当前对 Tavily 的真实验收证明返回了可引用网页，但结果中仍有第三方内容；正式课程演示应优先选用政府来源并人工核对页面内容与时效。

六张真实界面截图的采集步骤见 [SCREENSHOT_GUIDE.md](SCREENSHOT_GUIDE.md)。本轮未伪造截图，也未声称已保存浏览器截图。

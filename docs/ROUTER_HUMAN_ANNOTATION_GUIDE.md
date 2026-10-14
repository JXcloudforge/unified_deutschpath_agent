# Router 150 题人工独立标注操作指南

当前工作表为准备状态：150 条、14 列、150 个唯一 `case_id`；150 条 `review_status=unreviewed`，两位标注者和裁决标签均为空。**不要把 Router 预测、300 开发集标签或建议标签粘贴进本表。** 原工作表只读保留，标注工作在生成的独立副本完成。

## 标签口径

- `rag`：需要本地知识、附件或既有资料检索的请求。
- `web_search`：事实新鲜度重要、需要查询公开当前信息的请求。
- `no_tool`：普通交谈、翻译、改写、生成，不需检索或实时信息。
- `mixed_sources=true`：同一请求同时需要本地附件/知识和当前公开信息；其 `intent` 必须为 `web_search` 且 `has_attachment=true`。否则为 false。
- 标注者只填自己编号的 `intent` 与 `mixed_sources` 两列。不得看 Router 输出；遇到含糊题目先记录在个人 `notes`，不得修改题面。

## 工作流

从项目根目录运行。准备的两份文件应交给不同标注者，彼此完成前不交换答案：

```powershell
.\.venv\Scripts\python.exe scripts\router_human_eval.py audit
.\.venv\Scripts\python.exe scripts\router_human_eval.py prepare --annotator 1 --output evals\human_run\a1.csv
.\.venv\Scripts\python.exe scripts\router_human_eval.py prepare --annotator 2 --output evals\human_run\a2.csv
```

将 a1.csv、a2.csv 分别交给独立标注者。程序交互会逐题显示 `case_id`、附件标志和原始题面，再收集允许的标签；不会加载 Router 或输出预测。标注者完成各自副本后：

```powershell
.\.venv\Scripts\python.exe scripts\router_human_eval.py annotate --input evals\human_run\a1.csv --annotator 1
.\.venv\Scripts\python.exe scripts\router_human_eval.py annotate --input evals\human_run\a2.csv --annotator 2
.\.venv\Scripts\python.exe scripts\router_human_eval.py merge --annotator-1 evals\human_run\a1.csv --annotator-2 evals\human_run\a2.csv --output evals\human_run\merged.csv
```

`merge` 检查两份题面、附件和 ID 完全一致，检查标注者列没有串位。共识条目以两位人工标签作为最终标签；任一意图或 mixed_sources 不同的行保持 `needs_adjudication` 且裁决为空。由第三人完成分歧裁决：

```powershell
.\.venv\Scripts\python.exe scripts\router_human_eval.py adjudicate --input evals\human_run\merged.csv --output evals\human_run\adjudicated.csv --adjudicator reviewer-1
```

裁决人逐题看原文、两方标签及分歧原因，给出最终意图、mixed_sources 和非空理由。不得自动择取预测答案。完成后校验及冻结：

```powershell
.\.venv\Scripts\python.exe scripts\router_human_eval.py audit --input evals\human_run\adjudicated.csv
.\.venv\Scripts\python.exe scripts\router_human_eval.py freeze --input evals\human_run\adjudicated.csv --output evals\frozen\v011-independent-001.csv --manifest evals\frozen\v011-independent-001.manifest.json --batch v011-independent-001
```

冻结只接受 150 行、14 列、ID 唯一、合法标签齐全、全部 adjudicated、冲突有裁决人和原因、无旧 freeze_batch 的合并件。会生成不可覆盖的 CSV 和包含 UTC 时间、batch、行数、标签计数、合并输入哈希及冻结 CSV SHA-256 的 manifest。冻结完成后保存副本并禁止改题/改标签；修改一个字节会使评估拒绝。

## 冻结后一次性独立评估

Rules 离线评估：

```powershell
.\.venv\Scripts\python.exe scripts\router_human_eval.py evaluate --manifest evals\frozen\v011-independent-001.manifest.json --router rules --output evals\frozen\v011-independent-001.rules-report.json
```

Hybrid 会调用当前配置的 DeepSeek 并可能产生费用，应在确定预算并获准后另行执行；FakeLLM 会被拒绝，避免假称真实 Hybrid：

```powershell
.\.venv\Scripts\python.exe scripts\router_human_eval.py evaluate --manifest evals\frozen\v011-independent-001.manifest.json --router hybrid --output evals\frozen\v011-independent-001.hybrid-report.json
```

报告包括 Accuracy、Macro F1、每类 Precision/Recall/F1、三类混淆矩阵、错例和 mixed_sources 二分类 TP/FP/TN/FN、Precision/Recall/F1/Accuracy。150 题的 98% Accuracy 至少需 147 题正确；还需审阅其他指标和错例。独立评估后若据此调参，则该集不再是未使用的盲测集，必须准备新独立集。

## 数据治理

保存标注者编号、日期、语言理解资格/流程版本、裁决记录及双方确认；审计资料不记录与评估无关的个人信息。先人工检查 `evals/v011_review_overlap.json` 中的 8 个 token-overlap 候选是否可能泄漏，然后由验收负责人决定是否替换；不得擅自改动现有题目。本轮没有填写任何标签，也没有生成冻结数据。

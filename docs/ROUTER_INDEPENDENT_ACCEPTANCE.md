# Router 独立验收状态

日期：2026-10-13。当前结论：**NOT VERIFIED**。

## 数据与结构审计

只读审计命令：

```powershell
.\.venv\Scripts\python.exe scripts\router_human_eval.py audit
```

本轮观测：CSV 编码可由 UTF-8 BOM 正确读取；14 列名及顺序符合工作表契约；150 行、150 个唯一 case_id；`review_status` 为 150 条 `unreviewed`；annotator 1/2、adjudicated intent 和 mixed_sources 字段全部空；freeze_batch 全空。未发现非法/重复 case_id 或格式错误。格式有效并不等于标签有效或验收完成。

`evals/v011_hybrid_300_final.json` 记录工程开发集 300/300、Accuracy 1.0、Macro F1 1.0、mixed_sources Accuracy 1.0；这是已有的开发记录，不作为本轮重跑结果、人工 ground truth 或独立测试证明。150 题候选与开发集语义独立性仍需人工核对 8 个 token-overlap 项。

## 冻结前置条件

- 两名标注者在互相隔离、无预测输出的工作副本上独立标注所有案例。
- 合并校验问题和附件字段完全一致；统计原始一致率及意图/mixed_sources 分歧。
- 所有分歧由第三方写入裁决标签、裁决者标识和理由；一致条目保留双人标签及共识结果。
- 检查 150 行全部有效、唯一、无缺标签；混合来源标签符合约束。
- 生成新的 frozen CSV + manifest；记录 batch、UTC 时间、原合并输入 SHA-256、冻结 CSV SHA-256、标签计数及流程责任人；冻结后不修改。
- 在冻结前完成人工题目独立性与潜在泄漏审查；一旦用于调参，不再称为盲测。

## 冻结后统计

`scripts/router_human_eval.py evaluate --manifest <manifest> --router rules|hybrid` 只接受 manifest 哈希匹配的冻结集。Rules 离线运行；Hybrid 要求真实 DeepSeek 配置且会发出可能计费请求，必须在另行获得授权后运行。报告输出 intent Accuracy、Macro F1、per-class Precision/Recall/F1、confusion matrix、errors，以及 mixed_sources 2×2 混淆统计和指标。

正式判定要求 Accuracy ≥0.98，即 150 题至少 147 题分类正确；同时评审分类召回/精确率、Macro F1、mixed_sources 和错误案例。只有冻结标签和真实运行报告都存在才可判 PASS。

## 当前矩阵

| 项目 | 结论 |
|---|---|
| 题目与 14 列结构、case_id 唯一性 | PASS |
| 两名人工标注、裁决、完整标签 | NOT VERIFIED（0/150） |
| 题目盲测独立性/泄漏审核 | NOT VERIFIED（8 个 overlap 候选待人工看） |
| freeze_batch 和 SHA-256 冻结记录 | NOT VERIFIED（尚未冻结） |
| Accuracy ≥98%、Macro F1、类别指标、mixed_sources 指标 | NOT VERIFIED（尚无 ground truth） |

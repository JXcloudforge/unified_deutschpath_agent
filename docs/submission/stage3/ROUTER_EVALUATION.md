# Router 评估记录

日期：2026-10-13。标签约定为 `rag`、`web_search`、`no_tool`；`mixed_sources` 是额外证据标记，不是第四类。

## 本轮 Rules 开发集重跑

执行：

```powershell
@'
from app.routing.evaluation import evaluate
from app.routing.rules import RuleBasedIntentRouter
from evals.intent_v2_dataset import build_cases
r = evaluate(RuleBasedIntentRouter(), build_cases())
print(r)
'@ | .\.venv\Scripts\python.exe -
```

结果：300 条、300 正确；Accuracy 100.00%，Macro F1 1.000；15 条带附件的 mixed_sources 样本为 15/15 正确。错误样本 0。

| 实际\标注 | rag | web_search | no_tool |
|---|---:|---:|---:|
| rag | 100 | 0 | 0 |
| web_search | 0 | 100 | 0 |
| no_tool | 0 | 0 | 100 |

该 300 条是人工工程审阅的开发候选集（每个基础提示加语言/表达变体），不是独立盲测，不能证明课程要求的独立 98%。旧 268/300（89.33%）是更早版本报告，不代表本轮代码；本轮结果通过 `evaluate()` 对当前 `RuleBasedIntentRouter` 直接重算。

## Hybrid 对比（已有工程评估证据）

本轮读取既有 [v011_hybrid_300_final.json](../../../evals/v011_hybrid_300_final.json)，没有为了再测候选集而重复调用外部模型：300/300，Accuracy 100%，Macro F1 1.000，mixed_sources 100%；32 次真实语义模型调用、0 失败、0 fallback，平均路由耗时 84.00 ms，P95 773.22 ms。该文件没有独立人工真值、实际 token 用量或可核实费用；`estimated_cost_usd` 为空，故不报告费用。此为既存工程候选集报告，不是本轮新测或正式盲测。

更早的 [v011_hybrid_300_after.json](../../../evals/v011_hybrid_300_after.json) 记录 298/300、48 次语义调用、1 次失败和 1 次回退。这说明报告来自不同调试轮次；评价时应明确引用所用报告，不能拼接成绩。本轮未重新运行全量 Hybrid 以避免重复 API 消耗。

## 独立候选标注集状态

`evals/v011_human_annotation_worksheet.csv` 共 150 行，本轮读取到的 `review_status` 全部为 `unreviewed`。没有人工标签、裁决标签或冻结批次。故正式 Accuracy、Macro F1、混淆矩阵、mixed_sources 准确率、错误案例和 98% 结论均为 **NOT VERIFIED**，不是 0%，也不是 PASS。

已存在的重叠筛查报告显示：归一化完全重复 0、字符相似度 ≥0.80 为 0、token Jaccard ≥0.40 的 8 条。筛查只用于提醒人工复核，不能证明语义独立；冻结前须人工检查这 8 条。

## 正式评估流程

1. 两位标注者分别填写独立意图与 `mixed_sources` 标签，不查看 Router 预测。
2. 第三方裁决争议并填写 `adjudicated_*`、理由、审阅者和 `review_status=adjudicated`。
3. 核查开发集重叠并确定排除或保留原则；冻结 CSV，记录 SHA-256 与 `freeze_batch`。
4. 冻结后 Rules 和 Hybrid 在同一冻结集运行一次；不得用该集调规则或提示。
5. 150 条至少 147 条正确才满足 98%；同时报告三分类矩阵、Macro F1、mixed_sources、Hybrid 调用/失败/回退和延迟。

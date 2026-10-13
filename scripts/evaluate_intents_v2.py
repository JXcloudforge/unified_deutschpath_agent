"""Run the 300-case offline candidate evaluation and write a machine-readable report."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.routing.evaluation import evaluate
from app.routing.rules import RuleBasedIntentRouter
from evals.intent_v2_dataset import build_cases


root = Path(__file__).resolve().parents[1]
report = evaluate(RuleBasedIntentRouter(), build_cases())
report.update({"dataset_version": "intent-v2-candidate-300", "label_status": "engineering-reviewed candidate; human annotation pending"})
output = root / "evals" / "intent_v2_report.json"
output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({key: report[key] for key in ("dataset_version", "label_status", "total", "correct", "accuracy", "macro_f1", "mixed_sources_accuracy", "mixed_sources_total", "confusion_matrix")}, ensure_ascii=False, indent=2))

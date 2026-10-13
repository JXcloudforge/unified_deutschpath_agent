"""Run the checked-in Stage 3 P1 intent evaluation dataset."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.routing.evaluation import evaluate, load_cases
from app.routing.rules import RuleBasedIntentRouter


root = Path(__file__).resolve().parents[1]
report = evaluate(RuleBasedIntentRouter(), load_cases(root / "evals" / "intent_cases.json"))
print(f"Intent evaluation: {report['correct']}/{report['total']} ({report['accuracy']:.1%})")
print("Per-class:")
for name, metrics in report["per_class"].items():
    print(f"- {name}: precision={metrics['precision']:.1%}, recall={metrics['recall']:.1%}")
print("Confusion matrix:")
for expected, counts in report["confusion_matrix"].items():
    print(f"- expected {expected}: {counts}")
if report["errors"]:
    print("Errors:")
    for item in report["errors"]:
        print(f"- expected={item['expected']} actual={item['actual']} message={item['message']}")

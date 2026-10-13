"""Dependency-free evaluation helpers for the Stage 3 intent baseline."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .models import Intent, RoutingContext
from .router import IntentRouter


@dataclass(frozen=True)
class IntentCase:
    message: str
    expected: Intent
    has_attachment: bool = False
    expected_mixed_sources: bool = False


def load_cases(path: str | Path) -> list[IntentCase]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return [IntentCase(item["message"], Intent(item["expected"]), bool(item.get("has_attachment", False)), bool(item.get("expected_mixed_sources", False))) for item in payload]


def evaluate(router: IntentRouter, cases: list[IntentCase]) -> dict:
    labels = list(Intent)
    matrix = {expected.value: {actual.value: 0 for actual in labels} for expected in labels}
    errors = []
    mixed_correct = mixed_total = 0
    for case in cases:
        decision = router.route(case.message, RoutingContext(has_attachment=case.has_attachment))
        actual = decision.intent
        matrix[case.expected.value][actual.value] += 1
        if actual is not case.expected:
            errors.append({"message": case.message, "expected": case.expected.value, "actual": actual.value})
        if case.expected is Intent.WEB_SEARCH and case.has_attachment:
            mixed_total += 1
            mixed_correct += decision.mixed_sources == case.expected_mixed_sources
    total = len(cases)
    per_class = {}
    for label in labels:
        name = label.value
        true_positive = matrix[name][name]
        predicted = sum(matrix[expected.value][name] for expected in labels)
        expected = sum(matrix[name].values())
        per_class[name] = {
            "precision": true_positive / predicted if predicted else 0.0,
            "recall": true_positive / expected if expected else 0.0,
        }
        precision, recall = per_class[name]["precision"], per_class[name]["recall"]
        per_class[name]["f1"] = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"total": total, "correct": total - len(errors), "accuracy": (total - len(errors)) / total if total else 0.0, "per_class": per_class, "macro_f1": sum(item["f1"] for item in per_class.values()) / len(per_class), "mixed_sources_accuracy": mixed_correct / mixed_total if mixed_total else None, "mixed_sources_total": mixed_total, "confusion_matrix": matrix, "errors": errors}

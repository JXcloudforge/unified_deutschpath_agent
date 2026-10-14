"""Prepare independent human Router annotation, freeze, and evaluate a frozen set.

This tool never predicts or fills labels. Annotators work on separate prepared
copies; only a complete, human-reviewed merged worksheet can be frozen.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.routing.evaluation import IntentCase, evaluate
from app.routing.models import Intent, RoutingContext
from app.routing.rules import RuleBasedIntentRouter


SOURCE = ROOT / "evals" / "v011_human_annotation_worksheet.csv"
EXPECTED_COLUMNS = [
    "case_id", "message", "has_attachment", "annotator_1_intent",
    "annotator_1_mixed_sources", "annotator_2_intent",
    "annotator_2_mixed_sources", "adjudicated_intent",
    "adjudicated_mixed_sources", "review_status", "notes",
    "disagreement_reason", "adjudicator", "freeze_batch",
]
INTENT_COLUMNS = ("annotator_1_intent", "annotator_2_intent", "adjudicated_intent")
MIXED_COLUMNS = ("annotator_1_mixed_sources", "annotator_2_mixed_sources", "adjudicated_mixed_sources")
ALLOWED_INTENTS = {item.value for item in Intent}
ALLOWED_BOOL = {"true", "false"}
ALLOWED_STATUS = {"unreviewed", "needs_adjudication", "adjudicated"}
ANNOTATION_FIELDS = [*INTENT_COLUMNS, *MIXED_COLUMNS, "review_status", "notes", "disagreement_reason", "adjudicator", "freeze_batch"]


class EvaluationDataError(ValueError):
    pass


def load_rows(path: Path) -> list[dict[str, str]]:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames != EXPECTED_COLUMNS:
                raise EvaluationDataError(
                    f"expected exactly {len(EXPECTED_COLUMNS)} columns in canonical order; got {reader.fieldnames!r}"
                )
            rows = list(reader)
    except (OSError, UnicodeError, csv.Error) as exc:
        raise EvaluationDataError(f"cannot read CSV: {exc}") from exc
    if any(None in row for row in rows):
        raise EvaluationDataError("CSV contains a row with extra columns")
    return rows


def source_issues(rows: list[dict[str, str]], *, require_complete: bool = False) -> list[str]:
    issues: list[str] = []
    if len(rows) != 150:
        issues.append(f"expected 150 rows; got {len(rows)}")
    ids = [row["case_id"].strip() for row in rows]
    if any(not case_id for case_id in ids):
        issues.append("case_id must not be blank")
    if len(set(ids)) != len(ids):
        issues.append("case_id values are not unique")
    for index, row in enumerate(rows, start=2):
        prefix = f"CSV row {index} ({row.get('case_id', '')})"
        if not row["message"].strip():
            issues.append(f"{prefix}: message is blank")
        if row["has_attachment"].strip().lower() not in ALLOWED_BOOL:
            issues.append(f"{prefix}: has_attachment must be true or false")
        for key in INTENT_COLUMNS:
            value = row[key].strip()
            if value and value not in ALLOWED_INTENTS:
                issues.append(f"{prefix}: illegal {key}={value!r}")
        for key in MIXED_COLUMNS:
            value = row[key].strip().lower()
            if value and value not in ALLOWED_BOOL:
                issues.append(f"{prefix}: illegal {key}={value!r}")
        status = row["review_status"].strip()
        if status and status not in ALLOWED_STATUS:
            issues.append(f"{prefix}: illegal review_status={status!r}")
        if require_complete:
            if status != "adjudicated":
                issues.append(f"{prefix}: review_status is not adjudicated")
            if any(not row[key].strip() for key in (*INTENT_COLUMNS, *MIXED_COLUMNS)):
                issues.append(f"{prefix}: missing annotator or adjudicated label")
            if _is_disagreement(row) and (not row["adjudicator"].strip() or not row["disagreement_reason"].strip()):
                issues.append(f"{prefix}: disagreement needs an adjudicator and reason")
            if row["freeze_batch"].strip():
                issues.append(f"{prefix}: input already has a freeze_batch; freeze from an unfrozen merged copy")
            intent = row["adjudicated_intent"].strip()
            mixed = row["adjudicated_mixed_sources"].strip().lower()
            if mixed == "true" and (intent != "web_search" or row["has_attachment"].strip().lower() != "true"):
                issues.append(f"{prefix}: mixed_sources=true requires web_search and an attachment")
            if not _is_disagreement(row) and (
                intent != row["annotator_1_intent"].strip()
                or mixed != row["annotator_1_mixed_sources"].strip().lower()
            ):
                issues.append(f"{prefix}: consensus labels must match both annotators")
    return issues


def _is_disagreement(row: dict[str, str]) -> bool:
    return (
        row["annotator_1_intent"].strip() != row["annotator_2_intent"].strip()
        or row["annotator_1_mixed_sources"].strip().lower() != row["annotator_2_mixed_sources"].strip().lower()
    )


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    if path.exists():
        raise EvaluationDataError(f"refusing to overwrite existing file: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=EXPECTED_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        raise EvaluationDataError(f"refusing to overwrite existing file: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def audit(path: Path) -> dict[str, Any]:
    rows = load_rows(path)
    issues = source_issues(rows)
    statuses = Counter(row["review_status"].strip() or "<blank>" for row in rows)
    missing_final = sum(not row["adjudicated_intent"].strip() or not row["adjudicated_mixed_sources"].strip() for row in rows)
    return {
        "path": str(path), "columns": len(EXPECTED_COLUMNS), "row_count": len(rows),
        "unique_case_ids": len({row["case_id"].strip() for row in rows}),
        "status_counts": dict(statuses), "missing_adjudication_count": missing_final,
        "structural_valid": not issues, "issues": issues,
    }


def prepare(input_path: Path, output_path: Path, annotator: int) -> None:
    rows = load_rows(input_path)
    issues = source_issues(rows)
    if issues:
        raise EvaluationDataError("source worksheet invalid: " + "; ".join(issues[:5]))
    prepared = []
    for original in rows:
        row = dict(original)
        for key in ANNOTATION_FIELDS:
            row[key] = ""
        row["review_status"] = "unreviewed"
        prepared.append(row)
    _write_csv(output_path, prepared)
    print(json.dumps({"prepared": str(output_path), "annotator": annotator, "rows": len(prepared), "predictions_included": False}, ensure_ascii=False))


def _prompt_intent(prompt: str, input_fn=input) -> str:
    while True:
        value = input_fn(prompt).strip()
        if value in ALLOWED_INTENTS:
            return value
        print("请输入以下标签之一：rag、web_search、no_tool。")


def _prompt_bool(prompt: str, input_fn=input) -> str:
    while True:
        value = input_fn(prompt).strip().lower()
        if value in ALLOWED_BOOL:
            return value
        print("请输入 true 或 false。")


def annotate(path: Path, annotator: int, input_fn=input) -> int:
    rows = load_rows(path)
    issues = source_issues(rows)
    if issues:
        raise EvaluationDataError("worksheet invalid: " + "; ".join(issues[:5]))
    intent_key = f"annotator_{annotator}_intent"
    mixed_key = f"annotator_{annotator}_mixed_sources"
    completed = 0
    for row in rows:
        if row[intent_key].strip() and row[mixed_key].strip():
            continue
        print(f"\n{row['case_id']} | attachment={row['has_attachment'].strip().lower()}\n{row['message']}")
        row[intent_key] = _prompt_intent("Intent [rag/web_search/no_tool]: ", input_fn)
        row[mixed_key] = _prompt_bool("Both attachment and current web facts are required? [true/false]: ", input_fn)
        row["notes"] = input_fn("Optional note (do not include personal data): ").strip()
        completed += 1
    temp = path.with_name(path.name + ".writing")
    if temp.exists():
        raise EvaluationDataError(f"refusing to overwrite temporary file: {temp}")
    with temp.open("x", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=EXPECTED_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    temp.replace(path)
    return completed


def _question_fingerprint(row: dict[str, str]) -> tuple[str, str, str]:
    return (row["case_id"], row["message"], row["has_attachment"].strip().lower())


def merge(first_path: Path, second_path: Path, output_path: Path) -> dict[str, int]:
    first, second = load_rows(first_path), load_rows(second_path)
    issues = source_issues(first) + source_issues(second)
    if issues:
        raise EvaluationDataError("annotation copy invalid: " + "; ".join(issues[:5]))
    if [_question_fingerprint(row) for row in first] != [_question_fingerprint(row) for row in second]:
        raise EvaluationDataError("annotators' case_id, message, or attachment columns differ")
    merged = []
    disagreements = 0
    for row_a, row_b in zip(first, second, strict=True):
        row = {key: row_a[key] for key in EXPECTED_COLUMNS}
        for key in ("annotator_1_intent", "annotator_1_mixed_sources"):
            if row_b[key].strip():
                raise EvaluationDataError("annotator 2 copy contains annotator 1 fields; use separate prepared copies")
        if any(row_a[key].strip() for key in ("annotator_2_intent", "annotator_2_mixed_sources")):
            raise EvaluationDataError("annotator 1 copy contains annotator 2 fields; use separate prepared copies")
        if not row_a["annotator_1_intent"].strip() or not row_a["annotator_1_mixed_sources"].strip():
            raise EvaluationDataError(f"annotator 1 missing labels for {row['case_id']}")
        if not row_b["annotator_2_intent"].strip() or not row_b["annotator_2_mixed_sources"].strip():
            raise EvaluationDataError(f"annotator 2 missing labels for {row['case_id']}")
        row["annotator_2_intent"] = row_b["annotator_2_intent"].strip()
        row["annotator_2_mixed_sources"] = row_b["annotator_2_mixed_sources"].strip().lower()
        note_parts = [f"annotator 1: {row_a['notes'].strip()}" if row_a["notes"].strip() else ""]
        note_parts.append(f"annotator 2: {row_b['notes'].strip()}" if row_b["notes"].strip() else "")
        row["notes"] = " | ".join(part for part in note_parts if part)
        if _is_disagreement(row):
            row["review_status"] = "needs_adjudication"
            row["adjudicated_intent"] = ""
            row["adjudicated_mixed_sources"] = ""
            disagreements += 1
        else:
            row["review_status"] = "adjudicated"
            row["adjudicated_intent"] = row["annotator_1_intent"].strip()
            row["adjudicated_mixed_sources"] = row["annotator_1_mixed_sources"].strip().lower()
        row["freeze_batch"] = ""
        merged.append(row)
    _write_csv(output_path, merged)
    return {"rows": len(merged), "disagreements": disagreements, "consensus": len(merged) - disagreements}


def adjudicate(input_path: Path, output_path: Path, adjudicator: str, input_fn=input) -> int:
    if not adjudicator.strip():
        raise EvaluationDataError("adjudicator identifier is required")
    rows = load_rows(input_path)
    issues = source_issues(rows)
    if issues:
        raise EvaluationDataError("worksheet invalid: " + "; ".join(issues[:5]))
    completed = 0
    for row in rows:
        if row["review_status"].strip() != "needs_adjudication":
            continue
        print(f"\n{row['case_id']} | attachment={row['has_attachment']}\n{row['message']}")
        print(f"Annotator 1: {row['annotator_1_intent']} / mixed={row['annotator_1_mixed_sources']}")
        print(f"Annotator 2: {row['annotator_2_intent']} / mixed={row['annotator_2_mixed_sources']}")
        row["adjudicated_intent"] = _prompt_intent("Final adjudicated intent: ", input_fn)
        row["adjudicated_mixed_sources"] = _prompt_bool("Final mixed_sources [true/false]: ", input_fn)
        reason = input_fn("Disagreement reason: ").strip()
        if not reason:
            raise EvaluationDataError("disagreement reason is required")
        row["disagreement_reason"] = reason
        row["adjudicator"] = adjudicator.strip()
        row["review_status"] = "adjudicated"
        completed += 1
    _write_csv(output_path, rows)
    return completed


def freeze(input_path: Path, output_path: Path, manifest_path: Path, batch: str) -> dict[str, Any]:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", batch):
        raise EvaluationDataError("batch must be 1-64 safe ASCII letters, digits, dot, underscore, or hyphen")
    if output_path.resolve() == manifest_path.resolve():
        raise EvaluationDataError("frozen CSV and manifest paths must be different")
    if output_path.parent.resolve() != manifest_path.parent.resolve():
        raise EvaluationDataError("frozen CSV and manifest must be stored in the same directory")
    if output_path.exists() or manifest_path.exists():
        raise EvaluationDataError("refusing to overwrite an existing frozen artifact or manifest")
    rows = load_rows(input_path)
    issues = source_issues(rows, require_complete=True)
    if issues:
        raise EvaluationDataError("refusing to freeze incomplete/invalid worksheet: " + "; ".join(issues[:8]))
    frozen = [dict(row, freeze_batch=batch) for row in rows]
    _write_csv(output_path, frozen)
    digest = hashlib.sha256(output_path.read_bytes()).hexdigest()
    manifest = {
        "schema": "deutschpath-router-independent-freeze-v1",
        "freeze_batch": batch,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "artifact": output_path.name,
        "sha256": digest,
        "merged_input_sha256": hashlib.sha256(input_path.read_bytes()).hexdigest(),
        "row_count": len(frozen),
        "intent_counts": dict(Counter(row["adjudicated_intent"] for row in frozen)),
        "mixed_sources_count": sum(row["adjudicated_mixed_sources"].strip().lower() == "true" for row in frozen),
        "annotation_policy": "Two independent human annotations; disagreements manually adjudicated; no router predictions included.",
    }
    _write_json(manifest_path, manifest)
    return manifest


def verify_frozen(manifest_path: Path) -> tuple[Path, dict[str, Any], list[dict[str, str]]]:
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        artifact_name = manifest["artifact"]
        if not isinstance(artifact_name, str) or Path(artifact_name).name != artifact_name:
            raise EvaluationDataError("manifest artifact must be a filename beside the manifest")
        frozen_path = manifest_path.parent / artifact_name
        digest = hashlib.sha256(frozen_path.read_bytes()).hexdigest()
    except EvaluationDataError:
        raise
    except (OSError, KeyError, json.JSONDecodeError, TypeError) as exc:
        raise EvaluationDataError(f"invalid freeze manifest or missing artifact: {exc}") from exc
    if manifest.get("schema") != "deutschpath-router-independent-freeze-v1" or digest != manifest.get("sha256"):
        raise EvaluationDataError("freeze manifest SHA-256 mismatch or unknown schema")
    rows = load_rows(frozen_path)
    if len(rows) != manifest.get("row_count") or any(row["freeze_batch"] != manifest.get("freeze_batch") for row in rows):
        raise EvaluationDataError("frozen artifact row count or batch does not match its manifest")
    issues = source_issues([dict(row, freeze_batch="") for row in rows], require_complete=True)
    if issues:
        raise EvaluationDataError("frozen artifact invalid: " + "; ".join(issues[:8]))
    return frozen_path, manifest, rows


def evaluate_frozen(manifest_path: Path, router_name: str) -> dict[str, Any]:
    frozen_path, manifest, rows = verify_frozen(manifest_path)
    if router_name == "rules":
        router = RuleBasedIntentRouter()
    else:
        from app.llm import build_llm
        from app.llm.client import DeepSeekLLM
        from app.routing import HybridIntentRouter, LLMIntentRouter

        llm = build_llm()
        if not isinstance(llm, DeepSeekLLM):
            raise EvaluationDataError("hybrid evaluation requires a configured real DeepSeek provider; FakeLLM is refused")
        router = HybridIntentRouter(RuleBasedIntentRouter(), LLMIntentRouter(llm))
    cases = [
        IntentCase(
            message=row["message"], expected=Intent(row["adjudicated_intent"]),
            has_attachment=row["has_attachment"].strip().lower() == "true",
            expected_mixed_sources=row["adjudicated_mixed_sources"].strip().lower() == "true",
        )
        for row in rows
    ]
    # evaluate() and mixed-source reporting both inspect each decision; cache
    # decisions so Hybrid mode makes one provider call per case, not two.
    class CachedRouter:
        def __init__(self, wrapped):
            self.wrapped = wrapped
            self.decisions = {}

        def route(self, message, context):
            key = (message, context.has_attachment)
            if key not in self.decisions:
                self.decisions[key] = self.wrapped.route(message, context)
            return self.decisions[key]

    router = CachedRouter(router)
    report = evaluate(router, cases)
    mixed = {"tp": 0, "fp": 0, "tn": 0, "fn": 0}
    for case in cases:
        decision = router.route(case.message, RoutingContext(has_attachment=case.has_attachment))
        expected, actual = case.expected_mixed_sources, decision.mixed_sources
        mixed[{(True, True): "tp", (False, True): "fp", (False, False): "tn", (True, False): "fn"}[(expected, actual)]] += 1
    precision = mixed["tp"] / (mixed["tp"] + mixed["fp"]) if mixed["tp"] + mixed["fp"] else 0.0
    recall = mixed["tp"] / (mixed["tp"] + mixed["fn"]) if mixed["tp"] + mixed["fn"] else 0.0
    report.update({
        "freeze_batch": manifest["freeze_batch"], "dataset_sha256": manifest["sha256"],
        "router": router_name, "mixed_sources": {
            **mixed, "precision": precision, "recall": recall,
            "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
            "accuracy": (mixed["tp"] + mixed["tn"]) / len(cases),
        },
        "independent_acceptance": report["accuracy"] >= 0.98,
    })
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    audit_parser = sub.add_parser("audit")
    audit_parser.add_argument("--input", type=Path, default=SOURCE)
    prepare_parser = sub.add_parser("prepare")
    prepare_parser.add_argument("--input", type=Path, default=SOURCE)
    prepare_parser.add_argument("--annotator", type=int, choices=(1, 2), required=True)
    prepare_parser.add_argument("--output", type=Path, required=True)
    annotate_parser = sub.add_parser("annotate")
    annotate_parser.add_argument("--input", type=Path, required=True)
    annotate_parser.add_argument("--annotator", type=int, choices=(1, 2), required=True)
    merge_parser = sub.add_parser("merge")
    merge_parser.add_argument("--annotator-1", type=Path, required=True)
    merge_parser.add_argument("--annotator-2", type=Path, required=True)
    merge_parser.add_argument("--output", type=Path, required=True)
    adjudicate_parser = sub.add_parser("adjudicate")
    adjudicate_parser.add_argument("--input", type=Path, required=True)
    adjudicate_parser.add_argument("--output", type=Path, required=True)
    adjudicate_parser.add_argument("--adjudicator", required=True)
    freeze_parser = sub.add_parser("freeze")
    freeze_parser.add_argument("--input", type=Path, required=True)
    freeze_parser.add_argument("--output", type=Path, required=True)
    freeze_parser.add_argument("--manifest", type=Path, required=True)
    freeze_parser.add_argument("--batch", required=True)
    eval_parser = sub.add_parser("evaluate")
    eval_parser.add_argument("--manifest", type=Path, required=True)
    eval_parser.add_argument("--router", choices=("rules", "hybrid"), required=True)
    eval_parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "audit":
            report = audit(args.input)
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 0 if report["structural_valid"] else 2
        if args.command == "prepare":
            prepare(args.input, args.output, args.annotator)
        elif args.command == "annotate":
            print(json.dumps({"annotated_rows": annotate(args.input, args.annotator)}, ensure_ascii=False))
        elif args.command == "merge":
            print(json.dumps(merge(args.annotator_1, args.annotator_2, args.output), ensure_ascii=False))
        elif args.command == "adjudicate":
            print(json.dumps({"adjudicated_rows": adjudicate(args.input, args.output, args.adjudicator)}, ensure_ascii=False))
        elif args.command == "freeze":
            print(json.dumps(freeze(args.input, args.output, args.manifest, args.batch), ensure_ascii=False, indent=2))
        elif args.command == "evaluate":
            if args.output and args.output.exists():
                raise EvaluationDataError(f"refusing to overwrite existing file: {args.output}")
            result = evaluate_frozen(args.manifest, args.router)
            if args.output:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except EvaluationDataError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

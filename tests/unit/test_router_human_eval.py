import csv
import hashlib
from pathlib import Path

import pytest

from scripts.router_human_eval import (
    EXPECTED_COLUMNS,
    EvaluationDataError,
    adjudicate,
    annotate,
    audit,
    evaluate_frozen,
    freeze,
    load_rows,
    main,
    merge,
    prepare,
    source_issues,
    verify_frozen,
)


SOURCE = Path(__file__).resolve().parents[2] / "evals" / "v011_human_annotation_worksheet.csv"


def write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=EXPECTED_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def independent_copies(tmp_path: Path, *, disagreement: bool = False):
    prepared_1, prepared_2 = tmp_path / "annotator-1.csv", tmp_path / "annotator-2.csv"
    prepare(SOURCE, prepared_1, 1)
    prepare(SOURCE, prepared_2, 2)
    rows_1, rows_2 = load_rows(prepared_1), load_rows(prepared_2)
    for row in rows_1:
        row["annotator_1_intent"] = "rag"
        row["annotator_1_mixed_sources"] = "false"
    for row in rows_2:
        row["annotator_2_intent"] = "web_search" if disagreement and row["case_id"] == "B3-001" else "rag"
        row["annotator_2_mixed_sources"] = "false"
    write_rows(prepared_1, rows_1)
    write_rows(prepared_2, rows_2)
    return prepared_1, prepared_2


def test_audit_recognizes_original_unreviewed_150_case_worksheet():
    report = audit(SOURCE)
    assert report["structural_valid"] is True
    assert report["columns"] == 14
    assert report["row_count"] == report["unique_case_ids"] == 150
    assert report["status_counts"] == {"unreviewed": 150}
    assert report["missing_adjudication_count"] == 150


def test_validation_rejects_duplicate_ids_invalid_labels_and_missing_adjudication():
    rows = load_rows(SOURCE)
    rows[1]["case_id"] = rows[0]["case_id"]
    rows[0]["annotator_1_intent"] = "predicted"
    rows[0]["review_status"] = "complete"
    issues = source_issues(rows, require_complete=True)
    assert any("not unique" in item for item in issues)
    assert any("illegal annotator_1_intent" in item for item in issues)
    assert any("not adjudicated" in item for item in issues)


def test_prepare_creates_separate_blank_annotation_copy_without_predictions(tmp_path: Path):
    output = tmp_path / "blind-copy.csv"
    prepare(SOURCE, output, 1)
    rows = load_rows(output)
    assert len(rows) == 150
    assert all(not row[key] for row in rows for key in (
        "annotator_1_intent", "annotator_2_intent", "adjudicated_intent", "freeze_batch"
    ))
    assert "prediction" not in output.read_text(encoding="utf-8-sig").lower()
    with pytest.raises(EvaluationDataError, match="overwrite"):
        prepare(SOURCE, output, 1)


def test_interactive_annotator_sees_only_prompts_and_can_add_private_notes(tmp_path: Path, capsys):
    output = tmp_path / "review.csv"
    prepare(SOURCE, output, 1)
    capsys.readouterr()
    answers = iter([value for _ in range(150) for value in ("no_tool", "false", "unclear wording")])
    assert annotate(output, 1, input_fn=lambda _prompt: next(answers)) == 150
    displayed = capsys.readouterr().out
    assert "B3-001" in displayed and "subordinate-clause" in displayed
    assert "prediction" not in displayed.lower() and "router output" not in displayed.lower()
    assert load_rows(output)[0]["notes"] == "unclear wording"


def test_merge_keeps_consensus_and_marks_disagreement_for_human_review(tmp_path: Path):
    first, second = independent_copies(tmp_path, disagreement=True)
    output = tmp_path / "merged.csv"
    summary = merge(first, second, output)
    rows = load_rows(output)
    assert summary == {"rows": 150, "disagreements": 1, "consensus": 149}
    assert rows[0]["review_status"] == "needs_adjudication"
    assert rows[0]["adjudicated_intent"] == ""
    assert rows[1]["review_status"] == "adjudicated"
    assert rows[1]["adjudicated_intent"] == "rag"


def test_adjudication_requires_manual_reason_and_records_reviewer(tmp_path: Path):
    first, second = independent_copies(tmp_path, disagreement=True)
    merged = tmp_path / "merged.csv"
    merge(first, second, merged)
    output = tmp_path / "adjudicated.csv"
    answers = iter(("rag", "false", "reviewed original wording"))
    assert adjudicate(merged, output, "human-3", input_fn=lambda _prompt: next(answers)) == 1
    row = load_rows(output)[0]
    assert row["review_status"] == "adjudicated"
    assert row["adjudicator"] == "human-3"
    assert row["disagreement_reason"] == "reviewed original wording"


def test_freeze_rejects_missing_adjudication_then_records_sha256_and_metrics(tmp_path: Path):
    first, second = independent_copies(tmp_path, disagreement=True)
    merged = tmp_path / "merged.csv"
    merge(first, second, merged)
    with pytest.raises(EvaluationDataError, match="incomplete/invalid worksheet"):
        freeze(merged, tmp_path / "frozen.csv", tmp_path / "freeze.json", "trial-1")

    rows = load_rows(merged)
    rows[0]["adjudicated_intent"] = "rag"
    rows[0]["adjudicated_mixed_sources"] = "false"
    rows[0]["disagreement_reason"] = "manual test fixture adjudication"
    rows[0]["adjudicator"] = "test-reviewer"
    rows[0]["review_status"] = "adjudicated"
    write_rows(merged, rows)
    frozen_path, manifest_path = tmp_path / "frozen.csv", tmp_path / "freeze.json"
    manifest = freeze(merged, frozen_path, manifest_path, "trial-1")
    assert manifest["sha256"] == hashlib.sha256(frozen_path.read_bytes()).hexdigest()
    assert verify_frozen(manifest_path)[2][0]["freeze_batch"] == "trial-1"
    result = evaluate_frozen(manifest_path, "rules")
    assert result["total"] == 150
    assert "macro_f1" in result and "confusion_matrix" in result and "mixed_sources" in result


def test_frozen_evaluation_rejects_hash_tampering(tmp_path: Path):
    first, second = independent_copies(tmp_path)
    merged, frozen = tmp_path / "merged.csv", tmp_path / "frozen.csv"
    merge(first, second, merged)
    freeze(merged, frozen, tmp_path / "freeze.json", "trial-2")
    frozen.write_bytes(frozen.read_bytes() + b" ")
    with pytest.raises(EvaluationDataError, match="SHA-256 mismatch"):
        verify_frozen(tmp_path / "freeze.json")


def test_evaluate_refuses_existing_output_before_any_router_call(tmp_path: Path, monkeypatch):
    from scripts import router_human_eval

    output = tmp_path / "existing-report.json"
    output.write_text("preserve", encoding="utf-8")
    monkeypatch.setattr(router_human_eval, "evaluate_frozen", lambda *_args: pytest.fail("must not invoke evaluator"))
    result = main(["evaluate", "--manifest", str(tmp_path / "ignored.json"), "--router", "hybrid", "--output", str(output)])
    assert result == 2
    assert output.read_text(encoding="utf-8") == "preserve"

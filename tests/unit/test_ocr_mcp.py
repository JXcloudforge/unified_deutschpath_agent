from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path

import pytest
from PIL import Image

from app.mcp.servers.ocr.engine import ENGINE_NAME, ENGINE_VERSION, extract_text
from app.mcp.servers.ocr import security
from app.mcp.servers.ocr.security import ImageInputError, load_authorized_image
from app.mcp.servers.ocr import server as ocr_server


FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "ocr"


@pytest.mark.parametrize(
    ("filename", "language", "expected"),
    [
        ("english.png", "en", "Good morning"),
        ("german.png", "de", "Fünf große Wörter: Straße über München."),
    ],
)
def test_real_rapidocr_text_and_confidence(filename, language, expected):
    with Image.open(FIXTURES / filename) as image:
        result = extract_text(image.convert("RGB"), language)
    assert result["success"] is True
    assert result["engine"] == ENGINE_NAME == "RapidOCR"
    assert result["engine_version"] == ENGINE_VERSION
    assert result["language"] == language
    assert expected in result["raw_text"]
    assert result["lines"]
    assert all(0 <= line["confidence"] <= 1 for line in result["lines"])
    assert all("bbox" in line and line["words"] for line in result["lines"])


def test_real_table_returns_candidate_rows_with_engine_confidences():
    with Image.open(FIXTURES / "vocabulary_table.png") as image:
        result = extract_text(image.convert("RGB"), "en")
    assert result["success"] is True
    assert len(result["tables"]) == 1
    rows = result["tables"][0]["rows"]
    assert len(rows) == 4
    assert [cell["text"] for cell in rows[0]] == ["Word", "Meaning", "Level"]
    assert [cell["text"] for cell in rows[-1]] == ["verstehen", "understand", "A2"]
    assert "table_cells_are_layout_candidates_and_require_human_review" in result["warnings"]
    assert all("confidence" in cell and "bbox" in cell for row in rows for cell in row)


def test_blank_image_reports_no_text_without_fabricating_output():
    result = extract_text(Image.new("RGB", (600, 300), "white"), "en")
    assert result["success"] is False
    assert result["status"] == "no_text_detected"
    assert result["raw_text"] == ""
    assert result["tables"] == []
    assert "no_text_detected" in result["warnings"]


def test_input_security_content_size_and_path_policy(tmp_path):
    valid = tmp_path / "approved.png"
    with Image.new("RGB", (10, 10), "white") as image:
        image.save(valid)
    image, kind, size, raw = load_authorized_image(tmp_path, "approved")
    assert image.size == (10, 10) and kind == "PNG" and size > 0
    assert len(raw) == size
    with pytest.raises(ImageInputError, match="image_id"):
        load_authorized_image(tmp_path, "../secret")
    with pytest.raises(ImageInputError, match="missing or ambiguous"):
        load_authorized_image(tmp_path, "not-present")


def test_rejects_corrupt_image_and_mismatched_extension(tmp_path):
    (tmp_path / "broken.png").write_bytes(b"not an image")
    with pytest.raises(ImageInputError, match="corrupt"):
        load_authorized_image(tmp_path, "broken")
    (tmp_path / "wrong.jpg").write_bytes((FIXTURES / "english.png").read_bytes())
    with pytest.raises(ImageInputError, match="does not match"):
        load_authorized_image(tmp_path, "wrong")


def test_rejects_image_byte_and_pixel_limits(tmp_path, monkeypatch):
    path = tmp_path / "large.png"
    with Image.new("RGB", (10, 10), "white") as image:
        image.save(path)
    monkeypatch.setattr(security, "MAX_IMAGE_BYTES", 10)
    with pytest.raises(ImageInputError, match="10 MiB size limit"):
        load_authorized_image(tmp_path, "large")
    monkeypatch.setattr(security, "MAX_IMAGE_BYTES", 10 * 1024 * 1024)
    monkeypatch.setattr(security, "MAX_IMAGE_PIXELS", 99)
    with pytest.raises(ImageInputError, match="20-megapixel limit"):
        load_authorized_image(tmp_path, "large")


def test_rejects_symlink_when_supported(tmp_path):
    outside = tmp_path.parent / f"{tmp_path.name}-outside.png"
    with Image.new("RGB", (10, 10), "white") as image:
        image.save(outside)
    link = tmp_path / "linked.png"
    try:
        link.symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation is unavailable in this Windows account")
    with pytest.raises(ImageInputError, match="symlink or reparse"):
        load_authorized_image(tmp_path, "linked")


def test_rejects_reparse_point_policy(tmp_path, monkeypatch):
    image_path = tmp_path / "linked.png"
    with Image.new("RGB", (10, 10), "white") as image:
        image.save(image_path)
    original = security._is_reparse_or_link
    monkeypatch.setattr(
        security,
        "_is_reparse_or_link",
        lambda path: Path(path).name == "linked.png" or original(Path(path)),
    )
    with pytest.raises(ImageInputError, match="symlink or reparse"):
        load_authorized_image(tmp_path, "linked")


def test_ocr_timeout_is_reported_and_does_not_fake_success(monkeypatch):
    async def slow_thread(*_args):
        await asyncio.sleep(0.1)

    monkeypatch.setattr(ocr_server.asyncio, "to_thread", slow_thread)

    async def exercise():
        with pytest.raises(TimeoutError):
            await ocr_server._run_worker_with_timeout(b"test", "en", 0.001)

    asyncio.run(exercise())


def test_worker_process_timeout_is_converted_to_controlled_error(monkeypatch):
    def timed_out(*_args, **_kwargs):
        raise subprocess.TimeoutExpired("ocr worker", timeout=28)

    monkeypatch.setattr(ocr_server.subprocess, "run", timed_out)
    with pytest.raises(ocr_server.OCRWorkerTimeout):
        ocr_server._run_worker(b"pixels", "en")

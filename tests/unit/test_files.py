from pathlib import Path

import pytest
from docx import Document

from app.files.registry import UnsupportedFileTypeError
from app.files.service import EmptyFileError, FileService
from app.files.parsers.pdf_parser import PdfParser


def test_txt_and_markdown_parse(tmp_path: Path):
    (tmp_path / "lesson.txt").write_text("Hallo", encoding="utf-8")
    (tmp_path / "lesson.md").write_text("# Hallo", encoding="utf-8")
    service = FileService()
    assert service.parse(tmp_path / "lesson.txt").file_type == "txt"
    assert service.parse(tmp_path / "lesson.md").text == "# Hallo"


def test_docx_parse(tmp_path: Path):
    path = tmp_path / "lesson.docx"
    document = Document(); document.add_paragraph("Deutsch lernen"); document.save(path)
    parsed = FileService().parse(path)
    assert parsed.file_type == "docx"
    assert "Deutsch lernen" in parsed.text


def test_pdf_parser_extracts_text(monkeypatch, tmp_path: Path):
    path = tmp_path / "lesson.pdf"; path.write_bytes(b"%PDF-demo")
    class Page:
        def extract_text(self): return "PDF German content"
    class Reader:
        pages = [Page()]
    monkeypatch.setattr("app.files.parsers.pdf_parser.PdfReader", lambda _: Reader())
    assert PdfParser().parse(path).text == "PDF German content"


def test_rejects_unsupported_and_empty_files(tmp_path: Path):
    service = FileService()
    (tmp_path / "notes.csv").write_text("a,b", encoding="utf-8")
    (tmp_path / "blank.txt").write_text("", encoding="utf-8")
    with pytest.raises(UnsupportedFileTypeError): service.parse(tmp_path / "notes.csv")
    with pytest.raises(EmptyFileError): service.parse(tmp_path / "blank.txt")

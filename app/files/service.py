from pathlib import Path

from app.schemas import ParsedDocument
from .registry import ParserRegistry
from .parsers import DocxParser, MarkdownParser, PdfParser, TextParser


class EmptyFileError(ValueError):
    pass


class FileService:
    """Single file parsing boundary; callers never import parser libraries."""

    def __init__(self, registry: ParserRegistry | None = None) -> None:
        self.registry = registry or ParserRegistry([TextParser(), MarkdownParser(), PdfParser(), DocxParser()])

    def parse(self, path: str | Path) -> ParsedDocument:
        file_path = Path(path)
        if not file_path.is_file():
            raise FileNotFoundError(file_path)
        document = self.registry.parser_for(file_path).parse(file_path)
        if not document.text.strip():
            raise EmptyFileError(f"File contains no extractable text: {document.filename}")
        return document

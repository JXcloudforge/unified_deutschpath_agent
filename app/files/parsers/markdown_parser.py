from pathlib import Path

from app.schemas import ParsedDocument


class MarkdownParser:
    extensions = (".md", ".markdown")

    def parse(self, path: Path) -> ParsedDocument:
        return ParsedDocument(path.name, "markdown", path.read_text(encoding="utf-8-sig"), {"source": str(path)})

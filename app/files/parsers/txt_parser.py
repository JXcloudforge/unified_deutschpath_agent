from pathlib import Path

from app.schemas import ParsedDocument


class TextParser:
    extensions = (".txt",)

    def parse(self, path: Path) -> ParsedDocument:
        return ParsedDocument(path.name, "txt", path.read_text(encoding="utf-8-sig"), {"source": str(path)})

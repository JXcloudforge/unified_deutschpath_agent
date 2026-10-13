from pathlib import Path

from pypdf import PdfReader

from app.schemas import ParsedDocument


class PdfParser:
    extensions = (".pdf",)

    def parse(self, path: Path) -> ParsedDocument:
        reader = PdfReader(str(path))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        return ParsedDocument(path.name, "pdf", text, {"source": str(path), "pages": len(reader.pages)})

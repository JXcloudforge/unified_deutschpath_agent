"""Stage 2 file parser and direct-prompt-context acceptance demo."""
from tempfile import TemporaryDirectory
import sys
from pathlib import Path

# Make this explicit demo runnable as `python scripts\\demo_file_parser.py` before editable install.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

from docx import Document

from app.files import FileService
from app.rag.context_builder import ContextBuilder

def _write_demo_pdf(path: Path) -> None:
    """Generate a tiny text PDF locally so this demo has no old-project dependency."""
    stream = b"BT /F1 12 Tf 72 720 Td (Ausbildung PDF document.) Tj ET"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    body = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, item in enumerate(objects, 1):
        offsets.append(len(body)); body.extend(f"{number} 0 obj\n".encode()); body.extend(item); body.extend(b"\nendobj\n")
    xref = len(body); body.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    body.extend(b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets[1:]))
    body.extend(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    path.write_bytes(bytes(body))


with TemporaryDirectory() as temporary:
    folder = Path(temporary)
    (folder / "lesson.txt").write_text("Dativ follows mit in this lesson.", encoding="utf-8")
    (folder / "lesson.md").write_text("# Ausbildung\nGerman vocational training.", encoding="utf-8")
    word = Document(); word.add_paragraph("Dies ist ein Word-Dokument über deutsche Grammatik."); word.save(folder / "lesson.docx")
    _write_demo_pdf(folder / "lesson.pdf")
    paths = [folder / "lesson.txt", folder / "lesson.md", folder / "lesson.docx", folder / "lesson.pdf"]
    service, context = FileService(), ContextBuilder()
    print("=== Stage 2 File Parser Demo ===")
    for path in paths:
        document = service.parse(path)
        prompt_context = context.direct_attachment(document)
        print(f"\nfilename: {document.filename}\nfile type: {document.file_type}\ncharacter count: {len(document.text)}\ntext preview: {document.text[:100]}\nprompt preview: {prompt_context[:160]}")

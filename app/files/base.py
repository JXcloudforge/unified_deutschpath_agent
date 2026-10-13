from pathlib import Path
from typing import Protocol

from app.schemas import ParsedDocument


class FileParser(Protocol):
    extensions: tuple[str, ...]

    def parse(self, path: Path) -> ParsedDocument: ...

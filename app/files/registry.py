from pathlib import Path

from .base import FileParser


class UnsupportedFileTypeError(ValueError):
    pass


class ParserRegistry:
    def __init__(self, parsers: list[FileParser]) -> None:
        self._by_extension = {extension: parser for parser in parsers for extension in parser.extensions}

    def parser_for(self, path: str | Path) -> FileParser:
        parser = self._by_extension.get(Path(path).suffix.lower())
        if parser is None:
            raise UnsupportedFileTypeError("Supported file types are TXT, MD, PDF, and DOCX")
        return parser

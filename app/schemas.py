from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ParsedDocument:
    filename: str
    file_type: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Chunk:
    id: str
    text: str
    metadata: dict[str, Any]


@dataclass(frozen=True)
class SearchResult:
    chunk_id: str
    text: str
    score: float
    metadata: dict[str, Any]


@dataclass(frozen=True)
class ContextBundle:
    knowledge_context: str = ""
    attachment_context: str = ""
    chat_history: str = ""
    user_context: str = ""
    tool_context: str = ""

    def render(self) -> str:
        sections = [
            ("Knowledge context", self.knowledge_context),
            ("Attachment context", self.attachment_context),
            ("Chat history", self.chat_history),
            ("User state", self.user_context),
            ("Tool results", self.tool_context),
        ]
        return "\n\n".join(f"## {title}\n{value}" for title, value in sections if value.strip())

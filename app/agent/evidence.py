from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum

from app.schemas import ParsedDocument, SearchResult
from app.web.models import WebSearchResult


class EvidenceSource(str, Enum):
    LOCAL_FILE = "local_file"
    KNOWLEDGE = "knowledge"
    WEB = "web"


@dataclass(frozen=True)
class Evidence:
    source: EvidenceSource
    content: str
    label: str
    document_id: str | None = None
    url: str | None = None
    published_date: str | None = None
    retrieved_at: str | None = None


@dataclass(frozen=True)
class EvidenceBundle:
    items: tuple[Evidence, ...]
    truncated: bool = False

    @property
    def local_items(self) -> tuple[Evidence, ...]:
        return tuple(item for item in self.items if item.source is not EvidenceSource.WEB)

    @property
    def web_items(self) -> tuple[Evidence, ...]:
        return tuple(item for item in self.items if item.source is EvidenceSource.WEB)

    def render(self) -> str:
        """Render evidence as data only; orchestration supplies the execution instructions separately."""
        sections: list[str] = []
        for index, item in enumerate(self.items, 1):
            header = f"[Evidence {index} | source={item.source.value} | label={item.label}"
            if item.document_id:
                header += f" | document_id={item.document_id}"
            if item.url:
                header += f" | url={item.url}"
            if item.published_date:
                header += f" | published_date={item.published_date}"
            if item.retrieved_at:
                header += f" | retrieved_at={item.retrieved_at}"
            sections.append(f"{header}]\n{item.content}")
        return "\n\n".join(sections)

    def citations(self) -> str:
        lines: list[str] = []
        if self.local_items:
            lines.append("Local sources:")
            lines.extend(
                f"- {item.label}" + (f" (id: {item.document_id})" if item.document_id and item.document_id != item.label else "")
                for item in self.local_items
            )
        if self.web_items:
            lines.append("Web sources:")
            lines.extend(f"- {item.url}" for item in self.web_items if item.url)
        return "\n".join(lines)


class EvidenceAggregator:
    """Bounded, source-labelled evidence aggregation with exact-text deduplication."""

    def __init__(self, *, max_items: int = 12, max_characters: int = 9000, max_item_characters: int = 1800) -> None:
        self.max_items = max_items
        self.max_characters = max_characters
        self.max_item_characters = max_item_characters

    def direct_attachment(self, document: ParsedDocument) -> Evidence:
        document_id = str(document.metadata.get("document_id") or document.metadata.get("id") or document.filename)
        return Evidence(EvidenceSource.LOCAL_FILE, document.text, document.filename, document_id=document_id)

    def local_results(self, results: list[SearchResult], *, source: EvidenceSource = EvidenceSource.LOCAL_FILE) -> list[Evidence]:
        return [
            Evidence(source, result.text, str(result.metadata.get("filename", "unknown")), document_id=result.chunk_id)
            for result in results
        ]

    def web_results(self, results: tuple[WebSearchResult, ...]) -> list[Evidence]:
        retrieved_at = datetime.now(UTC).isoformat()
        return [
            Evidence(EvidenceSource.WEB, result.snippet, result.title, url=result.url,
                     published_date=result.published_date, retrieved_at=retrieved_at)
            for result in results
        ]

    def aggregate(self, *groups: list[Evidence]) -> EvidenceBundle:
        items: list[Evidence] = []
        seen: set[tuple[EvidenceSource, str]] = set()
        remaining = self.max_characters
        truncated = False
        for evidence in (item for group in groups for item in group):
            normalized = " ".join(evidence.content.split()).casefold()
            if not normalized or (evidence.source, normalized) in seen:
                continue
            if len(items) >= self.max_items or remaining <= 0:
                truncated = True
                break
            seen.add((evidence.source, normalized))
            limit = min(self.max_item_characters, remaining)
            content = evidence.content[:limit]
            if len(content) < len(evidence.content):
                truncated = True
            items.append(Evidence(evidence.source, content, evidence.label, evidence.document_id,
                                  evidence.url, evidence.published_date, evidence.retrieved_at))
            remaining -= len(content)
        return EvidenceBundle(tuple(items), truncated)

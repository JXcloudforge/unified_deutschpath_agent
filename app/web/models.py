from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class WebSearchTopic(str, Enum):
    GENERAL = "general"
    NEWS = "news"


@dataclass(frozen=True)
class WebSearchResult:
    title: str
    url: str
    snippet: str
    published_date: str | None = None


@dataclass(frozen=True)
class WebSearchResponse:
    query: str
    results: tuple[WebSearchResult, ...]

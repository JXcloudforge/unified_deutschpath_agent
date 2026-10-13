from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Intent(str, Enum):
    RAG = "rag"
    WEB_SEARCH = "web_search"
    NO_TOOL = "no_tool"


@dataclass(frozen=True)
class RoutingContext:
    """Request facts available before dispatch; it deliberately has no infrastructure handles."""

    has_attachment: bool = False
    has_session: bool = False


@dataclass(frozen=True)
class RouteDecision:
    intent: Intent
    confidence: float
    reason: str
    query: str | None = None
    mixed_sources: bool = False

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")

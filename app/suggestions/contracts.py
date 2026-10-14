"""Public immutable DTO and read-only query contract for M09."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Protocol

from app.chat.contracts import ActorContext


@dataclass(frozen=True, slots=True)
class FollowUpSuggestion:
    suggestion_id: str
    question: str
    category: str
    reason: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


class SuggestionQueries(Protocol):
    """Read-only API; implementations never persist or execute suggestions."""

    def get_follow_up_suggestions(
        self, actor: ActorContext, session_id: str, *, maximum: int = 3
    ) -> tuple[FollowUpSuggestion, ...]: ...

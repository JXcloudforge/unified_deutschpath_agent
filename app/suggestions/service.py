"""Bounded, deterministic recommendations based on public Conversation DTOs."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Protocol

from app.chat.contracts import ActorContext, ConversationQueries
from app.orchestration.contracts import OrchestrationQueries, OrchestrationStatus

from .contracts import FollowUpSuggestion

_SUPPRESSING_STATES = {
    OrchestrationStatus.NEEDS_CLARIFICATION,
    OrchestrationStatus.AWAITING_CONFIRMATION,
    OrchestrationStatus.EXECUTING,
    OrchestrationStatus.UNCERTAIN,
}
_TOPICS: tuple[tuple[str, tuple[str, ...], tuple[str, ...]], ...] = (
    (
        "ausbildung",
        ("ausbildung", "职业培训", "职业教育", "学徒", "岗位"),
        (
            "B1 和 B2 在 Ausbildung 学习与工作中的实际区别是什么？",
            "如何查询某个具体岗位当前公布的德语要求？",
            "申请 Ausbildung 前通常需要准备哪些材料？",
        ),
    ),
    (
        "language_level",
        ("德语水平", "语言水平", "b1", "b2", "语言要求", "sprachkenntnisse"),
        (
            "B1 和 B2 的德语能力差异体现在哪些实际场景？",
            "如何根据我的当前水平安排下一阶段的德语学习？",
            "哪些德语练习适合提升听说能力？",
        ),
    ),
    (
        "grammar",
        ("语法", "格", "冠词", "动词变位", "语序", "grammar", "grammatik"),
        (
            "能用一个日常德语例句说明这个语法规则吗？",
            "这个语法点有哪些常见错误需要避免？",
            "可以给我几道由易到难的练习题吗？",
        ),
    ),
    (
        "vocabulary",
        ("词汇", "单词", "短语", "表达", "vokabel", "wortschatz"),
        (
            "这些德语词汇在真实对话中怎样搭配使用？",
            "可以用这些词汇写一段简短的德语对话吗？",
            "如何区分这些近义词的使用场景？",
        ),
    ),
)


class SuggestionStrategy(Protocol):
    def suggest(self, question: str, answer: str, *, maximum: int) -> tuple[tuple[str, str], ...]: ...


@dataclass(frozen=True, slots=True)
class DeterministicSuggestionStrategy:
    """Offline rules for a small set of language-learning topics."""

    def suggest(self, question: str, answer: str, *, maximum: int = 3) -> tuple[tuple[str, str], ...]:
        if maximum <= 0 or not question.strip() or not answer.strip():
            return ()
        corpus = f"{question[:1200]} {answer[:2400]}".casefold()
        for category, markers, candidates in _TOPICS:
            if any(marker.casefold() in corpus for marker in markers):
                return tuple((item, category) for item in _deduplicate(candidates)[:maximum])
        return ()


class FollowUpSuggestionService:
    """M09 Query facade; data access remains behind Conversation and M08 Queries."""

    MAXIMUM = 3

    def __init__(
        self,
        conversations: ConversationQueries,
        orchestrations: OrchestrationQueries | None = None,
        strategy: SuggestionStrategy | None = None,
    ) -> None:
        self._conversations = conversations
        self._orchestrations = orchestrations
        self._strategy = strategy or DeterministicSuggestionStrategy()

    def get_follow_up_suggestions(
        self, actor: ActorContext, session_id: str, *, maximum: int = 3
    ) -> tuple[FollowUpSuggestion, ...]:
        limit = min(max(int(maximum), 0), self.MAXIMUM)
        if not limit:
            return ()
        snapshot = self._conversations.get_context_snapshot(actor, session_id)
        messages = snapshot.messages
        if not messages:
            return ()
        latest_assistant = next((item for item in reversed(messages) if item.role == "assistant"), None)
        if latest_assistant is None:
            return ()
        latest_user = next(
            (item for item in reversed(messages) if item.role == "user" and item.seq < latest_assistant.seq),
            None,
        )
        if latest_user is None:
            return ()
        if self._has_suppressing_orchestration(actor, session_id):
            return ()

        generated = self._strategy.suggest(latest_user.content[:1200], latest_assistant.content[:2400], maximum=limit)
        unique: list[FollowUpSuggestion] = []
        seen: set[str] = set()
        for question, category in generated:
            clean = question.strip()
            normalized = _normalize(clean)
            if not clean or normalized in seen or len(clean) > 180:
                continue
            seen.add(normalized)
            unique.append(FollowUpSuggestion(
                suggestion_id=f"m09-{len(unique) + 1}", question=clean,
                category=category, reason="基于当前问题与回答中的学习主题",
            ))
            if len(unique) >= limit:
                break
        return tuple(unique)

    def _has_suppressing_orchestration(self, actor: ActorContext, session_id: str) -> bool:
        if self._orchestrations is None:
            return False
        try:
            latest = self._orchestrations.get_latest_orchestration(actor, session_id)
        except KeyError:
            return False
        if latest is None:
            return False
        try:
            status = OrchestrationStatus(latest.status)
        except ValueError:
            return True
        return status in _SUPPRESSING_STATES


def _normalize(value: str) -> str:
    folded = unicodedata.normalize("NFKC", value).casefold()
    return re.sub(r"[\W_]+", "", folded, flags=re.UNICODE)


def _deduplicate(values: tuple[str, ...]) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        normalized = _normalize(value)
        if normalized not in seen:
            seen.add(normalized)
            result.append(value)
    return tuple(result)

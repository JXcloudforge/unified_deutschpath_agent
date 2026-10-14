"""Public Conversation commands, queries, and transport independent DTOs."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal, Protocol

from app.auth.contracts import ActorContext


MessageRole = Literal["user", "assistant"]


@dataclass(frozen=True, slots=True)
class ConversationSession:
    id: str
    user_id: str
    title: str
    created_at: str
    updated_at: str

    @classmethod
    def from_record(cls, record: dict) -> ConversationSession:
        return cls(**{name: str(record[name]) for name in cls.__dataclass_fields__})

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ConversationMessage:
    id: str
    session_id: str
    role: MessageRole
    content: str
    seq: int
    created_at: str

    @classmethod
    def from_record(cls, record: dict) -> ConversationMessage:
        return cls(
            id=str(record["id"]),
            session_id=str(record["session_id"]),
            role=record["role"],
            content=str(record["content"]),
            seq=int(record["seq"]),
            created_at=str(record["created_at"]),
        )

    def to_dict(self) -> dict[str, str | int]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ConversationContextSnapshot:
    session_id: str
    messages: tuple[ConversationMessage, ...]
    character_budget: int
    characters_used: int
    truncated: bool

    def to_llm_history(self) -> list[dict[str, str]]:
        return [{"role": item.role, "content": item.content} for item in self.messages]


@dataclass(frozen=True, slots=True)
class SendMessageResult:
    user_message: ConversationMessage
    assistant_message: ConversationMessage
    tool_operation: dict | None = None
    orchestration: dict | None = None

    def to_dict(self) -> dict:
        result = {
            "user_message": self.user_message.to_dict(),
            "assistant_message": self.assistant_message.to_dict(),
        }
        if self.tool_operation is not None:
            result["tool_operation"] = self.tool_operation
        if self.orchestration is not None:
            result["orchestration"] = self.orchestration
        return result


class ConversationCommands(Protocol):
    """State-changing Conversation operations; ChatService owns commits."""

    def create_session(self, actor: ActorContext) -> ConversationSession: ...

    def rename_session(self, actor: ActorContext, session_id: str, title: str) -> ConversationSession: ...

    def send_message(self, actor: ActorContext, session_id: str, content: str) -> SendMessageResult: ...

    def append_assistant_message(self, actor: ActorContext, session_id: str, content: str) -> ConversationMessage: ...

    def append_user_message(self, actor: ActorContext, session_id: str, content: str,
                            *, preserve_session_title: bool = False) -> ConversationMessage: ...

    def upload(self, actor: ActorContext, session_id: str, path: str | Path) -> dict: ...


class ConversationQueries(Protocol):
    """Read-only, user-scoped Conversation operations."""

    def get_session(self, actor: ActorContext, session_id: str) -> ConversationSession: ...

    def list_sessions(self, actor: ActorContext) -> list[ConversationSession]: ...

    def get_messages(self, actor: ActorContext, session_id: str) -> list[ConversationMessage]: ...

    def get_context_snapshot(self, actor: ActorContext, session_id: str) -> ConversationContextSnapshot: ...

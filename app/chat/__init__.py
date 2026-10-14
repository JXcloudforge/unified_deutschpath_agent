"""Conversation module public service contracts and immutable DTOs."""

from .contracts import (
    ActorContext,
    ConversationCommands,
    ConversationContextSnapshot,
    ConversationMessage,
    ConversationQueries,
    ConversationSession,
    SendMessageResult,
)
from .service import ChatService

__all__ = [
    "ActorContext",
    "ChatService",
    "ConversationCommands",
    "ConversationContextSnapshot",
    "ConversationMessage",
    "ConversationQueries",
    "ConversationSession",
    "SendMessageResult",
]

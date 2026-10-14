"""Bounded history context construction for Conversation snapshots."""

from __future__ import annotations

from dataclasses import replace

from .contracts import ConversationContextSnapshot, ConversationMessage


class ConversationContextBuilder:
    """Keep recent history under a predictable character budget.

    Character count is a deterministic guardrail, not an exact model-tokenizer
    estimate. The current user input and system safety instructions are sent
    separately and are never removed by this history builder.
    """

    def __init__(self, *, max_messages: int = 20, max_characters: int = 12_000) -> None:
        if max_messages < 1 or max_characters < 1:
            raise ValueError("history limits must be positive")
        self.max_messages = max_messages
        self.max_characters = max_characters

    def build(self, session_id: str, messages: list[ConversationMessage]) -> ConversationContextSnapshot:
        recent = messages[-self.max_messages :]
        truncated = len(recent) != len(messages)
        selected: list[ConversationMessage] = []
        used = 0
        for message in reversed(recent):
            available = self.max_characters - used
            if len(message.content) <= available:
                selected.append(message)
                used += len(message.content)
                continue

            truncated = True
            if not selected and available:
                marker = "[较早内容已省略]\n"
                if available <= len(marker):
                    content = message.content[-available:]
                else:
                    content = marker + message.content[-(available - len(marker)):]
                selected.append(replace(message, content=content))
                used += len(content)
            break

        selected.reverse()
        return ConversationContextSnapshot(
            session_id=session_id,
            messages=tuple(selected),
            character_budget=self.max_characters,
            characters_used=used,
            truncated=truncated,
        )

"""Small UI state helpers for choosing, but not automatically sending, prompts."""

from collections.abc import MutableMapping
from typing import Any


def queue_suggestion(state: MutableMapping[str, Any], question: str, session_id: str) -> None:
    """Prefill the chat widget and clear its cards; callers still submit explicitly."""
    state["chat_input"] = question
    suggestions = state.get("m09_suggestions", {})
    if isinstance(suggestions, dict):
        suggestions.pop(session_id, None)


def render_suggestion_buttons(st: Any, suggestions: list[dict[str, str]], session_id: str) -> None:
    """Render a small prompt chooser before chat_input so choices can prefill it."""
    if not suggestions:
        return
    with st.container(border=True):
        st.caption("你可以选择一个问题填入输入框，再自行决定是否发送。")
        for suggestion in suggestions[:3]:
            st.button(
                suggestion["question"],
                key=f"m09-{session_id}-{suggestion['suggestion_id']}",
                on_click=queue_suggestion,
                args=(st.session_state, suggestion["question"], session_id),
                use_container_width=True,
            )

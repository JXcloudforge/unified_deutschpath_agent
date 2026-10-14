from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from app.chat import ActorContext, ConversationMessage, ConversationSession
from app.chat.context import ConversationContextBuilder
from ui.api_client import ApiContractError, normalize_send_result


def message(seq: int, role: str, content: str) -> ConversationMessage:
    return ConversationMessage(
        id=f"message-{seq}", session_id="session-1", role=role,
        content=content, seq=seq, created_at="2026-10-13T00:00:00",
    )


def test_actor_context_marks_local_header_identity_and_rejects_blank_user():
    actor = ActorContext.from_local_header(" alice ")
    assert actor.user_id == "alice"
    assert actor.identity_source == "caller_supplied_x_user_id"
    with pytest.raises(ValueError, match="must not be blank"):
        ActorContext.from_local_header("  ")


def test_context_builder_keeps_newest_history_with_message_and_character_limits():
    builder = ConversationContextBuilder(max_messages=3, max_characters=12)
    snapshot = builder.build(
        "session-1",
        [message(1, "user", "old"), message(2, "assistant", "answer"), message(3, "user", "abcdefghijklmnop")],
    )
    assert [item.seq for item in snapshot.messages] == [3]
    assert snapshot.messages[-1].content.endswith("op")
    assert len(snapshot.messages[-1].content) == 12
    assert snapshot.characters_used == 12
    assert snapshot.truncated is True
    assert snapshot.to_llm_history() == [{"role": "user", "content": snapshot.messages[-1].content}]


def test_context_builder_caps_message_count_and_reports_character_budget():
    builder = ConversationContextBuilder(max_messages=2, max_characters=100)
    snapshot = builder.build("session-1", [message(1, "user", "a"), message(2, "assistant", "b"), message(3, "user", "c")])
    assert [item.seq for item in snapshot.messages] == [2, 3]
    assert snapshot.character_budget == 100
    assert snapshot.characters_used == 2
    assert snapshot.truncated is True


def test_public_session_dto_is_immutable_and_preserves_http_fields():
    session = ConversationSession("session-1", "alice", "Lesson", "created", "updated")
    assert session.to_dict() == {
        "id": "session-1", "user_id": "alice", "title": "Lesson",
        "created_at": "created", "updated_at": "updated",
    }
    with pytest.raises(FrozenInstanceError):
        session.title = "changed"


def test_send_response_preserves_m08_public_operation_dto():
    response = normalize_send_result({
        "user_message": {"role": "user", "content": "确认"},
        "assistant_message": {"role": "assistant", "content": "已完成"},
        "orchestration": {"status": "SUCCEEDED", "steps": []},
    })
    assert response["orchestration"]["status"] == "SUCCEEDED"
    with pytest.raises(ApiContractError, match="orchestration"):
        normalize_send_result({
            "user_message": {"role": "user", "content": "确认"},
            "assistant_message": {"role": "assistant", "content": "完成"},
            "orchestration": "not-an-object",
        })


def test_ui_and_api_do_not_import_or_access_chat_repository():
    root = Path(__file__).resolve().parents[2]
    api_source = (root / "app" / "api" / "main.py").read_text(encoding="utf-8")
    ui_source = "\n".join(path.read_text(encoding="utf-8") for path in (root / "ui").glob("*.py"))
    assert "ChatRepository" not in api_source
    assert "chat.repository" not in api_source
    assert "chat.orchestrator" not in api_source
    assert "ChatRepository" not in ui_source
    assert "sqlite3" not in ui_source

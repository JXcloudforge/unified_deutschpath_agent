from pathlib import Path

import pytest

from app.agent import UnifiedOrchestrator
from app.chat import ActorContext, ChatService
from app.chat.repository import ChatRepository
from app.files import FileService
from app.llm import FakeLLM
from app.rag import DeterministicEmbedding, RAGService
from app.rag.vector_store import ChromaVectorStore
from app.users import UserStateRepository, UserStateService


def test_chat_persists_user_then_assistant(tmp_path: Path):
    rag = RAGService(ChromaVectorStore(tmp_path / "chroma", DeterministicEmbedding()))
    service = ChatService(
        ChatRepository(tmp_path / "chat.db"),
        UnifiedOrchestrator(rag, UserStateService(UserStateRepository(tmp_path / "state.db")), FakeLLM("Hallo!")),
        FileService(),
    )
    actor = ActorContext.from_local_header("jing")
    session = service.create_session(actor)
    result = service.send_message(actor, session.id, "Hallo")
    assert result.assistant_message.content == "Hallo!"
    assert [item.role for item in service.get_messages(actor, session.id)] == ["user", "assistant"]


def test_session_list_preserves_history_and_user_isolation_after_reopen(tmp_path: Path):
    repository = ChatRepository(tmp_path / "chat.db")
    first = repository.create_session("alice")
    second = repository.create_session("alice")
    foreign = repository.create_session("bob")
    repository.add_message("alice", first["id"], "user", "First lesson")
    reopened = ChatRepository(tmp_path / "chat.db")
    sessions = reopened.list_sessions("alice")
    assert {item["id"] for item in sessions} == {first["id"], second["id"]}
    assert foreign["id"] not in {item["id"] for item in sessions}
    assert sessions == sorted(sessions, key=lambda row: (row["updated_at"], row["id"]), reverse=True)
    assert reopened.messages("alice", first["id"])[0]["content"] == "First lesson"
    assert reopened.list_sessions("missing") == []


def test_session_title_is_persistent_and_rename_is_user_scoped(tmp_path: Path):
    path = tmp_path / "chat.db"
    repository = ChatRepository(path)
    session = repository.create_session("alice")
    renamed = repository.rename_session("alice", session["id"], "Ausbildung Plan")
    assert renamed["title"] == "Ausbildung Plan"
    reopened = ChatRepository(path)
    assert reopened.get_session("alice", session["id"])["title"] == "Ausbildung Plan"
    try:
        reopened.rename_session("bob", session["id"], "Unauthorized")
    except KeyError:
        pass
    else:
        raise AssertionError("another user's session must not be renamed")
    for invalid in ("", "  ", "x" * 101):
        try:
            reopened.rename_session("alice", session["id"], invalid)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid session title was accepted")


def test_public_context_query_preserves_turns_across_reopen_and_enforces_owner(tmp_path: Path):
    database_path = tmp_path / "conversation.db"
    rag = RAGService(ChromaVectorStore(tmp_path / "chroma", DeterministicEmbedding()))
    users = UserStateService(UserStateRepository(tmp_path / "state.db"))
    llm = FakeLLM("Antwort")
    orchestrator = UnifiedOrchestrator(rag, users, llm)
    service = ChatService(ChatRepository(database_path), orchestrator, FileService())
    alice = ActorContext.from_local_header("alice")
    session = service.create_session(alice)

    empty = service.get_context_snapshot(alice, session.id)
    assert empty.messages == ()
    service.send_message(alice, session.id, "Der Termin ist am Dienstag.")
    service.send_message(alice, session.id, "An welchem Tag ist der Termin?")
    assert "Der Termin ist am Dienstag." in llm.last_prompt

    before_query = service.get_messages(alice, session.id)
    snapshot = service.get_context_snapshot(alice, session.id)
    assert [item.role for item in snapshot.messages] == ["user", "assistant", "user", "assistant"]
    assert service.get_messages(alice, session.id) == before_query
    with pytest.raises(KeyError):
        service.append_assistant_message(ActorContext.from_local_header("bob"), session.id, "unauthorized")
    with pytest.raises(ValueError, match="must not be blank"):
        service.append_assistant_message(alice, session.id, "  ")
    assert service.get_messages(alice, session.id) == before_query
    with pytest.raises(KeyError):
        service.get_context_snapshot(ActorContext.from_local_header("bob"), session.id)

    reopened = ChatService(ChatRepository(database_path), orchestrator, FileService())
    assert reopened.get_context_snapshot(alice, session.id).to_llm_history() == snapshot.to_llm_history()
    assert [item.id for item in reopened.list_sessions(alice)] == [session.id]
    assert reopened.list_sessions(ActorContext.from_local_header("bob")) == []

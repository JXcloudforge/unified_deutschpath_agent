from pathlib import Path

from app.agent import UnifiedOrchestrator
from app.chat import ChatRepository, ChatService
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
    session = service.create_session("jing")
    result = service.send_message("jing", session["id"], "Hallo")
    assert result["assistant_message"]["content"] == "Hallo!"
    assert [item["role"] for item in service.repository.messages("jing", session["id"])] == ["user", "assistant"]


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

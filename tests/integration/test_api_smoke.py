from importlib import import_module
from pathlib import Path

from fastapi.testclient import TestClient

from app.agent import UnifiedOrchestrator
from app.chat import ChatRepository, ChatService
from app.files import FileService
from app.llm import FakeLLM
from app.rag import DeterministicEmbedding, RAGService
from app.rag.vector_store import ChromaVectorStore
from app.users import UserStateRepository, UserStateService
from ui.api_client import normalize_attachment, normalize_messages, normalize_send_result, normalize_session


def test_health_chat_and_file_routes_use_current_unified_stack(tmp_path: Path, monkeypatch):
    # Import the eager FastAPI composition root only after isolating its runtime paths.
    # This avoids opening a developer's running data/chroma database during TestClient smoke.
    monkeypatch.setenv("STAGE2_DATA_PATH", str(tmp_path / "api-runtime"))
    api_main = import_module("app.api.main")
    llm = FakeLLM("API_FAKE_ANSWER")
    rag = RAGService(ChromaVectorStore(tmp_path / "chroma", DeterministicEmbedding()))
    users = UserStateService(UserStateRepository(tmp_path / "state.db"))
    monkeypatch.setattr(api_main, "chat", ChatService(ChatRepository(tmp_path / "chat.db"), UnifiedOrchestrator(rag, users, llm), FileService()))
    # Ensure a working platform closes TestClient's AnyIO portal during teardown.
    with TestClient(api_main.app) as client:
        health = client.get("/health").json()
        assert health["router"] in {"rules", "hybrid"}
        assert health["router_initialized"] is True
        assert health["tavily_connectivity"] == "not_tested"
        headers = {"X-User-ID": "api-user"}
        session = normalize_session(client.post("/sessions", headers=headers).json())
        uploaded = client.post(f"/sessions/{session['id']}/attachments", headers=headers, files={"file": ("api.txt", b"API_UPLOAD_SECRET_321", "text/plain")})
        assert uploaded.status_code == 200
        assert normalize_attachment(uploaded.json())["filename"].endswith(".txt")
        sent = client.post(f"/sessions/{session['id']}/messages", headers=headers, json={"content": "Use the upload"})
        assert sent.status_code == 200 and normalize_send_result(sent.json())["assistant_message"]["content"] == "API_FAKE_ANSWER"
        assert "API_UPLOAD_SECRET_321" in llm.last_prompt
        # The live FastAPI schema is A: a top-level list, not {"messages": [...]}.
        messages_payload = client.get(f"/sessions/{session['id']}/messages", headers=headers).json()
        assert isinstance(messages_payload, list)
        assert [item["role"] for item in normalize_messages(messages_payload)] == ["user", "assistant"]

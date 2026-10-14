from importlib import import_module

from fastapi.testclient import TestClient

from app.chat import ChatService
from app.chat.repository import ChatRepository
from app.files import FileService
from app.orchestration import OrchestrationService
from app.orchestration.chat_adapter import ConversationListSessionsQuery, ConversationRenameExecutor, M08ChatAdapter
from app.routing import RuleBasedIntentRouter
from app.suggestions import FollowUpSuggestionService


class AusbildungAnswer:
    def answer(self, **kwargs):
        return "Ausbildung ist eine betriebliche Berufsausbildung. Deutschkenntnisse und die konkreten Anforderungen unterscheiden sich je nach Beruf."


def _chat(tmp_path):
    return ChatService(ChatRepository(tmp_path / "chat.sqlite3"), AusbildungAnswer(), FileService())


def _configure_api(monkeypatch, api, chat, *, adapter=None, queries=None):
    monkeypatch.setattr(api, "chat", chat)
    monkeypatch.setattr(api, "m08_chat_adapter", adapter)
    monkeypatch.setattr(api, "M08_LOCAL_ENABLED", bool(adapter))
    monkeypatch.setattr(api, "APP_ENV", "development")
    monkeypatch.setattr(api, "suggestion_queries", queries or FollowUpSuggestionService(chat))


def test_http_suggestions_are_opt_in_and_old_chat_response_remains_compatible(tmp_path, monkeypatch):
    api = import_module("app.api.main")
    chat = _chat(tmp_path)
    calls = []
    real_queries = FollowUpSuggestionService(chat)

    class SpyQueries:
        def get_follow_up_suggestions(self, actor, session_id, *, maximum=3):
            calls.append((actor.user_id, session_id))
            return real_queries.get_follow_up_suggestions(actor, session_id, maximum=maximum)

    _configure_api(monkeypatch, api, chat, queries=SpyQueries())
    with TestClient(api.app, client=("127.0.0.1", 45678)) as client:
        headers = {"X-User-ID": "alice"}
        session_id = client.post("/sessions", headers=headers).json()["id"]
        legacy = client.post(f"/sessions/{session_id}/messages", headers=headers,
                             json={"content": "德国 Ausbildung 对德语有什么要求？"})
        assert legacy.status_code == 200
        assert "suggestions" not in legacy.json()
        assert calls == []

        enabled = client.post(f"/sessions/{session_id}/messages", headers=headers,
                              json={"content": "德国 Ausbildung 对德语有什么要求？", "include_suggestions": True})
        assert enabled.status_code == 200
        body = enabled.json()
        assert body["assistant_message"]["content"].startswith("Ausbildung")
        assert 1 <= len(body["suggestions"]) <= 3
        assert body["suggestions"][0]["category"] == "ausbildung"
        assert len(client.get(f"/sessions/{session_id}/messages", headers=headers).json()) == 4
        assert len(calls) == 1


def test_suggestion_failure_does_not_break_http_answer(tmp_path, monkeypatch):
    api = import_module("app.api.main")
    chat = _chat(tmp_path)

    class BrokenQueries:
        def get_follow_up_suggestions(self, *args, **kwargs):
            raise RuntimeError("optional module unavailable")

    _configure_api(monkeypatch, api, chat, queries=BrokenQueries())
    with TestClient(api.app, client=("127.0.0.1", 45678)) as client:
        headers = {"X-User-ID": "alice"}
        session_id = client.post("/sessions", headers=headers).json()["id"]
        response = client.post(f"/sessions/{session_id}/messages", headers=headers,
                               json={"content": "德国 Ausbildung 对德语有什么要求？", "include_suggestions": True})
    assert response.status_code == 200
    assert response.json()["assistant_message"]["content"].startswith("Ausbildung")
    assert "suggestions" not in response.json()


def test_http_m08_confirmation_responses_do_not_attach_suggestions(tmp_path, monkeypatch):
    api = import_module("app.api.main")
    chat = _chat(tmp_path)
    state = OrchestrationService(tmp_path / "orchestration.sqlite3", RuleBasedIntentRouter(), chat,
        {"rename_session": ConversationRenameExecutor(chat, chat),
         "list_sessions": ConversationListSessionsQuery(chat)})
    adapter = M08ChatAdapter(chat, chat, state)

    class MustNotRun:
        def get_follow_up_suggestions(self, *args, **kwargs):
            raise AssertionError("M08 operation responses do not request suggestions")

    _configure_api(monkeypatch, api, chat, adapter=adapter, queries=MustNotRun())
    with TestClient(api.app, client=("127.0.0.1", 45678)) as client:
        headers = {"X-User-ID": "alice"}
        session_id = client.post("/sessions", headers=headers).json()["id"]
        response = client.post(f"/sessions/{session_id}/messages", headers=headers,
                               json={"content": "把当前会话改名为德语复习", "include_suggestions": True})
    assert response.status_code == 200
    assert response.json()["orchestration"]["status"] == "AWAITING_CONFIRMATION"
    assert "suggestions" not in response.json()

    # An unrelated knowledge answer may finish, but M09 must remain silent while
    # the earlier write proposal is still waiting for confirmation.
    monkeypatch.setattr(api, "suggestion_queries", FollowUpSuggestionService(chat, state))
    with TestClient(api.app, client=("127.0.0.1", 45678)) as client:
        headers = {"X-User-ID": "alice"}
        active = client.post(f"/sessions/{session_id}/messages", headers=headers,
                             json={"content": "德国 Ausbildung 对德语有什么要求？", "include_suggestions": True})
    assert active.status_code == 200
    assert active.json()["suggestions"] == []

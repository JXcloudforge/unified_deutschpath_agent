import pytest

from ui.api_client import (
    ApiContractError,
    Stage2ApiClient,
    normalize_attachment,
    normalize_messages,
    normalize_send_result,
    normalize_session,
    resolve_api_base_url,
    request_error_detail,
)


def test_health_metadata_uses_the_same_api_base_url(monkeypatch):
    calls = []

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"status": "ok", "llm_provider": "FakeLLM"}

    def get(url, **kwargs):
        calls.append((url, kwargs))
        return Response()

    monkeypatch.setattr("ui.api_client.requests.get", get)
    client = Stage2ApiClient("http://api.example/")
    assert client.get_health()["llm_provider"] == "FakeLLM"
    assert calls == [("http://api.example/health", {"timeout": 10})]


def test_create_session_response_is_read_at_the_correct_level():
    assert normalize_session({"id": "session-1", "title": "New Chat"})["id"] == "session-1"


def test_rename_session_uses_user_scoped_patch_contract(monkeypatch):
    calls = []

    class Response:
        def raise_for_status(self): pass
        def json(self): return {"id": "session-1", "user_id": "alice", "title": "Ausbildung"}

    def patch(url, **kwargs):
        calls.append((url, kwargs))
        return Response()

    monkeypatch.setattr("ui.api_client.requests.patch", patch)
    result = Stage2ApiClient("http://api.example").rename_session("alice", "session-1", "Ausbildung")
    assert result["title"] == "Ausbildung"
    assert calls[0][0] == "http://api.example/sessions/session-1"
    assert calls[0][1]["headers"] == {"X-User-ID": "alice"}
    assert calls[0][1]["json"] == {"title": "Ausbildung"}


def test_api_base_url_defaults_to_deutschpath_backend_port(monkeypatch):
    monkeypatch.delenv("DEUTSCHPATH_API_BASE_URL", raising=False)
    assert resolve_api_base_url() == "http://127.0.0.1:8765"


def test_api_base_url_supports_environment_override_and_normalizes_slash(monkeypatch):
    monkeypatch.setenv("DEUTSCHPATH_API_BASE_URL", "http://127.0.0.1:9876/")
    assert resolve_api_base_url() == "http://127.0.0.1:9876"


def test_message_list_and_wrapped_message_list_are_supported():
    messages = [{"role": "user", "content": "Hallo"}, {"role": "assistant", "content": "Hi"}]
    assert normalize_messages(messages) == messages
    assert normalize_messages({"messages": messages}) == messages


def test_empty_messages_are_valid():
    assert normalize_messages([]) == []
    assert normalize_messages({"messages": []}) == []


@pytest.mark.parametrize("payload", ["not-a-list", ["not-an-object"], {"messages": {}}])
def test_invalid_message_payload_never_reaches_streamlit_indexing(payload):
    with pytest.raises(ApiContractError):
        normalize_messages(payload)


def test_send_and_attachment_response_contracts():
    result = normalize_send_result({"user_message": {"role": "user", "content": "Hallo"}, "assistant_message": {"role": "assistant", "content": "Hi"}})
    assert result["assistant_message"]["content"] == "Hi"
    assert normalize_attachment({"filename": "lesson.txt", "file_type": "txt", "characters": 10})["filename"] == "lesson.txt"


def test_upload_attachment_generates_the_fastapi_file_multipart_request(monkeypatch):
    captured = {}

    class Response:
        def raise_for_status(self): pass
        def json(self): return {"filename": "lesson.docx", "file_type": "docx", "characters": 328}

    def fake_post(url, **kwargs):
        captured["url"], captured["kwargs"] = url, kwargs
        return Response()

    monkeypatch.setattr("ui.api_client.requests.post", fake_post)
    result = Stage2ApiClient("http://api.example").upload_attachment("user-1", "session-1", "lesson.docx", b"word-data", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    assert captured["url"].endswith("/sessions/session-1/attachments")
    assert captured["kwargs"]["headers"] == {"X-User-ID": "user-1"}
    assert captured["kwargs"]["files"]["file"] == ("lesson.docx", b"word-data", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    assert result["characters"] == 328


def test_invalid_upload_response_and_http_failure_are_controlled():
    with pytest.raises(ApiContractError):
        normalize_attachment({"filename": "missing-type"})

    class Response:
        def json(self): return {"detail": "Unsupported file type"}
    class UploadFailure(Exception):
        response = Response()
    assert request_error_detail(UploadFailure()) == "Unsupported file type"

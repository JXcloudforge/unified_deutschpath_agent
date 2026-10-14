"""UI contract and AppTest coverage adapted from 03's API and Streamlit tests."""

from pathlib import Path

import pytest
import requests
from streamlit.testing.v1 import AppTest

from ui.api_client import (
    ApiContractError,
    Stage2ApiClient,
    normalize_learning_events,
    normalize_user_state,
    request_error_detail,
)


APP = Path(__file__).parents[2] / "ui" / "streamlit_app.py"


def profile(user_id="demo-user", **changes):
    return {"user_id": user_id, "current_level": "A2", "target_level": "B1",
            "learning_goal": "Learn German", "learning_preferences": None, **changes}


def test_profile_client_uses_existing_identity_header_and_bounded_metadata_timeout(monkeypatch):
    calls = []

    class Response:
        def __init__(self, payload):
            self.payload = payload

        def raise_for_status(self):
            pass

        def json(self):
            return self.payload

    def get(url, **kwargs):
        calls.append(("GET", url, kwargs))
        if url.endswith("/sessions"):
            return Response([{"id": "session-a", "user_id": "alice"}])
        return Response([] if url.endswith("/events") else profile("alice"))

    def patch(url, **kwargs):
        calls.append(("PATCH", url, kwargs))
        return Response(profile("alice", **kwargs["json"]))

    monkeypatch.setattr("ui.api_client.requests.get", get)
    monkeypatch.setattr("ui.api_client.requests.patch", patch)
    client = Stage2ApiClient("http://api.example/", timeout=30)
    assert client.get_user_state("alice")["current_level"] == "A2"
    assert client.update_user_state("alice", {"learning_goal": None})["learning_goal"] is None
    assert client.list_learning_events("alice") == []
    assert client.list_sessions("alice")[0]["id"] == "session-a"
    assert [(method, url) for method, url, _ in calls] == [
        ("GET", "http://api.example/users/me/state"),
        ("PATCH", "http://api.example/users/me/state"),
        ("GET", "http://api.example/users/me/events"),
        ("GET", "http://api.example/sessions"),
    ]
    assert all(kwargs["headers"] == {"X-User-ID": "alice"} and kwargs["timeout"] == 10 for _, _, kwargs in calls)
    assert calls[1][2]["json"] == {"learning_goal": None}
    assert calls[2][2]["params"] == {"limit": 10}


@pytest.mark.parametrize("payload", [None, {"user_id": "alice"}, profile("other"), profile("alice", learning_goal=123)])
def test_profile_contract_rejects_missing_fields_and_wrong_user(payload):
    with pytest.raises(ApiContractError):
        normalize_user_state(payload, "alice")


def test_nullable_profile_and_empty_events_are_valid():
    empty = profile("alice", current_level=None, target_level=None, learning_goal=None)
    assert normalize_user_state(empty, "alice") == empty
    assert normalize_learning_events([], "alice") == []
    with pytest.raises(ApiContractError):
        normalize_learning_events([{"user_id": "bob"}], "alice")
    with pytest.raises(ApiContractError):
        normalize_learning_events([{"user_id": "alice", "id": "invalid"}], "alice")


def test_profile_request_failure_and_timeout_remain_failures(monkeypatch):
    def timeout(*args, **kwargs):
        raise requests.Timeout("test timeout")

    monkeypatch.setattr("ui.api_client.requests.patch", timeout)
    with pytest.raises(requests.Timeout):
        Stage2ApiClient("http://api.example").update_user_state("alice", {"current_level": "B1"})
    assert "超时" in request_error_detail(requests.Timeout())
    assert "不可用" in request_error_detail(requests.ConnectionError())


@pytest.fixture
def ui_backend(monkeypatch):
    class Backend:
        def __init__(self):
            self.profiles = {"demo-user": profile(), "bob": profile("bob", current_level="C1", target_level="C2", learning_goal="Bob goal")}
            self.updates = []
            self.history_reads = []
            self.fail_update = False
            self.fail_read = False
            self.chat_messages = {}
            self.send_calls = []
            self.send_error = None
            self.sessions = {
                "demo-user": [{"id": "session-a", "user_id": "demo-user", "title": "First"}, {"id": "session-b", "user_id": "demo-user", "title": "Second"}],
                "bob": [{"id": "session-bob", "user_id": "bob", "title": "Bob chat"}],
            }

        def list_sessions(self, user_id):
            return self.sessions[user_id]

        def rename_session(self, user_id, session_id, title):
            session = next(item for item in self.sessions[user_id] if item["id"] == session_id)
            session["title"] = title.strip()
            return dict(session)

        def get_health(self):
            return {"status": "ok", "llm_provider": "FakeLLM", "llm_model": None,
                    "deepseek_config_source": "not configured", "tavily_config_source": "not configured"}

        def create_session(self, user_id):
            result = {"id": "session-new", "user_id": user_id, "title": "New Chat"}
            self.sessions[user_id].append(result)
            return result

        def get_user_state(self, user_id):
            if self.fail_read:
                raise requests.ConnectionError("offline")
            return dict(self.profiles[user_id])

        def update_user_state(self, user_id, changes):
            self.updates.append((user_id, changes))
            if self.fail_update:
                raise requests.Timeout("slow")
            self.profiles[user_id].update(changes)
            return dict(self.profiles[user_id])

        def list_learning_events(self, user_id, *, limit):
            assert limit == 10
            return [{"id": 1, "user_id": user_id, "event_type": "practice", "item": f"{user_id} vocabulary", "result": "completed", "created_at": "2026-10-12"}]

        def get_messages(self, user_id, session_id):
            self.history_reads.append((user_id, session_id))
            return self.chat_messages.get((user_id, session_id), [{"role": "user", "content": f"History: {session_id}"}])

        def send_message(self, user_id, session_id, content):
            self.send_calls.append((user_id, session_id, content))
            user_message = {"role": "user", "content": content}
            assistant_message = {"role": "assistant", "content": f"Reply: {content}"}
            previous = self.chat_messages.get((user_id, session_id), [{"role": "user", "content": f"History: {session_id}"}])
            self.chat_messages[(user_id, session_id)] = previous + [user_message, assistant_message]
            if self.send_error:
                raise self.send_error
            return {"user_message": user_message, "assistant_message": assistant_message}

    backend = Backend()
    monkeypatch.setattr("ui.api_client.Stage2ApiClient", lambda _base: backend)
    return backend


def click(app, label):
    next(button for button in app.button if button.label == label).click().run()
    assert not app.exception


def test_profile_form_saves_only_changes_and_can_clear_fields(ui_backend):
    app = AppTest.from_file(str(APP)).run()
    assert not app.exception
    assert app.selectbox(key="profile_current_level").value == "A2"
    assert any("demo-user vocabulary" in item.value for item in app.text)
    app.selectbox(key="profile_target_level").select("B2")
    app.text_area(key="profile_learning_goal").input("  German interview  ")
    app.text_area(key="profile_learning_preferences").input("Dialogue")
    click(app, "保存学习资料")
    assert ui_backend.updates == [("demo-user", {"target_level": "B2", "learning_goal": "German interview", "learning_preferences": "Dialogue"})]
    assert app.session_state["learning_profile"]["target_level"] == "B2"
    assert app.text_area(key="profile_learning_goal").value == "German interview"
    assert app.success[0].value == "学习资料已保存。"
    app.text_area(key="profile_learning_goal").input(" ")
    click(app, "保存学习资料")
    assert ui_backend.updates[-1] == ("demo-user", {"learning_goal": None})


def test_failed_save_keeps_confirmed_profile_and_draft_without_reposting(ui_backend):
    app = AppTest.from_file(str(APP)).run()
    ui_backend.fail_update = True
    app.text_area(key="profile_learning_goal").input("Unsaved draft")
    click(app, "保存学习资料")
    assert app.session_state["learning_profile"]["learning_goal"] == "Learn German"
    assert app.text_area(key="profile_learning_goal").value == "Unsaved draft"
    assert any("超时" in error.value for error in app.error)
    assert not app.success
    app.run()
    assert not app.exception
    assert len(ui_backend.updates) == 1


def test_user_switch_clears_previous_profile_chat_and_upload_state(ui_backend):
    app = AppTest.from_file(str(APP)).run()
    app.selectbox(key="session_picker").select("session-a").run()
    app.session_state["uploaded_attachment_fingerprints"] = {"private-upload"}
    app.text_area(key="profile_learning_goal").input("Alice unsaved goal")
    app.text_input[0].input("bob").run()
    assert not app.exception
    assert app.session_state["learning_profile"]["user_id"] == "bob"
    assert app.text_area(key="profile_learning_goal").value == "Bob goal"
    assert app.selectbox(key="profile_current_level").value == "C1"
    assert app.selectbox(key="session_picker").value is None
    assert "session_id" not in app.session_state
    assert "uploaded_attachment_fingerprints" not in app.session_state
    assert ("bob", "session-a") not in ui_backend.history_reads
    assert all("demo-user" not in item.value for item in app.text)


def test_session_switch_and_create_keep_history_scoped_to_selection(ui_backend):
    app = AppTest.from_file(str(APP)).run()
    app.selectbox(key="session_picker").select("session-a").run()
    assert not app.exception
    assert app.chat_message[0].markdown[0].value == "History: session-a"
    app.selectbox(key="session_picker").select("session-b").run()
    assert app.chat_message[0].markdown[0].value == "History: session-b"
    click(app, "＋ 新建会话")
    assert app.session_state["session_id"] == "session-new"
    assert app.selectbox(key="session_picker").value == "session-new"
    app.selectbox(key="session_picker").select("session-a").run()
    assert not app.exception
    assert app.chat_message[0].markdown[0].value == "History: session-a"


def test_session_rename_search_and_selected_title_are_visible(ui_backend):
    app = AppTest.from_file(str(APP)).run()
    app.selectbox(key="session_picker").select("session-a").run()
    app.text_input(key="rename_session_title").set_value("Ausbildung Plan")
    click(app, "保存标题")
    assert ui_backend.sessions["demo-user"][0]["title"] == "Ausbildung Plan"
    assert any(item.value == "Ausbildung Plan" for item in app.header)
    app.text_input(key="session_search").set_value("second").run()
    options = app.selectbox(key="session_picker").options
    assert len(options) == 2 and "Second" in options[1] and "Ausbildung Plan" not in " ".join(map(str, options))
    app.text_input(key="rename_session_title").set_value("Filtered but active")
    click(app, "保存标题")
    assert ui_backend.sessions["demo-user"][0]["title"] == "Filtered but active"
    assert not app.exception


def test_system_information_panel_shows_current_version_and_release_history(ui_backend):
    app = AppTest.from_file(str(APP)).run()
    assert not app.exception
    visible_text = list(app.markdown) + list(app.caption) + list(app.text)
    assert any("v0.1.1.dev0" in item.value and "unreleased development candidate" in item.value.lower()
               for item in visible_text)
    assert app.selectbox(key="version_history_selector").options == ["0.1.1.dev0", "0.1.0-beta.1"]
    milestone_labels = [item.label for item in app.expander]
    assert all(any(label.startswith(f"M{number:02d} ·") for label in milestone_labels) for number in range(1, 11))
    assert any("M06" in item.value for item in app.markdown)
    app.selectbox(key="version_history_selector").select("0.1.0-beta.1").run()
    assert not app.exception
    assert any("163 passed, 1 skipped" in item.value for item in app.markdown)
    app.selectbox(key="system_information_view").select("功能状态").run()
    assert not app.exception
    assert any("NOT VERIFIED" in item.value and "IMPLEMENTED" in item.value for item in app.markdown)


def test_chat_send_renders_user_and_assistant_immediately_without_rerun(ui_backend):
    app = AppTest.from_file(str(APP)).run()
    app.selectbox(key="session_picker").select("session-a").run()
    prior_reads = len(ui_backend.history_reads)
    app.chat_input(key="chat_input").set_value("Hallo").run()
    assert not app.exception
    assert ui_backend.send_calls == [("demo-user", "session-a", "Hallo")]
    assert [item.markdown[0].value for item in app.chat_message] == [
        "History: session-a", "Hallo", "Reply: Hallo",
    ]
    assert len(ui_backend.history_reads) == prior_reads + 1


def test_timed_out_post_recovers_persisted_turn_from_session_history_without_resend(ui_backend):
    ui_backend.send_error = requests.Timeout("slow")
    app = AppTest.from_file(str(APP)).run()
    app.selectbox(key="session_picker").select("session-a").run()
    app.chat_input(key="chat_input").set_value("Search this later").run()
    assert not app.exception
    assert ui_backend.send_calls == [("demo-user", "session-a", "Search this later")]
    assert [item.markdown[0].value for item in app.chat_message][-2:] == [
        "Search this later", "Reply: Search this later",
    ]
    assert any("从当前会话历史恢复" in item.value for item in app.caption)


def test_ocr_review_is_editable_and_requires_explicit_confirmation(ui_backend):
    app = AppTest.from_file(str(APP)).run()
    app.selectbox(key="session_picker").select("session-a").run()
    ui_backend.confirm_ocr = lambda user_id, session_id, operation_id, rows: {
        "operation_id": operation_id, "status": "verified", "inserted_rows": len(rows),
        "rows": rows,
    }
    app.session_state["ocr_preview"] = {
        "success": True, "session_id": "session-a", "operation_id": "b6-operation-123",
        "ocr": {"raw_text": "Haus house A1"},
        "rows": [{"word": "Haus", "meaning": "house", "level": "A1"}],
    }
    app.run()
    assert not app.exception
    assert app.text_area(key="ocr-raw-b6-operation-123").value == "Haus house A1"
    assert app.checkbox(key="ocr-confirm-check-b6-operation-123").value is False
    assert app.button(key="ocr-commit-b6-operation-123").disabled is True
    app.checkbox(key="ocr-confirm-check-b6-operation-123").check().run()
    app.button(key="ocr-commit-b6-operation-123").click().run()
    assert not app.exception
    assert any("已写入并查询验证 1 条记录" in item.value for item in app.success)


def test_profile_load_failure_does_not_block_chat_and_refresh_recovers(ui_backend):
    ui_backend.fail_read = True
    app = AppTest.from_file(str(APP)).run()
    app.selectbox(key="session_picker").select("session-a").run()
    assert not app.exception
    assert app.chat_message[0].markdown[0].value == "History: session-a"
    assert not app.text_area
    assert any("无法加载学习资料" in error.value for error in app.error)
    ui_backend.fail_read = False
    click(app, "刷新学习资料")
    assert app.text_area(key="profile_learning_goal").value == "Learn German"


def test_api_settings_panel_is_present_and_secrets_are_disabled_without_local_launcher(ui_backend, monkeypatch):
    monkeypatch.delenv("DEUTSCHPATH_LOCAL_SETTINGS_ENABLED", raising=False)
    app = AppTest.from_file(str(APP)).run()
    assert not app.exception
    assert any("API Settings" in item.label for item in app.expander)
    assert app.text_input(key="settings_deepseek_key").proto.type == 1  # TextInputProto.Type.PASSWORD
    assert app.text_input(key="settings_tavily_key").proto.type == 1  # TextInputProto.Type.PASSWORD
    assert app.text_input(key="settings_deepseek_key").disabled is True
    assert any("密钥管理未启用" in warning.value for warning in app.warning)

from importlib import import_module
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from fastapi.testclient import TestClient

from app.chat import ActorContext, ChatService
from app.chat.repository import ChatRepository
from app.files import FileService
from app.orchestration import OrchestrationService
from app.orchestration.chat_adapter import (
    ConversationListSessionsQuery, ConversationRenameExecutor, M08ChatAdapter, _parse_rename,
)
from app.routing import RuleBasedIntentRouter
from app.orchestration.service import ExecutionUncertainError


class NoAnswer:
    def answer(self, **kwargs):
        return "ordinary-answer"


def build_chat(tmp_path):
    return ChatService(ChatRepository(tmp_path / "chat.db"), NoAnswer(), FileService())


def build_adapter(tmp_path, chat):
    state = OrchestrationService(tmp_path / "orchestration.sqlite3", RuleBasedIntentRouter(), chat,
        {"rename_session": ConversationRenameExecutor(chat, chat),
         "list_sessions": ConversationListSessionsQuery(chat)})
    return M08ChatAdapter(chat, chat, state), state


@pytest.mark.parametrize("text,title", [
    ("把当前会话改名", None),
    ("把当前对话改名为德语A1复习", "德语A1复习"),
    ("我让你把当前对话改名为德语A1复习", "德语A1复习"),
    ("重命名当前会话为德语学习计划", "德语学习计划"),
])
def test_rename_parser_covers_supported_chinese_word_orders(text, title):
    assert _parse_rename(text) == (True, title)


def test_http_multiturn_clarify_confirm_and_duplicate_confirmation(tmp_path, monkeypatch):
    monkeypatch.setenv("M08_LOCAL_ENABLED", "false")
    api = import_module("app.api.main")
    chat = build_chat(tmp_path)
    adapter, state = build_adapter(tmp_path, chat)
    monkeypatch.setattr(api, "chat", chat)
    monkeypatch.setattr(api, "m08_chat_adapter", adapter)
    monkeypatch.setattr(api, "m08_orchestration", state)
    monkeypatch.setattr(api, "M08_LOCAL_ENABLED", True)
    monkeypatch.setattr(api, "APP_ENV", "development")

    with TestClient(api.app, client=("127.0.0.1", 45678)) as client:
        headers = {"X-User-ID": "alice"}
        session_id = client.post("/sessions", headers=headers).json()["id"]
        ordinary = client.post(f"/sessions/{session_id}/messages", headers=headers, json={"content": "Hallo"})
        assert ordinary.status_code == 200
        assert ordinary.json()["assistant_message"]["content"] == "ordinary-answer"
        missing = client.post(f"/sessions/{session_id}/messages", headers=headers,
                              json={"content": "把当前会话改名"}).json()
        operation_id = missing["orchestration"]["orchestration_id"]
        assert missing["orchestration"]["status"] == "NEEDS_CLARIFICATION"
        clarified = client.post(f"/sessions/{session_id}/messages", headers=headers,
                                json={"content": "德语复习"}).json()
        assert clarified["orchestration"]["orchestration_id"] == operation_id
        assert clarified["orchestration"]["status"] == "AWAITING_CONFIRMATION"
        confirmed = client.post(f"/sessions/{session_id}/messages", headers=headers,
                                json={"content": "确认"}).json()
        assert confirmed["orchestration"]["status"] == "SUCCEEDED"
        assert chat.get_session(ActorContext("alice"), session_id).title == "德语复习"
        replay = client.post(f"/sessions/{session_id}/messages", headers=headers,
                             json={"content": "确认"}).json()
        assert "没有再次执行" in replay["assistant_message"]["content"]
        assert state.get_orchestration_status(ActorContext("alice"), operation_id).status.value == "SUCCEEDED"
        history = client.get(f"/sessions/{session_id}/messages", headers=headers).json()
        assert [message["role"] for message in history] == ["user", "assistant"] * 4 + ["user", "assistant"]


def test_http_revision_invalidates_old_confirmation_and_cross_user_is_denied(tmp_path, monkeypatch):
    api = import_module("app.api.main")
    chat = build_chat(tmp_path)
    adapter, state = build_adapter(tmp_path, chat)
    monkeypatch.setattr(api, "chat", chat)
    monkeypatch.setattr(api, "m08_chat_adapter", adapter)
    monkeypatch.setattr(api, "m08_orchestration", state)
    monkeypatch.setattr(api, "M08_LOCAL_ENABLED", True)
    monkeypatch.setattr(api, "APP_ENV", "development")
    alice = ActorContext("alice")
    session = chat.create_session(alice)

    with TestClient(api.app, client=("127.0.0.1", 45678)) as client:
        headers = {"X-User-ID": "alice"}
        first = client.post(f"/sessions/{session.id}/messages", headers=headers,
                            json={"content": "把当前会话改名为第一版"}).json()["orchestration"]
        old = state.get_orchestration_status(alice, first["orchestration_id"])
        revised = client.post(f"/sessions/{session.id}/messages", headers=headers,
                              json={"content": "改成最终版"}).json()["orchestration"]
        new = state.get_orchestration_status(alice, revised["orchestration_id"])
        assert old.confirmation_key != new.confirmation_key
        with pytest.raises(KeyError):
            state.get_orchestration_status(ActorContext("bob"), old.orchestration_id)
        denied = client.post(f"/sessions/{session.id}/messages", headers={"X-User-ID": "bob"},
                             json={"content": "确认"})
        assert denied.status_code == 404
        accepted = client.post(f"/sessions/{session.id}/messages", headers=headers,
                               json={"content": "确认"}).json()
        assert accepted["orchestration"]["status"] == "SUCCEEDED"
        assert chat.get_session(alice, session.id).title == "最终版"


def test_production_mutating_http_routes_fail_closed(tmp_path, monkeypatch):
    api = import_module("app.api.main")
    monkeypatch.setattr(api, "APP_ENV", "production")
    with TestClient(api.app) as client:
        response = client.post("/sessions", headers={"X-User-ID": "untrusted"})
    assert response.status_code == 401


def test_business_commit_with_lost_result_is_reconciled_without_replay(tmp_path):
    chat = build_chat(tmp_path)
    actor = ActorContext("alice")
    session = chat.create_session(actor)

    class CommitThenLoseReply:
        def __init__(self): self.calls = 0
        def execute(self, *, actor, session_id, **kwargs):
            self.calls += 1
            chat.rename_session(actor, session_id, "Verified after uncertainty")
            raise ExecutionUncertainError("simulate response loss after commit")
        def reconcile(self, *, actor, session_id, parameters, **kwargs):
            current = chat.get_session(actor, session_id)
            if current.title != parameters.get("new_name"):
                return None
            return json.dumps({"session_id": current.id, "title": current.title})
    executor = CommitThenLoseReply()
    state = OrchestrationService(tmp_path / "orchestration.sqlite3", RuleBasedIntentRouter(), chat,
                                 {"rename_session": executor})
    adapter = M08ChatAdapter(chat, chat, state)
    proposal = state.start_orchestration(actor, session.id, "rename session")
    import json
    action = json.dumps({"action_type": "rename_session", "session_id": session.id,
                         "new_name": "Verified after uncertainty"})
    pending = state.propose_action(actor, proposal.orchestration_id, action)
    first = state.confirm_pending_action(actor, proposal.orchestration_id, pending.confirmation_key)
    assert first.status.value == "UNCERTAIN"
    reconciled = adapter.handle(actor, session.id, "确认")
    assert reconciled.orchestration["status"].value == "SUCCEEDED"
    assert chat.get_session(actor, session.id).title == "Verified after uncertainty"
    assert executor.calls == 1


def test_disabled_m08_preserves_legacy_chat_path(tmp_path, monkeypatch):
    api = import_module("app.api.main")
    chat = build_chat(tmp_path)
    adapter, _state = build_adapter(tmp_path, chat)
    actor = ActorContext("alice")
    session = chat.create_session(actor)
    chat.rename_session(actor, session.id, "Existing title")
    monkeypatch.setattr(api, "chat", chat)
    monkeypatch.setattr(api, "m08_chat_adapter", None)
    monkeypatch.setattr(api, "M08_LOCAL_ENABLED", False)
    monkeypatch.setattr(api, "APP_ENV", "development")
    with TestClient(api.app, client=("127.0.0.1", 45678)) as client:
        result = client.post(f"/sessions/{session.id}/messages", headers={"X-User-ID": "alice"},
                             json={"content": "把当前会话改名为Not executed"})
    assert result.status_code == 200
    assert chat.get_session(actor, session.id).title == "Existing title"


def test_parallel_http_confirm_does_not_reconcile_active_execution(tmp_path):
    chat = build_chat(tmp_path)
    actor = ActorContext("alice")
    session = chat.create_session(actor)
    entered, release = Event(), Event()

    class SlowRename:
        calls = 0
        def execute(self, *, actor, session_id, **kwargs):
            self.calls += 1
            entered.set()
            assert release.wait(5)
            import json
            title = json.loads(kwargs["proposal"])["new_name"]
            chat.rename_session(actor, session_id, title)
            return "confirmed"

    executor = SlowRename()
    state = OrchestrationService(tmp_path / "orchestration.sqlite3", RuleBasedIntentRouter(), chat,
                                 {"rename_session": executor})
    adapter = M08ChatAdapter(chat, chat, state)
    proposed = adapter.handle(actor, session.id, "把当前会话改名为并发测试")
    orchestration_id = proposed.orchestration["orchestration_id"]
    with ThreadPoolExecutor(max_workers=1) as pool:
        first = pool.submit(adapter.handle, actor, session.id, "确认")
        assert entered.wait(5)
        second = adapter.handle(actor, session.id, "确认")
        assert "仍在执行中" in second.assistant_message.content
        assert state.get_orchestration_status(actor, orchestration_id).status.value == "EXECUTING"
        release.set()
        assert first.result(timeout=5).orchestration["status"].value == "SUCCEEDED"
    assert executor.calls == 1
    assert chat.get_session(actor, session.id).title == "并发测试"


def test_startup_recovery_marks_interrupted_execution_uncertain(tmp_path):
    chat = build_chat(tmp_path)
    actor = ActorContext("alice")
    session = chat.create_session(actor)
    state = OrchestrationService(tmp_path / "orchestration.sqlite3", RuleBasedIntentRouter(), chat)
    operation = state.start_orchestration(actor, session.id, "test interrupted")
    pending = state.propose_action(actor, operation.orchestration_id, "{}")
    state._repository.update(actor.user_id, operation.orchestration_id,
        expected=(pending.status.value,), status="EXECUTING", proposal=pending.proposal,
        confirmation_key=None, recoverable=False)

    reopened = OrchestrationService(tmp_path / "orchestration.sqlite3", RuleBasedIntentRouter(), chat)
    assert reopened.recover_interrupted_executions() == 1
    assert reopened.get_orchestration_status(actor, operation.orchestration_id).status.value == "UNCERTAIN"


def test_two_step_rename_then_list_runs_command_before_query_and_persists_results(tmp_path, monkeypatch):
    api = import_module("app.api.main")
    chat = build_chat(tmp_path)
    adapter, state = build_adapter(tmp_path, chat)
    actor = ActorContext("alice")
    session = chat.create_session(actor)
    monkeypatch.setattr(api, "chat", chat)
    monkeypatch.setattr(api, "m08_chat_adapter", adapter)
    monkeypatch.setattr(api, "m08_orchestration", state)
    monkeypatch.setattr(api, "M08_LOCAL_ENABLED", True)
    monkeypatch.setattr(api, "APP_ENV", "development")

    with TestClient(api.app, client=("127.0.0.1", 45678)) as client:
        headers = {"X-User-ID": "alice"}
        proposal_response = client.post(f"/sessions/{session.id}/messages", headers=headers,
            json={"content": "把当前会话改名为德语学习，然后列出我的会话"})
        plan = proposal_response.json()["orchestration"]
        assert proposal_response.status_code == 200
        assert plan["status"] == "AWAITING_CONFIRMATION"
        assert [step["action_type"] for step in plan["steps"]] == ["rename_session", "list_sessions"]
        assert plan["steps"][1]["depends_on"] == ["rename-session"]
        assert chat.get_session(actor, session.id).title == "New Chat"

        revised = client.post(f"/sessions/{session.id}/messages", headers=headers,
            json={"content": "改成德语语法复习"}).json()["orchestration"]
        assert revised["steps"][0]["parameters_json"] != plan["steps"][0]["parameters_json"]
        confirmed = client.post(f"/sessions/{session.id}/messages", headers=headers,
            json={"content": "确认"}).json()
        operation_id = plan["orchestration_id"]
        stored = state.get_orchestration_status(actor, operation_id)
        assert stored.status.value == "SUCCEEDED"
        assert [step.status.value for step in stored.steps] == ["SUCCEEDED", "SUCCEEDED"]
        listing = __import__("json").loads(stored.steps[1].result_reference)
        assert any(item["title"] == "德语语法复习" for item in listing)
        assert "德语语法复习" in confirmed["assistant_message"]["content"]
        assert "当前会话列表" in confirmed["assistant_message"]["content"]
        assert "New Session" not in confirmed["assistant_message"]["content"]


def test_multi_intent_requires_supported_explicit_connector(tmp_path):
    chat = build_chat(tmp_path)
    actor = ActorContext("alice")
    session = chat.create_session(actor)
    adapter, state = build_adapter(tmp_path, chat)
    response = adapter.handle(actor, session.id, "把当前会话改名为Deutsch，然后创建学习任务")
    assert "仅支持" in response.assistant_message.content
    assert state.get_pending_action(actor, session.id) is None


def test_service_rejects_unregistered_multi_step_capability(tmp_path):
    chat = build_chat(tmp_path)
    actor = ActorContext("alice")
    session = chat.create_session(actor)
    state = OrchestrationService(tmp_path / "orchestration.sqlite3", RuleBasedIntentRouter(), chat)
    operation = state.start_orchestration(actor, session.id, "invalid plan")
    proposal = {
        "steps": [{
            "step_id": "fake-create",
            "action_type": "create_learning_task",
            "owner_module": "CRM",
            "command_or_query": "Command",
            "parameters": {"title": "fake"},
            "depends_on": [],
        }]
    }
    import json
    with pytest.raises(ValueError, match="not an available public capability"):
        state.propose_action(actor, operation.orchestration_id, json.dumps(proposal))
    assert state.get_orchestration_status(actor, operation.orchestration_id).status.value == "READY"


def test_multi_step_missing_title_inherits_plan_across_turns(tmp_path):
    chat = build_chat(tmp_path)
    actor = ActorContext("alice")
    session = chat.create_session(actor)
    adapter, state = build_adapter(tmp_path, chat)
    first = adapter.handle(actor, session.id, "把当前会话改名，然后列出我的会话")
    plan_id = first.orchestration["orchestration_id"]
    assert first.orchestration["status"] == "NEEDS_CLARIFICATION"
    supplied = adapter.handle(actor, session.id, "德语口语")
    assert supplied.orchestration["orchestration_id"] == plan_id
    assert [step["action_type"] for step in supplied.orchestration["steps"]] == ["rename_session", "list_sessions"]
    assert supplied.orchestration["steps"][0]["status"].value == "PENDING"
    assert "请回复“确认”执行" in supplied.assistant_message.content


def test_first_command_failure_blocks_dependent_query_and_cancel_blocks_unstarted_steps(tmp_path):
    chat = build_chat(tmp_path)
    actor = ActorContext("alice")
    session = chat.create_session(actor)

    class BrokenCommand:
        def execute(self, **kwargs):
            raise RuntimeError("command rejected")

    class CountQuery:
        calls = 0
        def execute(self, **kwargs):
            self.calls += 1
            return "should not run"

    query = CountQuery()
    state = OrchestrationService(tmp_path / "orchestration.sqlite3", RuleBasedIntentRouter(), chat,
        {"rename_session": BrokenCommand(), "list_sessions": query})
    from app.orchestration.chat_adapter import _multi_proposal
    operation = state.start_orchestration(actor, session.id, "rename then list")
    pending = state.propose_action(actor, operation.orchestration_id, _multi_proposal(session.id, "Plan title"))
    failed = state.confirm_pending_action(actor, operation.orchestration_id, pending.confirmation_key)
    assert failed.status.value == "FAILED"
    assert [step.status.value for step in failed.steps] == ["FAILED", "BLOCKED"]
    assert query.calls == 0

    cancellable = state.start_orchestration(actor, session.id, "another plan")
    pending_cancel = state.propose_action(actor, cancellable.orchestration_id,
        _multi_proposal(session.id, "Never applied"))
    cancelled = state.cancel_pending_action(actor, cancellable.orchestration_id)
    assert cancelled.status.value == "CANCELLED"
    assert [step.status.value for step in cancelled.steps] == ["BLOCKED", "BLOCKED"]


def test_uncertain_command_is_query_reconciled_before_dependent_step(tmp_path):
    chat = build_chat(tmp_path)
    actor = ActorContext("alice")
    session = chat.create_session(actor)
    rename = ConversationRenameExecutor(chat, chat)

    class CommitThenLoseResponse(ConversationRenameExecutor):
        calls = 0
        def execute(self, **kwargs):
            self.calls += 1
            super().execute(**kwargs)
            raise ExecutionUncertainError("lost response after Command commit")

    command = CommitThenLoseResponse(chat, chat)
    state = OrchestrationService(tmp_path / "orchestration.sqlite3", RuleBasedIntentRouter(), chat,
        {"rename_session": command, "list_sessions": ConversationListSessionsQuery(chat)})
    adapter = M08ChatAdapter(chat, chat, state)
    from app.orchestration.chat_adapter import _multi_proposal
    operation = state.start_orchestration(actor, session.id, "rename then list")
    pending = state.propose_action(actor, operation.orchestration_id,
        _multi_proposal(session.id, "Reconciled title"))
    unknown = state.confirm_pending_action(actor, operation.orchestration_id, pending.confirmation_key)
    assert unknown.status.value == "UNCERTAIN"
    assert [step.status.value for step in unknown.steps] == ["UNCERTAIN", "PENDING"]

    resumed = adapter.handle(actor, session.id, "确认")
    final = state.get_orchestration_status(actor, operation.orchestration_id)
    assert final.status.value == "SUCCEEDED"
    assert [step.status.value for step in final.steps] == ["SUCCEEDED", "SUCCEEDED"]
    assert command.calls == 1
    assert chat.get_session(actor, session.id).title == "Reconciled title"
    assert resumed.orchestration["status"].value == "SUCCEEDED"


def test_failed_second_query_returns_partial_and_does_not_replay_rename(tmp_path):
    chat = build_chat(tmp_path)
    actor = ActorContext("alice")
    session = chat.create_session(actor)
    rename = ConversationRenameExecutor(chat, chat)

    class BrokenList:
        calls = 0
        def execute(self, **kwargs):
            self.calls += 1
            raise RuntimeError("query unavailable")

    query = BrokenList()
    state = OrchestrationService(tmp_path / "orchestration.sqlite3", RuleBasedIntentRouter(), chat,
        {"rename_session": rename, "list_sessions": query})
    from app.orchestration.chat_adapter import _multi_proposal
    operation = state.start_orchestration(actor, session.id, "rename then list")
    pending = state.propose_action(actor, operation.orchestration_id,
        _multi_proposal(session.id, "Partial German"))
    result = state.confirm_pending_action(actor, operation.orchestration_id, pending.confirmation_key)
    assert result.status.value == "PARTIAL"
    assert [step.status.value for step in result.steps] == ["SUCCEEDED", "FAILED"]
    assert chat.get_session(actor, session.id).title == "Partial German"
    assert query.calls == 1

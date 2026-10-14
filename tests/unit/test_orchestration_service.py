import pytest
from concurrent.futures import ThreadPoolExecutor
from threading import Event

from app.chat.contracts import ActorContext, ConversationContextSnapshot
from app.orchestration import OrchestrationService, OrchestrationStatus
from app.routing import Intent, RouteDecision, RuleBasedIntentRouter


class Conversations:
    def get_context_snapshot(self, actor, session_id):
        assert actor.user_id == "alice"
        return ConversationContextSnapshot(session_id, (), 12000, 0, False)


class CountingExecutor:
    def __init__(self):
        self.calls = []

    def execute(self, **kwargs):
        self.calls.append(kwargs)
        return "result-1"


@pytest.fixture
def actor():
    return ActorContext("alice")


def service(path, executor=None):
    mapping = {Intent.NO_TOOL.value: executor} if executor else None
    return OrchestrationService(path, RuleBasedIntentRouter(), Conversations(), mapping)


def test_simple_knowledge_route_creates_scoped_ready_state_and_survives_restart(tmp_path, actor):
    path = tmp_path / "orchestration.sqlite3"
    item = service(path).start_orchestration(actor, "s1", "Explain German Dativ")
    assert item.status is OrchestrationStatus.READY
    assert item.intent == "rag"
    reopened = service(path)
    assert reopened.get_orchestration_status(actor, item.orchestration_id) == item
    assert reopened.get_route_decision(actor, item.orchestration_id).intent is Intent.RAG


def test_clarification_inherits_original_and_requires_confirmation(tmp_path, actor):
    api = service(tmp_path / "state.db")
    item = api.start_orchestration(actor, "s1", "Create two learning tasks", missing_fields=("start_date",))
    assert item.status is OrchestrationStatus.NEEDS_CLARIFICATION
    ready = api.submit_clarification(actor, item.orchestration_id, "Tomorrow", missing_fields=())
    assert ready.status is OrchestrationStatus.READY
    assert "Create two learning tasks" in ready.proposal
    pending = api.propose_action(actor, item.orchestration_id, "Create exactly two tasks starting tomorrow")
    assert pending.status is OrchestrationStatus.AWAITING_CONFIRMATION
    assert pending.proposal.endswith("tomorrow")


def test_confirmation_is_exactly_once_and_requires_registered_executor(tmp_path, actor):
    executor = CountingExecutor()
    api = service(tmp_path / "state.db", executor)
    item = api.start_orchestration(actor, "s1", "Make a draft", )
    pending = api.propose_action(actor, item.orchestration_id, "Exact proposal")
    completed = api.confirm_pending_action(actor, item.orchestration_id, pending.confirmation_key)
    assert completed.status is OrchestrationStatus.SUCCEEDED
    assert completed.result_reference == "result-1"
    assert len(executor.calls) == 1
    with pytest.raises(ValueError, match="no longer pending|awaiting confirmation"):
        api.confirm_pending_action(actor, item.orchestration_id, pending.confirmation_key)
    assert len(executor.calls) == 1


def test_missing_executor_fails_closed_and_cross_user_cannot_read_or_confirm(tmp_path, actor):
    api = service(tmp_path / "state.db")
    item = api.start_orchestration(actor, "s1", "Make a draft")
    pending = api.propose_action(actor, item.orchestration_id, "Write something")
    with pytest.raises(ValueError, match="no authorized executor"):
        api.confirm_pending_action(actor, item.orchestration_id, pending.confirmation_key)
    with pytest.raises(KeyError):
        api.get_orchestration_status(ActorContext("mallory"), item.orchestration_id)
    assert api.get_orchestration_status(actor, item.orchestration_id).status is OrchestrationStatus.AWAITING_CONFIRMATION


def test_proposal_revision_invalidates_old_confirmation_and_cancel_is_terminal(tmp_path, actor):
    api = service(tmp_path / "state.db")
    item = api.start_orchestration(actor, "s1", "Make a draft")
    first = api.propose_action(actor, item.orchestration_id, "proposal A")
    revised = api.revise_pending_action(actor, item.orchestration_id, "proposal B")
    assert revised.confirmation_key != first.confirmation_key
    with pytest.raises(ValueError, match="does not match"):
        api.confirm_pending_action(actor, item.orchestration_id, first.confirmation_key)
    api.cancel_pending_action(actor, item.orchestration_id)
    with pytest.raises(ValueError, match="cannot be cancelled"):
        api.cancel_pending_action(actor, item.orchestration_id)


def test_multiple_pending_operations_are_never_guessed(tmp_path, actor):
    api = service(tmp_path / "state.db")
    first = api.start_orchestration(actor, "s1", "First request", missing_fields=("x",))
    second = api.start_orchestration(actor, "s1", "Second request", missing_fields=("y",))
    with pytest.raises(ValueError, match="multiple pending"):
        api.get_pending_action(actor, "s1")
    assert first.orchestration_id != second.orchestration_id


def test_executor_failure_is_recorded_and_not_retried(tmp_path, actor):
    class Broken:
        def __init__(self): self.calls = 0
        def execute(self, **kwargs):
            self.calls += 1
            raise TimeoutError("result unknown")
    broken = Broken()
    api = service(tmp_path / "state.db", broken)
    item = api.start_orchestration(actor, "s1", "Make a draft")
    pending = api.propose_action(actor, item.orchestration_id, "Exact write")
    failed = api.confirm_pending_action(actor, item.orchestration_id, pending.confirmation_key)
    assert failed.status is OrchestrationStatus.FAILED
    assert failed.error_code == "TimeoutError"
    with pytest.raises(ValueError):
        api.confirm_pending_action(actor, item.orchestration_id, pending.confirmation_key)
    assert broken.calls == 1


def test_concurrent_confirmations_claim_one_execution(tmp_path, actor):
    entered, release = Event(), Event()
    class SlowExecutor:
        def __init__(self): self.calls = 0
        def execute(self, **kwargs):
            self.calls += 1
            entered.set()
            assert release.wait(5)
            return "once"
    executor = SlowExecutor()
    api = service(tmp_path / "state.db", executor)
    item = api.start_orchestration(actor, "s1", "Make a draft")
    pending = api.propose_action(actor, item.orchestration_id, "Exact proposal")
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(api.confirm_pending_action, actor, item.orchestration_id, pending.confirmation_key)
        assert entered.wait(5)
        with pytest.raises(ValueError, match="no longer pending|awaiting confirmation"):
            api.confirm_pending_action(actor, item.orchestration_id, pending.confirmation_key)
        release.set()
        assert future.result(timeout=5).status is OrchestrationStatus.SUCCEEDED
    assert executor.calls == 1


def test_query_does_not_mutate_state_and_unknown_id_is_hidden(tmp_path, actor):
    api = service(tmp_path / "state.db")
    item = api.start_orchestration(actor, "s1", "hello")
    before = api.get_orchestration_status(actor, item.orchestration_id)
    api.get_route_decision(actor, item.orchestration_id)
    after = api.get_orchestration_status(actor, item.orchestration_id)
    assert before == after
    with pytest.raises(KeyError):
        api.get_orchestration_status(actor, "missing")

from dataclasses import dataclass

import pytest

from app.chat import ActorContext, ChatService
from app.chat.contracts import ConversationContextSnapshot, ConversationMessage
from app.chat.repository import ChatRepository
from app.files import FileService
from app.orchestration.contracts import OrchestrationStatus
from app.suggestions import FollowUpSuggestionService
from app.suggestions.service import DeterministicSuggestionStrategy


class NoAnswer:
    def answer(self, **kwargs):
        return "Für eine Ausbildung können Deutschkenntnisse wichtig sein. Die konkreten Anforderungen hängen vom Beruf ab."


@dataclass(frozen=True)
class LatestState:
    status: OrchestrationStatus


class FakeOrchestrations:
    def __init__(self, status):
        self.status = status
        self.calls = 0

    def get_latest_orchestration(self, actor, session_id):
        self.calls += 1
        return LatestState(self.status) if self.status else None


def _conversation(tmp_path):
    chat = ChatService(ChatRepository(tmp_path / "chat.sqlite3"), NoAnswer(), FileService())
    actor = ActorContext("alice")
    session = chat.create_session(actor)
    chat.append_user_message(actor, session.id, "德国 Ausbildung 对德语水平有什么要求？")
    chat.append_assistant_message(actor, session.id, NoAnswer().answer())
    return chat, actor, session


def test_offline_recommendations_are_relevant_bounded_and_do_not_write(tmp_path):
    chat, actor, session = _conversation(tmp_path)
    before = [(item.id, item.title, item.updated_at) for item in chat.list_sessions(actor)]
    message_count = len(chat.get_messages(actor, session.id))

    suggestions = FollowUpSuggestionService(chat).get_follow_up_suggestions(actor, session.id)

    assert 1 <= len(suggestions) <= 3
    assert suggestions[0].category == "ausbildung"
    assert "B1" in suggestions[0].question
    assert all(item.question.endswith("？") for item in suggestions)
    assert len({item.question for item in suggestions}) == len(suggestions)
    assert [(item.id, item.title, item.updated_at) for item in chat.list_sessions(actor)] == before
    assert len(chat.get_messages(actor, session.id)) == message_count


def test_recommendations_use_public_bounded_context_and_honor_limit(tmp_path):
    chat, actor, session = _conversation(tmp_path)
    strategy = DeterministicSuggestionStrategy()
    service = FollowUpSuggestionService(chat, strategy=strategy)

    assert len(service.get_follow_up_suggestions(actor, session.id, maximum=1)) == 1
    assert service.get_follow_up_suggestions(actor, session.id, maximum=99).__len__() == 3
    assert service.get_follow_up_suggestions(actor, session.id, maximum=0) == ()


def test_long_context_is_clipped_before_strategy_receives_it():
    class LongConversationQuery:
        def get_context_snapshot(self, actor, session_id):
            return ConversationContextSnapshot(
                session_id=session_id,
                messages=(
                    ConversationMessage("u", session_id, "user", "Ausbildung " * 500, 1, "now"),
                    ConversationMessage("a", session_id, "assistant", "Ausbildung " * 1000, 2, "now"),
                ),
                character_budget=12_000, characters_used=15_000, truncated=True,
            )

    class RecordingStrategy:
        seen = None

        def suggest(self, question, answer, *, maximum):
            self.seen = (question, answer)
            return (("如何查询某岗位当前公布的德语要求？", "ausbildung"),)

    strategy = RecordingStrategy()
    actor = ActorContext("alice")
    suggestions = FollowUpSuggestionService(LongConversationQuery(), strategy=strategy).get_follow_up_suggestions(actor, "session")
    assert len(suggestions) == 1
    assert len(strategy.seen[0]) <= 1200
    assert len(strategy.seen[1]) <= 2400


def test_no_answer_and_unknown_topic_return_empty(tmp_path):
    chat = ChatService(ChatRepository(tmp_path / "chat.sqlite3"), NoAnswer(), FileService())
    actor = ActorContext("alice")
    session = chat.create_session(actor)
    service = FollowUpSuggestionService(chat)
    assert service.get_follow_up_suggestions(actor, session.id) == ()
    chat.append_user_message(actor, session.id, "What is the weather right now in Berlin?")
    chat.append_assistant_message(actor, session.id, "I cannot verify current weather in this offline answer.")
    assert service.get_follow_up_suggestions(actor, session.id) == ()


@pytest.mark.parametrize("status", [
    OrchestrationStatus.NEEDS_CLARIFICATION,
    OrchestrationStatus.AWAITING_CONFIRMATION,
    OrchestrationStatus.EXECUTING,
    OrchestrationStatus.UNCERTAIN,
])
def test_active_or_uncertain_orchestration_suppresses_suggestions(tmp_path, status):
    chat, actor, session = _conversation(tmp_path)
    m08 = FakeOrchestrations(status)
    assert FollowUpSuggestionService(chat, m08).get_follow_up_suggestions(actor, session.id) == ()
    assert m08.calls == 1


def test_foreign_actor_cannot_read_context_for_recommendations(tmp_path):
    chat, _, session = _conversation(tmp_path)
    with pytest.raises(KeyError):
        FollowUpSuggestionService(chat).get_follow_up_suggestions(ActorContext("bob"), session.id)


def test_duplicate_suggestions_are_removed_and_output_is_immutable(tmp_path):
    chat, actor, session = _conversation(tmp_path)

    class DuplicateStrategy:
        def suggest(self, question, answer, *, maximum):
            return (("B1 和 B2 有什么区别？", "ausbildung"), ("B1和B2有什么区别？", "ausbildung"))

    suggestions = FollowUpSuggestionService(chat, strategy=DuplicateStrategy()).get_follow_up_suggestions(actor, session.id)
    assert len(suggestions) == 1
    with pytest.raises((AttributeError, TypeError)):
        suggestions[0].question = "changed"

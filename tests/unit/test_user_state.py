"""02 tests/test_sqlite.py profile/event coverage adapted to 04's schema."""

from dataclasses import asdict
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.users.models import LearningEventIn, ProfileUpdate, UserState
from app.users.repository import UserStateRepository
from app.users.service import UserStateService


@pytest.fixture
def users(tmp_path: Path) -> UserStateService:
    return UserStateService(UserStateRepository(tmp_path / "users.db"))


def test_unknown_user_retains_empty_state_contract(users):
    assert users.get_user_state("missing") == UserState("missing", None, None, None, None)
    assert users.list_learning_events("missing") == []


def test_service_factory_owns_repository_construction(tmp_path: Path):
    service = UserStateService.from_path(tmp_path / "factory.db")
    saved = service.update_user_state("alice", current_level="A1")
    reopened = UserStateService.from_path(tmp_path / "factory.db")
    assert reopened.get_user_state("alice") == saved


def test_profile_fields_can_be_updated_independently(users):
    assert users.update_user_level("alice", " a1 ").current_level == "A1"
    assert users.update_target_level("alice", " b1 ").target_level == "B1"
    assert users.update_learning_goal("alice", " Use German at work ").learning_goal == "Use German at work"
    saved = users.update_learning_preferences("alice", " Simple examples ")
    assert saved == UserState("alice", "A1", "B1", "Use German at work", "Simple examples")
    assert users.get_user_state("alice") == saved


def test_partial_update_preserves_omitted_values_and_null_clears(users):
    users.update_user_state("alice", current_level="A1", target_level="B1", learning_goal="Work", learning_preferences="Audio")
    saved = users.update_user_state("alice", learning_goal=None)
    assert saved == UserState("alice", "A1", "B1", None, "Audio")
    users.update_user_state("alice", current_level=None, target_level=None, learning_preferences=None)
    assert users.get_user_state("alice") == UserState("alice", None, None, None, None)
    assert ProfileUpdate(target_level=None).model_dump(exclude_unset=True) == {"target_level": None}


@pytest.mark.parametrize("payload", [
    {}, {"unknown_field": "value"},
    {"current_level": "B9"}, {"target_level": " "}, {"current_level": 1},
    {"learning_goal": " "}, {"learning_preferences": ""},
    {"learning_goal": "x" * 2001}, {"learning_preferences": "x" * 2001},
    {"learning_goal": ["work"]}, {"learning_preferences": True},
])
def test_invalid_profile_updates_leave_saved_state_unchanged(users, payload):
    before = users.update_user_state("alice", current_level="A1", target_level="B1")
    with pytest.raises(ValidationError):
        users.update_user_state("alice", **payload)
    assert users.get_user_state("alice") == before


def test_profiles_and_events_survive_repository_reopen(users):
    profile = users.update_user_state("alice", current_level="A2", target_level="B2", learning_goal="Work", learning_preferences="Audio")
    event = users.save_learning_event("alice", "quiz_completed", "articles", "8/10")
    reopened = UserStateService(UserStateRepository(users.repository.path))
    assert reopened.get_user_state("alice") == profile
    assert reopened.list_learning_events("alice") == [event]
    assert event.id > 0 and event.created_at


def test_recent_events_are_sorted_limited_and_isolated(users):
    first = users.save_learning_event("alice", "quiz_completed", "articles", "8/10")
    second = users.save_learning_event("alice", "review", "Dativ")
    third = users.save_learning_event("alice", "review", "Akkusativ")
    other = users.save_learning_event("bob", "quiz_completed", "verbs", "10/10")
    # Explicit timestamps prove both sort keys without sleeping or a clock dependency.
    with users.repository._connection() as connection:
        connection.execute("UPDATE learning_events SET created_at=? WHERE id=?", ("2026-01-02 12:00:00", first.id))
        connection.execute("UPDATE learning_events SET created_at=? WHERE id IN (?,?)", ("2026-01-01 12:00:00", second.id, third.id))
    assert [event.id for event in users.list_learning_events("alice")] == [first.id, third.id, second.id]
    assert [event.id for event in users.list_learning_events("alice", limit=2)] == [first.id, third.id]
    assert users.list_learning_events("bob") == [other]
    assert users.list_learning_events("absent") == []


@pytest.mark.parametrize("limit", [0, -1, 101, True, 1.5, "2", None])
def test_invalid_event_limits_are_rejected(users, limit):
    with pytest.raises(ValueError, match="limit"):
        users.repository.list_events("alice", limit)


@pytest.mark.parametrize("payload", [
    {"event_type": "", "item": "Dativ"}, {"event_type": "review", "item": " "},
    {"event_type": "review", "item": "Dativ", "result": " "},
    {"event_type": "x" * 101, "item": "Dativ"}, {"event_type": "review", "item": "x" * 2001},
    {"event_type": "review", "item": "Dativ", "result": "x" * 2001},
    {"event_type": 2, "item": "Dativ"}, {"event_type": "review", "item": {"topic": "Dativ"}},
])
def test_invalid_events_do_not_write(users, payload):
    with pytest.raises(ValidationError):
        users.save_learning_event("alice", **payload)
    assert users.list_learning_events("alice") == []


def test_event_contract_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        LearningEventIn(event_type="review", item="Dativ", user_id="bob")
    with pytest.raises(ValidationError):
        ProfileUpdate(user_id="bob", current_level="A1")


def test_sql_like_values_are_literal_data_and_user_state_is_isolated(users):
    literal = "'; DROP TABLE learning_events; --"
    profile = users.update_user_state(literal, learning_goal=literal, learning_preferences=literal)
    event = users.save_learning_event(literal, "review", literal, literal)
    assert users.get_user_state(literal) == profile
    assert users.list_learning_events(literal) == [event]
    assert asdict(users.get_user_state("bob")) == asdict(UserState("bob", None, None, None, None))
    assert users.list_learning_events("bob") == []
    assert users.save_learning_event("bob", "review", "Dativ").user_id == "bob"


@pytest.mark.parametrize("user_id", ["", " ", None, 42])
def test_invalid_user_id_is_rejected_for_all_service_operations(users, user_id):
    for operation in (
        lambda: users.get_user_state(user_id),
        lambda: users.update_user_state(user_id, current_level="A1"),
        lambda: users.list_learning_events(user_id),
        lambda: users.save_learning_event(user_id, "review", "Dativ"),
    ):
        with pytest.raises(ValueError, match="user_id"):
            operation()

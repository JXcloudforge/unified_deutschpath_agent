from pathlib import Path

from .models import LearningEvent, LearningEventIn, ProfileUpdate, UserState
from .repository import UserStateRepository


class UserStateService:
    def __init__(self, repository: UserStateRepository) -> None:
        self.repository = repository

    @classmethod
    def from_path(cls, path: str | Path) -> "UserStateService":
        """Build the module's SQLite-backed service without exposing storage setup to callers."""
        return cls(UserStateRepository(path))

    def get_user_state(self, user_id: str) -> UserState:
        _require_user_id(user_id)
        return self.repository.get(user_id)

    def update_user_state(self, user_id: str, **values: str | None) -> UserState:
        _require_user_id(user_id)
        update = ProfileUpdate(**values)
        return self.repository.update(user_id, **update.model_dump(exclude_unset=True))

    def update_user_level(self, user_id: str, level: str | None) -> UserState:
        return self.update_user_state(user_id, current_level=level)

    def update_target_level(self, user_id: str, level: str | None) -> UserState:
        return self.update_user_state(user_id, target_level=level)

    def update_learning_goal(self, user_id: str, goal: str | None) -> UserState:
        return self.update_user_state(user_id, learning_goal=goal)

    def update_learning_preferences(self, user_id: str, preferences: str | None) -> UserState:
        return self.update_user_state(user_id, learning_preferences=preferences)

    def save_learning_event(self, user_id: str, event_type: str, item: str, result: str | None = None) -> LearningEvent:
        _require_user_id(user_id)
        event = LearningEventIn(event_type=event_type, item=item, result=result)
        return self.repository.add_event(user_id, **event.model_dump())

    def list_learning_events(self, user_id: str, limit: int = 20) -> list[LearningEvent]:
        _require_user_id(user_id)
        return self.repository.list_events(user_id, limit)


def _require_user_id(user_id: str) -> None:
    # Reused from 02 repository._require_text; keep 04's existing identity values.
    if not isinstance(user_id, str) or not user_id.strip():
        raise ValueError("user_id must be a non-empty string")

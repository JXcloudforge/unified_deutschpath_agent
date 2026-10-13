from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# Reused from 02_crm_agent/app/db/repository.py.
VALID_LEVELS = {"A1", "A2", "B1", "B2", "C1", "C2"}


@dataclass(frozen=True)
class UserState:
    user_id: str
    current_level: str | None
    target_level: str | None
    learning_goal: str | None
    learning_preferences: str | None


class ProfileUpdate(BaseModel):
    """Only supplied fields change; explicit null clears a saved field."""

    model_config = ConfigDict(extra="forbid", strict=True)

    current_level: str | None = None
    target_level: str | None = None
    learning_goal: str | None = Field(default=None, max_length=2000)
    learning_preferences: str | None = Field(default=None, max_length=2000)

    @field_validator("current_level", "target_level")
    @classmethod
    def normalize_level(cls, value: str | None) -> str | None:
        # Adapted from 02 CustomerRepository.update_target_level.
        if value is None:
            return None
        value = value.strip().upper()
        if value not in VALID_LEVELS:
            raise ValueError(f"level must be one of {sorted(VALID_LEVELS)}")
        return value

    @field_validator("learning_goal", "learning_preferences")
    @classmethod
    def require_non_blank(cls, value: str | None) -> str | None:
        # Adapted from 02 API request validation, retaining null clearing.
        if value is not None:
            value = value.strip()
            if not value:
                raise ValueError("must not be blank; use null to clear")
        return value

    @model_validator(mode="after")
    def require_update(self) -> "ProfileUpdate":
        if not self.model_fields_set:
            raise ValueError("at least one profile field is required")
        return self


@dataclass(frozen=True)
class LearningEvent:
    """02 LearningEvent adapted to 04's existing user_id and columns."""

    id: int
    user_id: str
    event_type: str
    item: str
    result: str | None
    created_at: str


class LearningEventIn(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    event_type: str = Field(min_length=1, max_length=100)
    item: str = Field(min_length=1, max_length=2000)
    result: str | None = Field(default=None, max_length=2000)

    @field_validator("event_type", "item", "result")
    @classmethod
    def require_non_blank(cls, value: str | None) -> str | None:
        if value is not None:
            value = value.strip()
            if not value:
                raise ValueError("must not be blank")
        return value

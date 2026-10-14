"""Public DTOs and interfaces for multi-turn task orchestration."""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from app.chat.contracts import ActorContext
from app.routing.models import Intent


class OrchestrationStatus(StrEnum):
    CREATED = "CREATED"
    NEEDS_CLARIFICATION = "NEEDS_CLARIFICATION"
    READY = "READY"
    AWAITING_CONFIRMATION = "AWAITING_CONFIRMATION"
    EXECUTING = "EXECUTING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    PARTIAL = "PARTIAL"
    UNCERTAIN = "UNCERTAIN"
    CANCELLED = "CANCELLED"


class StepStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    UNCERTAIN = "UNCERTAIN"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True, slots=True)
class OrchestrationStep:
    step_id: str
    action_type: str
    owner_module: str
    command_or_query: str
    parameters_json: str
    depends_on: tuple[str, ...]
    status: StepStatus
    result_reference: str | None
    error_code: str | None
    order_index: int


@dataclass(frozen=True, slots=True)
class Orchestration:
    orchestration_id: str
    actor_user_id: str
    session_id: str
    intent: str
    status: OrchestrationStatus
    original_input: str
    proposal: str | None
    missing_fields: tuple[str, ...]
    confirmation_key: str | None
    result_reference: str | None
    error_code: str | None
    recoverable: bool
    revision: int
    created_at: str
    updated_at: str
    steps: tuple[OrchestrationStep, ...] = ()


@dataclass(frozen=True, slots=True)
class RouteSnapshot:
    orchestration_id: str
    intent: Intent
    confidence: float
    reason: str
    query: str | None
    mixed_sources: bool


class OrchestrationCommands(Protocol):
    def start_orchestration(self, actor: ActorContext, session_id: str, user_input: str,
                            *, missing_fields: tuple[str, ...] = ()) -> Orchestration: ...
    def submit_clarification(self, actor: ActorContext, orchestration_id: str,
                             answer: str, *, missing_fields: tuple[str, ...]) -> Orchestration: ...
    def propose_action(self, actor: ActorContext, orchestration_id: str, proposal: str) -> Orchestration: ...
    def revise_pending_action(self, actor: ActorContext, orchestration_id: str, proposal: str) -> Orchestration: ...
    def confirm_pending_action(self, actor: ActorContext, orchestration_id: str,
                               confirmation_key: str) -> Orchestration: ...
    def resume_uncertain(self, actor: ActorContext, orchestration_id: str) -> Orchestration: ...
    def cancel_pending_action(self, actor: ActorContext, orchestration_id: str) -> Orchestration: ...
    def record_reconciled_success(self, actor: ActorContext, orchestration_id: str,
                                  result_reference: str) -> Orchestration: ...
    def mark_uncertain(self, actor: ActorContext, orchestration_id: str,
                       error_code: str = "EXECUTION_OUTCOME_UNKNOWN") -> Orchestration: ...


class OrchestrationQueries(Protocol):
    def get_orchestration_status(self, actor: ActorContext, orchestration_id: str) -> Orchestration: ...
    def get_pending_action(self, actor: ActorContext, session_id: str) -> Orchestration | None: ...
    def get_latest_orchestration(self, actor: ActorContext, session_id: str) -> Orchestration | None: ...
    def get_route_decision(self, actor: ActorContext, orchestration_id: str) -> RouteSnapshot: ...


class OrchestrationExecutor(Protocol):
    """Target-module adapter; implementations enforce authorization and idempotency."""

    def execute(self, *, actor: ActorContext, session_id: str, orchestration_id: str,
                idempotency_key: str, proposal: str) -> str: ...

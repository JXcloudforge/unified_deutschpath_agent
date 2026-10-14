"""M08 orchestration commands and queries; no business-module persistence access."""
from __future__ import annotations

import hashlib
import json
from uuid import uuid4

from app.chat.contracts import ActorContext, ConversationQueries
from app.routing import IntentRouter, RouteDecision, RoutingContext

from .contracts import Orchestration, OrchestrationExecutor, OrchestrationStatus, RouteSnapshot, StepStatus
from .repository import OrchestrationRepository
from .capabilities import CAPABILITIES


_TRANSITIONS = {
    OrchestrationStatus.NEEDS_CLARIFICATION: {OrchestrationStatus.NEEDS_CLARIFICATION, OrchestrationStatus.READY, OrchestrationStatus.CANCELLED},
    OrchestrationStatus.READY: {OrchestrationStatus.AWAITING_CONFIRMATION, OrchestrationStatus.CANCELLED},
    OrchestrationStatus.AWAITING_CONFIRMATION: {OrchestrationStatus.EXECUTING, OrchestrationStatus.CANCELLED},
    OrchestrationStatus.EXECUTING: {OrchestrationStatus.SUCCEEDED, OrchestrationStatus.FAILED, OrchestrationStatus.UNCERTAIN},
    OrchestrationStatus.UNCERTAIN: {OrchestrationStatus.SUCCEEDED},
}


class OrchestrationService:
    """Owns only orchestration state. Actual business writes require a registered executor."""
    def __init__(self, database_path, router: IntentRouter, conversations: ConversationQueries,
                 executors: dict[str, OrchestrationExecutor] | None = None) -> None:
        self._repository = OrchestrationRepository(database_path)
        self._router = router
        self._conversations = conversations
        self._executors = dict(executors or {})

    def start_orchestration(self, actor: ActorContext, session_id: str, user_input: str,
                            *, missing_fields: tuple[str, ...] = ()) -> Orchestration:
        if not user_input.strip():
            raise ValueError("user_input must not be blank")
        # Query enforces M07 session ownership; the bounded contents are not yet
        # consumed by a multi-turn planner (that capability remains blocked).
        self._conversations.get_context_snapshot(actor, session_id)
        decision = self._router.route(user_input.strip(), RoutingContext(has_session=True))
        status = OrchestrationStatus.NEEDS_CLARIFICATION if missing_fields else OrchestrationStatus.READY
        return self._repository.insert({
            "orchestration_id": uuid4().hex, "actor_user_id": actor.user_id, "session_id": session_id,
            "intent": decision.intent.value, "status": status.value, "original_input": user_input.strip(),
            "missing_fields": list(missing_fields), "route_confidence": decision.confidence,
            "route_reason": decision.reason, "route_query": decision.query,
            "mixed_sources": int(decision.mixed_sources),
        })

    def submit_clarification(self, actor: ActorContext, orchestration_id: str, answer: str,
                             *, missing_fields: tuple[str, ...]) -> Orchestration:
        row = self._owned(actor, orchestration_id)
        if row["status"] != OrchestrationStatus.NEEDS_CLARIFICATION.value:
            raise ValueError("orchestration is not awaiting clarification")
        if not answer.strip():
            raise ValueError("clarification answer must not be blank")
        # A new proposal revision automatically invalidates any older confirmation key.
        return self._dto(self._repository.update(
            actor.user_id, orchestration_id, expected=(OrchestrationStatus.NEEDS_CLARIFICATION.value,),
            status=(OrchestrationStatus.READY if not missing_fields else OrchestrationStatus.NEEDS_CLARIFICATION).value,
            proposal=f"{row['original_input']}\nClarification: {answer.strip()}",
            missing_fields=missing_fields, confirmation_key=None,
        ))

    def propose_action(self, actor: ActorContext, orchestration_id: str, proposal: str) -> Orchestration:
        row = self._owned(actor, orchestration_id)
        if row["status"] != OrchestrationStatus.READY.value:
            raise ValueError("orchestration is not ready for an action proposal")
        if not proposal.strip():
            raise ValueError("proposal must not be blank")
        revised = f"{proposal.strip()}\nrevision:{int(row['revision']) + 1}"
        key = hashlib.sha256(f"{orchestration_id}:{revised}".encode()).hexdigest()
        steps = self._canonical_steps(proposal, row)
        result = self._repository.update(
            actor.user_id, orchestration_id, expected=(OrchestrationStatus.READY.value,),
            status=OrchestrationStatus.AWAITING_CONFIRMATION.value, proposal=proposal.strip(),
            confirmation_key=key, steps=steps,
        )
        return self._dto(result)

    def revise_pending_action(self, actor: ActorContext, orchestration_id: str, proposal: str) -> Orchestration:
        row = self._owned(actor, orchestration_id)
        if row["status"] != OrchestrationStatus.AWAITING_CONFIRMATION.value:
            raise ValueError("orchestration is not awaiting confirmation")
        if not proposal.strip():
            raise ValueError("proposal must not be blank")
        revision = int(row["revision"]) + 1
        key = hashlib.sha256(f"{orchestration_id}:{revision}:{proposal.strip()}".encode()).hexdigest()
        steps = self._canonical_steps(proposal, row)
        result = self._repository.update(
            actor.user_id, orchestration_id,
            expected=(OrchestrationStatus.AWAITING_CONFIRMATION.value,),
            status=OrchestrationStatus.AWAITING_CONFIRMATION.value,
            proposal=proposal.strip(), confirmation_key=key, steps=steps,
        )
        return self._dto(result)

    def confirm_pending_action(self, actor: ActorContext, orchestration_id: str,
                               confirmation_key: str) -> Orchestration:
        row = self._owned(actor, orchestration_id)
        if row["status"] != OrchestrationStatus.AWAITING_CONFIRMATION.value:
            raise ValueError("operation is not awaiting confirmation")
        if not confirmation_key or confirmation_key != row["confirmation_key"]:
            raise ValueError("confirmation does not match the current proposal")
        steps = self._ensure_steps(row)
        if any(step.action_type not in self._executors for step in steps):
            raise ValueError("no authorized executor is registered for every planned step")
        # Claim the transition before invoking external code. Replays cannot execute twice.
        claimed = self._repository.update(actor.user_id, orchestration_id,
            expected=(OrchestrationStatus.AWAITING_CONFIRMATION.value,),
            status=OrchestrationStatus.EXECUTING.value, proposal=row["proposal"],
            confirmation_key=None, recoverable=False)
        return self._execute_pending_steps(actor, claimed, confirmation_key)

    def resume_uncertain(self, actor: ActorContext, orchestration_id: str) -> Orchestration:
        row = self._owned(actor, orchestration_id)
        if row["status"] != OrchestrationStatus.UNCERTAIN.value:
            raise ValueError("operation is not awaiting uncertainty recovery")
        steps = self._ensure_steps(row)
        uncertain = next((step for step in steps if step.status is StepStatus.UNCERTAIN), None)
        if uncertain is None and row["status"] == OrchestrationStatus.UNCERTAIN.value:
            # Upgrade a pre-step-table M08-B record conservatively: a write may
            # already have committed, so its first step must be reconciled.
            first = steps[0]
            if first.command_or_query == "Command":
                self._repository.update_step(orchestration_id, first.step_id,
                    expected=(StepStatus.PENDING.value,), status=StepStatus.UNCERTAIN.value,
                    error_code="LEGACY_OUTCOME_UNKNOWN")
                uncertain = self._repository.steps(orchestration_id)[0]
        if uncertain is not None:
            executor = self._executors.get(uncertain.action_type)
            if uncertain.command_or_query == "Query":
                # Read-only queries are safe to repeat after an interrupted response.
                try:
                    result = self._execute_step(actor, row, uncertain, orchestration_id)
                except Exception:
                    return self._dto(row)
            elif executor is not None and callable(getattr(executor, "reconcile", None)):
                try:
                    result = executor.reconcile(actor=actor, session_id=row["session_id"],
                        orchestration_id=orchestration_id, proposal=row["proposal"],
                        parameters=json.loads(uncertain.parameters_json))
                except Exception:
                    result = None
                if result is None:
                    return self._dto(row)
            else:
                return self._dto(row)
            self._repository.update_step(orchestration_id, uncertain.step_id,
                expected=(StepStatus.UNCERTAIN.value,), status=StepStatus.SUCCEEDED.value,
                result_reference=str(result))
        self._repository.update(actor.user_id, orchestration_id,
            expected=(OrchestrationStatus.UNCERTAIN.value,), status=OrchestrationStatus.EXECUTING.value,
            proposal=row["proposal"], confirmation_key=None, error_code=None, recoverable=False)
        return self._execute_pending_steps(actor, row, orchestration_id)

    def cancel_pending_action(self, actor: ActorContext, orchestration_id: str) -> Orchestration:
        row = self._owned(actor, orchestration_id)
        allowed = _TRANSITIONS.get(OrchestrationStatus(row["status"]), set())
        if OrchestrationStatus.CANCELLED not in allowed:
            raise ValueError("orchestration cannot be cancelled in its current state")
        cancelled = self._repository.update(actor.user_id, orchestration_id,
            expected=(row["status"],), status=OrchestrationStatus.CANCELLED.value,
            proposal=row["proposal"], confirmation_key=None, recoverable=False)
        for step in self._repository.steps(orchestration_id):
            if step.status is StepStatus.PENDING:
                self._repository.update_step(orchestration_id, step.step_id,
                    expected=(StepStatus.PENDING.value,), status=StepStatus.BLOCKED.value,
                    error_code="PLAN_CANCELLED")
        return self._dto(cancelled)

    def get_orchestration_status(self, actor: ActorContext, orchestration_id: str) -> Orchestration:
        return self._dto(self._owned(actor, orchestration_id))

    def get_pending_action(self, actor: ActorContext, session_id: str) -> Orchestration | None:
        rows = self._repository.pending(actor.user_id, session_id)
        if len(rows) > 1:
            raise ValueError("multiple pending operations require an explicit orchestration_id")
        return self._dto(rows[0]) if rows else None

    def get_latest_orchestration(self, actor: ActorContext, session_id: str) -> Orchestration | None:
        row = self._repository.latest(actor.user_id, session_id)
        return self._dto(row) if row else None

    def recover_interrupted_executions(self) -> int:
        """Fail closed on operations left in-flight when the local API process stopped."""
        return self._repository.recover_executing()

    def mark_uncertain(self, actor: ActorContext, orchestration_id: str,
                       error_code: str = "EXECUTION_OUTCOME_UNKNOWN") -> Orchestration:
        row = self._owned(actor, orchestration_id)
        if row["status"] not in {OrchestrationStatus.EXECUTING.value, OrchestrationStatus.UNCERTAIN.value}:
            raise ValueError("operation is not in an uncertain execution state")
        if row["status"] == OrchestrationStatus.UNCERTAIN.value:
            return self._dto(row)
        return self._dto(self._repository.update(actor.user_id, orchestration_id,
            expected=(OrchestrationStatus.EXECUTING.value,), status=OrchestrationStatus.UNCERTAIN.value,
            proposal=row["proposal"], confirmation_key=None, error_code=error_code, recoverable=False))

    def record_reconciled_success(self, actor: ActorContext, orchestration_id: str,
                                  result_reference: str) -> Orchestration:
        row = self._owned(actor, orchestration_id)
        return self._dto(self._repository.update(actor.user_id, orchestration_id,
            expected=(OrchestrationStatus.EXECUTING.value, OrchestrationStatus.UNCERTAIN.value),
            status=OrchestrationStatus.SUCCEEDED.value, proposal=row["proposal"],
            confirmation_key=None, result_reference=result_reference, recoverable=False))

    def get_route_decision(self, actor: ActorContext, orchestration_id: str) -> RouteSnapshot:
        row = self._owned(actor, orchestration_id)
        return RouteSnapshot(orchestration_id, self._router_intent(row["intent"]), row["route_confidence"],
                             row["route_reason"], row["route_query"], bool(row["mixed_sources"]))

    def _owned(self, actor: ActorContext, orchestration_id: str):
        row = self._repository.get(actor.user_id, orchestration_id)
        if row is None:
            raise KeyError("orchestration not found")
        return row

    def _canonical_steps(self, proposal: str, row) -> list[dict]:
        try:
            payload = json.loads(proposal)
        except (TypeError, json.JSONDecodeError):
            payload = {}
        raw_steps = payload.get("steps") if isinstance(payload, dict) else None
        if raw_steps is None:
            action_type = payload.get("action_type", row["intent"]) if isinstance(payload, dict) else row["intent"]
            raw_steps = [{"step_id": "step-1", "action_type": action_type,
                "owner_module": "Conversation" if action_type in {"rename_session", "list_sessions"} else "unknown",
                "command_or_query": "Command", "parameters": payload if isinstance(payload, dict) else {},
                "depends_on": []}]
        if not isinstance(raw_steps, list) or not 1 <= len(raw_steps) <= 4:
            raise ValueError("a plan must contain between one and four steps")
        capability_by_name = {capability.name: capability for capability in CAPABILITIES}
        normalized, known = [], set()
        for index, item in enumerate(raw_steps):
            if not isinstance(item, dict):
                raise ValueError("each plan step must be an object")
            step_id, action_type = item.get("step_id"), item.get("action_type")
            parameters, dependencies = item.get("parameters", {}), item.get("depends_on", [])
            if not isinstance(step_id, str) or not step_id or step_id in known:
                raise ValueError("plan step ids must be unique non-empty strings")
            if not isinstance(action_type, str) or not action_type:
                raise ValueError("plan step action_type is required")
            if (not isinstance(parameters, dict) or not isinstance(dependencies, list)
                    or any(not isinstance(dependency, str) for dependency in dependencies)):
                raise ValueError("step parameters and dependencies have invalid types")
            if any(dependency not in known for dependency in dependencies):
                raise ValueError("dependencies must refer only to earlier steps")
            operation = item.get("command_or_query", "Command")
            if operation not in {"Command", "Query"}:
                raise ValueError("command_or_query must be Command or Query")
            if isinstance(payload, dict) and "steps" in payload:
                capability = capability_by_name.get(action_type)
                if (capability is None or not capability.real_executor
                        or item.get("owner_module") != capability.owner_module
                        or operation != capability.operation):
                    raise ValueError(f"plan step is not an available public capability: {action_type}")
            normalized.append({"step_id": step_id, "action_type": action_type,
                "owner_module": str(item.get("owner_module", "unknown")),
                "command_or_query": operation, "parameters": parameters,
                "depends_on": dependencies})
            known.add(step_id)
        return normalized

    def _ensure_steps(self, row):
        steps = self._repository.steps(row["orchestration_id"])
        if not steps:
            self._repository.replace_steps(row["orchestration_id"], self._canonical_steps(row["proposal"] or "{}", row))
            steps = self._repository.steps(row["orchestration_id"])
        return steps

    def _execute_step(self, actor, plan_row, step, idempotency_key):
        executor = self._executors.get(step.action_type)
        if executor is None:
            raise ValueError(f"no executor registered for {step.action_type}")
        parameters = json.loads(step.parameters_json)
        try:
            original = json.loads(plan_row["proposal"] or "{}")
        except (TypeError, json.JSONDecodeError):
            original = {}
        if isinstance(original, dict) and isinstance(original.get("steps"), list):
            action_proposal = {"action_type": step.action_type, "session_id": plan_row["session_id"], **parameters}
            proposal = json.dumps(action_proposal, ensure_ascii=False, sort_keys=True)
        else:
            proposal = plan_row["proposal"]
        return executor.execute(actor=actor, session_id=plan_row["session_id"],
            orchestration_id=plan_row["orchestration_id"], idempotency_key=idempotency_key,
            proposal=proposal)

    def _execute_pending_steps(self, actor, plan_row, idempotency_key):
        plan_id = plan_row["orchestration_id"]
        prior_results = []
        for step in self._repository.steps(plan_id):
            if step.status is StepStatus.SUCCEEDED:
                prior_results.append(step.result_reference)
                continue
            if step.status is not StepStatus.PENDING:
                continue
            states = {item.step_id: item.status for item in self._repository.steps(plan_id)}
            if any(states.get(dep) is not StepStatus.SUCCEEDED for dep in step.depends_on):
                self._repository.update_step(plan_id, step.step_id, expected=(StepStatus.PENDING.value,),
                    status=StepStatus.BLOCKED.value, error_code="DEPENDENCY_NOT_SUCCEEDED")
                continue
            self._repository.update_step(plan_id, step.step_id,
                expected=(StepStatus.PENDING.value,), status=StepStatus.RUNNING.value)
            try:
                result = self._execute_step(actor, plan_row, step, idempotency_key)
            except ExecutionUncertainError:
                self._repository.update_step(plan_id, step.step_id,
                    expected=(StepStatus.RUNNING.value,), status=StepStatus.UNCERTAIN.value,
                    error_code="EXECUTION_OUTCOME_UNKNOWN")
                updated = self._repository.update(actor.user_id, plan_id,
                    expected=(OrchestrationStatus.EXECUTING.value,), status=OrchestrationStatus.UNCERTAIN.value,
                    proposal=plan_row["proposal"], error_code="EXECUTION_OUTCOME_UNKNOWN", recoverable=False)
                return self._dto(updated)
            except Exception as exc:
                self._repository.update_step(plan_id, step.step_id,
                    expected=(StepStatus.RUNNING.value,), status=StepStatus.FAILED.value,
                    error_code=type(exc).__name__)
                for later in self._repository.steps(plan_id):
                    if later.status is StepStatus.PENDING:
                        self._repository.update_step(plan_id, later.step_id,
                            expected=(StepStatus.PENDING.value,), status=StepStatus.BLOCKED.value,
                            error_code="EARLIER_STEP_FAILED")
                overall = OrchestrationStatus.PARTIAL if prior_results else OrchestrationStatus.FAILED
                updated = self._repository.update(actor.user_id, plan_id,
                    expected=(OrchestrationStatus.EXECUTING.value,), status=overall.value,
                    proposal=plan_row["proposal"], error_code=type(exc).__name__, recoverable=False)
                return self._dto(updated)
            self._repository.update_step(plan_id, step.step_id,
                expected=(StepStatus.RUNNING.value,), status=StepStatus.SUCCEEDED.value,
                result_reference=str(result))
            prior_results.append(str(result))
        completed_steps = self._repository.steps(plan_id)
        final_reference = (completed_steps[0].result_reference if len(completed_steps) == 1
                           else json.dumps(prior_results, ensure_ascii=False))
        final = self._repository.update(actor.user_id, plan_id,
            expected=(OrchestrationStatus.EXECUTING.value,), status=OrchestrationStatus.SUCCEEDED.value,
            proposal=plan_row["proposal"], result_reference=final_reference,
            recoverable=False)
        return self._dto(final)

    def _dto(self, row) -> Orchestration:
        return Orchestration(
            row["orchestration_id"], row["actor_user_id"], row["session_id"], row["intent"],
            OrchestrationStatus(row["status"]), row["original_input"], row["proposal"],
            tuple(json.loads(row["missing_fields_json"])), row["confirmation_key"],
            row["result_reference"],
            row["error_code"], bool(row["recoverable"]), int(row["revision"]),
            row["created_at"], row["updated_at"], self._repository.steps(row["orchestration_id"]),
        )

    @staticmethod
    def _router_intent(value):
        from app.routing import Intent
        return Intent(value)


class ExecutionUncertainError(RuntimeError):
    """Business call may have committed but its public Query could not verify it."""


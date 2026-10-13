from __future__ import annotations

from dataclasses import dataclass
from contextvars import ContextVar

from .llm_router import LLMIntentRouter, SemanticRoutingError
from .models import Intent, RouteDecision, RoutingContext
from .rules import RuleBasedIntentRouter, is_explicit_learning_knowledge_request, is_explicit_local_source_request, is_explicit_web_request


@dataclass(frozen=True)
class DecisionAudit:
    rule_intent: Intent
    rule_reason: str
    rule_confidence: float
    llm_invoked: bool
    llm_suggested_intent: Intent | None
    final_intent: Intent
    decision_source: str
    fallback_reason: str | None = None


class HybridIntentRouter:
    """Rules protect unambiguous/safety-critical requests; LLM resolves selected ambiguity only."""
    def __init__(self, rules: RuleBasedIntentRouter, semantic: LLMIntentRouter) -> None:
        self.rules, self.semantic = rules, semantic
        self._audit: ContextVar[DecisionAudit | None] = ContextVar("hybrid_router_audit", default=None)

    @property
    def last_audit(self) -> DecisionAudit | None:
        """Current execution-context audit for tests; never a shared request history."""
        return self._audit.get()

    def route(self, message: str, context: RoutingContext) -> RouteDecision:
        rule = self.rules.route(message, context)
        if self._is_protected(rule, message, context):
            self._audit.set(DecisionAudit(rule.intent, rule.reason, rule.confidence, False, None, rule.intent, "high_certainty_rule"))
            return rule
        try:
            decision = self.semantic.route(message, context)
        except SemanticRoutingError as exc:
            if is_explicit_web_request(message):
                decision = RouteDecision(Intent.WEB_SEARCH, 1.0, f"semantic fallback protects real-time request: {exc}", query=message)
                self._audit.set(DecisionAudit(rule.intent, rule.reason, rule.confidence, True, None, decision.intent, "safety_fallback", str(exc)))
                return decision
            decision = RouteDecision(rule.intent, rule.confidence, f"rule fallback after semantic failure: {exc}", query=rule.query, mixed_sources=rule.mixed_sources)
            self._audit.set(DecisionAudit(rule.intent, rule.reason, rule.confidence, True, None, decision.intent, "rule_fallback", str(exc)))
            return decision
        if is_explicit_web_request(message) and decision.intent is not Intent.WEB_SEARCH:
            decision = RouteDecision(Intent.WEB_SEARCH, 1.0, "rule safety override protects explicit real-time request", query=message,
                                 mixed_sources=context.has_attachment and rule.mixed_sources)
            self._audit.set(DecisionAudit(rule.intent, rule.reason, rule.confidence, True, decision.intent, decision.intent, "safety_override"))
            return decision
        self._audit.set(DecisionAudit(rule.intent, rule.reason, rule.confidence, True, decision.intent, decision.intent, "llm_override"))
        return decision

    @staticmethod
    def _is_protected(rule: RouteDecision, message: str, context: RoutingContext) -> bool:
        if is_explicit_web_request(message):
            return True
        if rule.intent is Intent.RAG and (context.has_attachment or is_explicit_local_source_request(message)):
            return True
        if rule.intent is Intent.RAG and is_explicit_learning_knowledge_request(message):
            return True
        if rule.intent is Intent.NO_TOOL and rule.confidence >= 0.9:
            return True
        return False

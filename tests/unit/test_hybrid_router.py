import json
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.llm import FakeLLM
from app.routing import HybridIntentRouter, Intent, LLMIntentRouter, RoutingContext, RuleBasedIntentRouter
from app.routing.llm_router import SemanticRoutingError


class SpyLLM(FakeLLM):
    def __init__(self, response):
        super().__init__(response)
        self.calls = 0

    def answer(self, prompt):
        self.calls += 1
        return super().answer(prompt)


def semantic(intent, *, mixed=False):
    return json.dumps({"intent": intent, "mixed_sources": mixed, "confidence": 0.8, "reason": "semantic classification"})


def test_protected_translation_attachment_and_web_do_not_need_semantic_llm():
    llm = SpyLLM(semantic("rag"))
    router = HybridIntentRouter(RuleBasedIntentRouter(), LLMIntentRouter(llm))
    assert router.route("Translate this into German", RoutingContext()).intent is Intent.NO_TOOL
    assert router.route("summarize attachment", RoutingContext(has_attachment=True)).intent is Intent.RAG
    assert router.route("今天柏林天气怎么样？", RoutingContext()).intent is Intent.WEB_SEARCH
    assert llm.calls == 0


def test_high_certainty_generation_rule_does_not_need_semantic_override():
    llm = SpyLLM(semantic("no_tool"))
    router = HybridIntentRouter(RuleBasedIntentRouter(), LLMIntentRouter(llm))
    assert router.route("给我一个德语自我介绍模板", RoutingContext()).intent is Intent.NO_TOOL
    assert llm.calls == 0 and router.last_audit.decision_source == "high_certainty_rule"


def test_named_local_material_and_clear_learning_explanation_are_protected():
    llm = SpyLLM(semantic("no_tool"))
    router = HybridIntentRouter(RuleBasedIntentRouter(), LLMIntentRouter(llm))
    assert router.route("Find the phrase in the attached markdown", RoutingContext()).intent is Intent.RAG
    assert router.route("解释德语从句语序", RoutingContext()).intent is Intent.RAG
    assert llm.calls == 0


@pytest.mark.parametrize("response", ["not json", semantic("unknown"), json.dumps({"intent": "rag"})])
def test_invalid_semantic_output_falls_back_without_executing_untrusted_text(response):
    router = HybridIntentRouter(RuleBasedIntentRouter(), LLMIntentRouter(SpyLLM(response), retries=0))
    decision = router.route("Information about Germany", RoutingContext())
    assert decision.intent is Intent.RAG and "fallback" in decision.reason


def test_explicit_web_request_is_safe_when_semantic_classifier_fails():
    class FailingSemantic:
        def route(self, message, context):
            raise SemanticRoutingError("timeout")

    router = HybridIntentRouter(RuleBasedIntentRouter(), FailingSemantic())
    assert router.route("请联网查今天柏林天气", RoutingContext()).intent is Intent.WEB_SEARCH


def test_mixed_sources_is_preserved_by_rule_protection():
    router = HybridIntentRouter(RuleBasedIntentRouter(), LLMIntentRouter(SpyLLM(semantic("no_tool"))))
    decision = router.route("比较上传附件与网上最新签证政策", RoutingContext(has_attachment=True))
    assert decision.intent is Intent.WEB_SEARCH and decision.mixed_sources is True


def test_semantic_timeout_is_controlled_and_falls_back_to_rules():
    class SlowLLM:
        def answer(self, prompt):
            time.sleep(0.01)
            return semantic("no_tool")

    router = HybridIntentRouter(RuleBasedIntentRouter(), LLMIntentRouter(SlowLLM(), retries=0, timeout_seconds=0.001))
    decision = router.route("Information about Germany", RoutingContext())
    assert decision.intent is Intent.RAG and "fallback" in decision.reason


def test_semantic_request_failure_records_latency_without_exposing_provider_details():
    class FailedRequest:
        def answer(self, prompt):
            raise RuntimeError("private transport diagnostic")

    semantic_router = LLMIntentRouter(FailedRequest(), retries=0)
    with pytest.raises(SemanticRoutingError, match="request failed") as error:
        semantic_router.route("Information about Germany", RoutingContext())
    report = semantic_router.metrics.report()
    assert report["calls"] == report["failures"] == 1
    assert report["average_ms"] >= 0 and report["p95_ms"] >= 0
    assert report["estimated_cost_usd"] is None
    assert len(semantic_router.metrics.durations_ms) == 1
    assert "private transport diagnostic" not in str(error.value)


def test_decision_audit_exposes_no_user_message_and_records_rule_path():
    router = HybridIntentRouter(RuleBasedIntentRouter(), LLMIntentRouter(SpyLLM(semantic("rag"))))
    router.route("Translate this private sentence", RoutingContext())
    audit = router.last_audit
    assert audit is not None and audit.decision_source == "high_certainty_rule"
    assert audit.llm_invoked is False and not hasattr(audit, "message")


def test_decision_audit_is_isolated_between_concurrent_execution_contexts():
    router = HybridIntentRouter(RuleBasedIntentRouter(), LLMIntentRouter(SpyLLM(semantic("rag"))))

    def route_and_read(message):
        router.route(message, RoutingContext())
        return router.last_audit.final_intent

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(route_and_read, ["Translate this", "今天柏林天气怎么样？"]))
    assert results == [Intent.NO_TOOL, Intent.WEB_SEARCH]

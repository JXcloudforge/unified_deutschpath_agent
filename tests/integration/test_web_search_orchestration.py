from types import SimpleNamespace

from app.agent import UnifiedOrchestrator
from app.llm import FakeLLM
from app.rag.context_builder import ContextBuilder
from app.routing import Intent, RouteDecision
from app.web import FakeWebSearchProvider, WebSearchResponse, WebSearchResult, WebSearchServiceError


class SpyRag:
    def __init__(self):
        self.context_builder = ContextBuilder()
        self.search_calls = []

    def search(self, *args):
        self.search_calls.append(args)
        return []

    def context_for_session(self, *args):
        self.search_calls.append(args)
        return ""


class FakeUsers:
    def get_user_state(self, user_id):
        return SimpleNamespace(current_level="A2", target_level="B1", learning_goal=None, learning_preferences=None)


class FixedRouter:
    def __init__(self, intent, *, mixed_sources=False, query="latest Berlin weather"):
        self.decision = RouteDecision(intent, 1.0, "test", query=query, mixed_sources=mixed_sources)

    def route(self, message, context):
        return self.decision


def test_web_search_calls_provider_passes_evidence_to_llm_and_keeps_actual_urls():
    result = WebSearchResult("Berlin Weather", "https://weather.example.test/berlin", "Clear skies", "2026-10-10")
    provider, llm, rag = FakeWebSearchProvider(WebSearchResponse("seed", (result,))), FakeLLM("It is clear."), SpyRag()
    answer = UnifiedOrchestrator(rag, FakeUsers(), llm, router=FixedRouter(Intent.WEB_SEARCH), web_search=provider).answer(user_id="u", message="What's the latest weather?")
    assert provider.calls and provider.calls[0][0] == "latest Berlin weather"
    assert rag.search_calls == []
    assert "Berlin Weather" in llm.last_prompt and "Clear skies" in llm.last_prompt and result.url in llm.last_prompt
    assert answer.endswith(f"Sources:\n- {result.url}")


def test_rag_and_no_tool_routes_do_not_call_web_provider():
    provider = FakeWebSearchProvider()
    rag, llm = SpyRag(), FakeLLM("answer")
    UnifiedOrchestrator(rag, FakeUsers(), llm, router=FixedRouter(Intent.RAG), web_search=provider).answer(user_id="u", message="Dativ")
    UnifiedOrchestrator(rag, FakeUsers(), llm, router=FixedRouter(Intent.NO_TOOL), web_search=provider).answer(user_id="u", message="Hello")
    assert provider.calls == []


def test_web_provider_failure_and_empty_results_are_not_presented_as_success():
    failed = FakeWebSearchProvider(error=WebSearchServiceError("service unavailable"))
    llm, rag = FakeLLM("invented"), SpyRag()
    answer = UnifiedOrchestrator(rag, FakeUsers(), llm, router=FixedRouter(Intent.WEB_SEARCH), web_search=failed).answer(user_id="u", message="latest news")
    assert "实时网页搜索失败" in answer and llm.last_prompt == ""
    empty = FakeWebSearchProvider(WebSearchResponse("seed", ()))
    answer = UnifiedOrchestrator(rag, FakeUsers(), llm, router=FixedRouter(Intent.WEB_SEARCH), web_search=empty).answer(user_id="u", message="latest news")
    assert answer == "实时网页搜索未找到可用结果。"


def test_sensitive_web_query_is_stopped_before_provider_and_llm():
    provider, llm, rag = FakeWebSearchProvider(), FakeLLM("invented"), SpyRag()
    answer = UnifiedOrchestrator(rag, FakeUsers(), llm, router=FixedRouter(Intent.WEB_SEARCH, query=None), web_search=provider).answer(
        user_id="u", message="最新政策，请联系 alice@example.com"
    )
    assert "实时网页搜索失败" in answer
    assert provider.calls == [] and llm.last_prompt == "" and rag.search_calls == []

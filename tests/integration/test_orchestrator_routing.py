from types import SimpleNamespace

from app.agent import UnifiedOrchestrator
from app.llm import FakeLLM
from app.rag.context_builder import ContextBuilder
from app.routing import Intent, RouteDecision
from app.schemas import ParsedDocument


class SpyRag:
    def __init__(self) -> None:
        self.context_builder = ContextBuilder()
        self.search_calls = []
        self.session_calls = []
        self.index_calls = []

    def search(self, namespace, query, top_k=4):
        self.search_calls.append((namespace, query, top_k))
        return []

    def context_for_session(self, session_id, query, top_k=4):
        self.session_calls.append((session_id, query, top_k))
        return ""

    def index_documents(self, namespace, documents):
        self.index_calls.append((namespace, documents))
        return 0


class FakeUsers:
    def get_user_state(self, user_id):
        return SimpleNamespace(current_level="A2", target_level="B1", learning_goal=None, learning_preferences=None)


class FixedRouter:
    def __init__(self, decision):
        self.decision = decision
        self.calls = []

    def route(self, message, context):
        self.calls.append((message, context))
        return self.decision


def test_rag_route_reuses_existing_knowledge_search_path():
    rag, llm = SpyRag(), FakeLLM("answer")
    router = FixedRouter(RouteDecision(Intent.RAG, 1.0, "test"))
    UnifiedOrchestrator(rag, FakeUsers(), llm, router=router).answer(user_id="u", message="Explain Dativ")
    assert rag.search_calls == [("knowledge:german", "Explain Dativ", 4)]
    assert llm.last_prompt


def test_no_tool_route_skips_rag_and_keeps_history():
    rag, llm = SpyRag(), FakeLLM("answer")
    router = FixedRouter(RouteDecision(Intent.NO_TOOL, 1.0, "test"))
    UnifiedOrchestrator(rag, FakeUsers(), llm, router=router).answer(user_id="u", message="Hello", history=[{"role": "user", "content": "Earlier context"}])
    assert rag.search_calls == [] and rag.session_calls == []
    assert "Earlier context" in llm.last_prompt


def test_web_route_never_calls_rag_llm_or_network():
    rag, llm = SpyRag(), FakeLLM("answer")
    router = FixedRouter(RouteDecision(Intent.WEB_SEARCH, 1.0, "test", query="latest weather"))
    answer = UnifiedOrchestrator(rag, FakeUsers(), llm, router=router).answer(user_id="u", message="latest weather")
    assert "实时网页搜索失败" in answer
    assert rag.search_calls == [] and rag.session_calls == [] and llm.last_prompt == ""


def test_attachment_rag_route_keeps_direct_prompt_without_knowledge_search():
    rag, llm = SpyRag(), FakeLLM("answer")
    router = FixedRouter(RouteDecision(Intent.RAG, 1.0, "attachment"))
    UnifiedOrchestrator(rag, FakeUsers(), llm, router=router).answer(user_id="u", message="Summarize", session_id="s", attachment=ParsedDocument("note.txt", "txt", "DIRECT_ROUTE_SECRET", {}))
    assert "DIRECT_ROUTE_SECRET" in llm.last_prompt
    assert rag.search_calls == [] and rag.session_calls == []


def test_router_failure_has_safe_fallback_and_preserves_web_safety():
    class FailingRouter:
        def route(self, message, context):
            raise RuntimeError("router unavailable")

    rag, llm = SpyRag(), FakeLLM("answer")
    orchestrator = UnifiedOrchestrator(rag, FakeUsers(), llm, router=FailingRouter())
    assert "实时网页搜索失败" in orchestrator.answer(user_id="u", message="今天柏林天气怎么样？")
    assert llm.last_prompt == "" and rag.search_calls == []
    assert orchestrator.answer(user_id="u", message="Hello") == "answer"
    assert rag.search_calls == []

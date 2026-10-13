from pathlib import Path

import pytest

from app.agent import UnifiedOrchestrator
from app.llm import FakeLLM
from app.rag import DeterministicEmbedding, RAGService
from app.rag.vector_store import ChromaVectorStore
from app.schemas import ParsedDocument
from app.users import UserStateRepository, UserStateService


def services(tmp_path: Path):
    rag = RAGService(ChromaVectorStore(tmp_path / "chroma", DeterministicEmbedding()))
    users = UserStateService(UserStateRepository(tmp_path / "state.db"))
    llm = FakeLLM("answer")
    return rag, users, llm


def test_index_search_and_namespace_isolation(tmp_path: Path):
    rag, _, _ = services(tmp_path)
    rag.index_documents("knowledge:german", [ParsedDocument("dativ.txt", "txt", "mit requires Dativ", {})])
    rag.index_documents("session:one", [ParsedDocument("private.txt", "txt", "secret attachment answer", {})])
    assert rag.search("knowledge:german", "Dativ", 1)[0].metadata["filename"] == "dativ.txt"
    assert rag.search("session:two", "secret attachment", 1) == []
    assert rag.search("session:one", "secret attachment", 1)[0].metadata["filename"] == "private.txt"


def test_direct_attachment_is_injected_into_prompt(tmp_path: Path):
    rag, users, llm = services(tmp_path)
    agent = UnifiedOrchestrator(rag, users, llm)
    agent.answer(user_id="u", message="Summarize", attachment=ParsedDocument("lesson.txt", "txt", "Direct attachment evidence", {}))
    assert "Direct attachment evidence" in llm.last_prompt


def test_user_state_persists(tmp_path: Path):
    _, users, _ = services(tmp_path)
    users.update_user_level("u", "B1")
    users.update_target_level("u", "B2")
    assert users.get_user_state("u").target_level == "B2"


@pytest.mark.parametrize("message,uses_rag", [("Hello", False), ("请解释德语 Dativ，并给出简单例句。", True)])
def test_latest_profile_reaches_prompt_and_stays_user_isolated(tmp_path: Path, message: str, uses_rag: bool):
    """Observe the existing FakeLLM prompt boundary and real RAG path."""
    rag, users, llm = services(tmp_path)
    try:
        rag.index_documents("knowledge:german", [ParsedDocument("dativ.txt", "txt", "Dativ evidence B2_CONTEXT", {})])
        agent = UnifiedOrchestrator(rag, users, llm)
        users.update_user_state("alice", current_level="A1", target_level="B1",
                                learning_goal="ALICE_GOAL", learning_preferences="ALICE_SIMPLE_EXAMPLES")
        users.update_user_state("bob", current_level="C1", target_level="C2",
                                learning_goal="BOB_GOAL", learning_preferences="BOB_ADVANCED")
        assert agent.answer(user_id="alice", message=message) == "answer"
        assert "current_level=A1; target_level=B1" in llm.last_prompt
        assert "ALICE_GOAL" in llm.last_prompt and "ALICE_SIMPLE_EXAMPLES" in llm.last_prompt
        assert "BOB_" not in llm.last_prompt
        assert ("B2_CONTEXT" in llm.last_prompt) is uses_rag
        UserStateService(UserStateRepository(tmp_path / "state.db")).update_user_state(
            "alice", current_level="A2", learning_goal="ALICE_NEW_GOAL")
        agent.answer(user_id="alice", message=message)
        assert "current_level=A2; target_level=B1" in llm.last_prompt
        assert "ALICE_NEW_GOAL" in llm.last_prompt and "goal=ALICE_GOAL;" not in llm.last_prompt
        agent.answer(user_id="bob", message=message)
        assert "current_level=C1; target_level=C2" in llm.last_prompt
        assert "BOB_GOAL" in llm.last_prompt and "ALICE_" not in llm.last_prompt
    finally:
        rag.store.close()

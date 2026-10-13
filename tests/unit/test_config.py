from pathlib import Path

import pytest

from app import config
from app.llm.client import DeepSeekLLM, FakeLLM, build_llm
import app.rag.embeddings as embeddings


@pytest.fixture
def clean_provider_environment(monkeypatch):
    keys = ("DEEPSEEK_API_KEY", "STAGE2_EMBEDDING_PROVIDER")
    for key in keys:
        monkeypatch.delenv(key, raising=False)
    yield
    for key in keys:
        monkeypatch.delenv(key, raising=False)


def test_no_api_key_uses_offline_provider(clean_provider_environment):
    assert isinstance(build_llm(), FakeLLM)


def test_project_dotenv_enables_deepseek_without_printing_secret(tmp_path: Path, clean_provider_environment):
    env_file = tmp_path / ".env"
    env_file.write_text("DEEPSEEK_API_KEY=dotenv-test-key\n", encoding="utf-8")
    config.load_project_env(env_file)
    provider = build_llm()
    assert isinstance(provider, DeepSeekLLM)
    # The test verifies provider selection only; it deliberately does not log or print the value.


def test_system_environment_overrides_dotenv(tmp_path: Path, monkeypatch, clean_provider_environment):
    env_file = tmp_path / ".env"
    env_file.write_text("DEEPSEEK_API_KEY=dotenv-test-key\n", encoding="utf-8")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "system-test-key")
    config.load_project_env(env_file)
    assert isinstance(build_llm(), DeepSeekLLM)
    assert build_llm().api_key == "system-test-key"


def test_embedding_provider_loads_from_dotenv(tmp_path: Path, monkeypatch, clean_provider_environment):
    class E5Stub:
        pass

    env_file = tmp_path / ".env"
    env_file.write_text("STAGE2_EMBEDDING_PROVIDER=e5\n", encoding="utf-8")
    monkeypatch.setattr(embeddings, "MultilingualE5Embedding", E5Stub)
    config.load_project_env(env_file)
    assert isinstance(embeddings.build_embedding(), E5Stub)

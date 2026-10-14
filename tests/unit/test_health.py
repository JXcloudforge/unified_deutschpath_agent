import importlib
import sys

import pytest


@pytest.fixture
def api_main(tmp_path, monkeypatch):
    monkeypatch.setenv("STAGE2_DATA_PATH", str(tmp_path / "api-runtime"))
    sys.modules.pop("app.api.main", None)
    module = importlib.import_module("app.api.main")
    yield module
    module.rag.store.close()


def test_health_reports_actual_router_and_web_configuration_without_secrets(api_main, monkeypatch):
    monkeypatch.setattr(api_main, "router_mode", "rules")
    monkeypatch.setattr(api_main, "router", api_main.RuleBasedIntentRouter())
    response = api_main.health()
    assert response["router"] == "rules"
    assert response["router_configured_mode"] == "rules"
    assert response["router_initialized"] is True
    assert response["web_search"] == "not_configured"
    assert response["web_provider_initialized"] is True
    assert response["tavily_api_key_configured"] is False
    assert response["tavily_connectivity"] == "not_tested"
    assert response["llm_provider"] in {"FakeLLM", "DeepSeekLLM"}
    assert response["deepseek_api_key_configured"] is False
    assert "llm_model" in response
    assert "deepseek_config_source" in response
    assert "api_key" not in response


def test_health_identifies_hybrid_mode_and_never_equates_key_with_connectivity(api_main, monkeypatch):
    monkeypatch.setattr(api_main, "router_mode", "hybrid")
    monkeypatch.setattr(api_main, "router", api_main.HybridIntentRouter(api_main.RuleBasedIntentRouter(), api_main.LLMIntentRouter(api_main.llm)))
    monkeypatch.setattr(api_main.web_search, "api_key", "health-test-secret")
    response = api_main.health()
    assert response["router"] == "hybrid"
    assert response["router_initialized"] is True
    assert response["web_search"] == "configured"
    assert response["tavily_api_key_configured"] is True
    assert response["tavily_connectivity"] == "not_tested"
    assert "health-test-secret" not in repr(response)

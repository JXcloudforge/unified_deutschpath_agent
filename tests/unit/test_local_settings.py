import pytest

from ui import local_settings


def test_missing_env_is_reported_without_exposing_values(tmp_path, monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setattr(local_settings, "PROCESS_ENV_AT_LOAD", frozenset())
    env_file = tmp_path / ".env"
    status = local_settings.credential_status("DEEPSEEK_API_KEY", env_file)
    assert status == {"configured": False, "source": "not configured", "process_override": False}
    assert local_settings.test_deepseek_connection(env_file=env_file)["status"] == "NOT TESTED"


def test_process_environment_has_precedence_over_dotenv(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("TAVILY_API_KEY=dotenv-secret-value\n", encoding="utf-8")
    monkeypatch.setattr(local_settings, "PROCESS_ENV_AT_LOAD", frozenset({"TAVILY_API_KEY"}))
    monkeypatch.setenv("TAVILY_API_KEY", "process-secret-value")
    assert local_settings.effective_value("TAVILY_API_KEY", env_file) == "process-secret-value"
    assert local_settings.credential_status("TAVILY_API_KEY", env_file) == {
        "configured": True, "source": "process environment", "process_override": True,
    }


def test_save_creates_from_template_and_replaces_only_requested_key(tmp_path):
    env_file, template = tmp_path / ".env", tmp_path / ".env.example"
    template.write_text("DEEPSEEK_API_KEY=\nDEEPSEEK_MODEL=deepseek-chat\nTAVILY_API_KEY=\n", encoding="utf-8")
    local_settings.save_credential("DEEPSEEK_API_KEY", "deepseek-test-key-123", env_file=env_file, template_file=template)
    first = env_file.read_text(encoding="utf-8")
    assert 'DEEPSEEK_API_KEY="deepseek-test-key-123"' in first
    assert "DEEPSEEK_MODEL=deepseek-chat" in first
    assert "TAVILY_API_KEY=" in first
    local_settings.save_credential("DEEPSEEK_API_KEY", "replacement-key-456", env_file=env_file, template_file=template)
    second = env_file.read_text(encoding="utf-8")
    assert second.count("DEEPSEEK_API_KEY=") == 1
    assert "replacement-key-456" in second
    assert "deepseek-test-key-123" not in second


def test_invalid_or_non_allowlisted_key_does_not_modify_existing_file(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("TAVILY_API_KEY=valid-existing-key\nOTHER=value\n", encoding="utf-8")
    before = env_file.read_bytes()
    with pytest.raises(ValueError):
        local_settings.save_credential("TAVILY_API_KEY", "invalid\nINJECTED=value", env_file=env_file)
    with pytest.raises(ValueError):
        local_settings.save_credential("UNRELATED_SECRET", "valid-new-key", env_file=env_file)
    assert env_file.read_bytes() == before


def test_secret_status_never_returns_secret_and_deepseek_test_without_key_is_not_tested(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("DEEPSEEK_API_KEY=some-test-secret\n", encoding="utf-8")
    monkeypatch.setattr(local_settings, "PROCESS_ENV_AT_LOAD", frozenset())
    status = local_settings.credential_status("DEEPSEEK_API_KEY", env_file)
    assert status["configured"] is True
    assert status["source"] == ".env"
    assert "some-test-secret" not in repr(status)


def test_tavily_without_key_is_not_tested(tmp_path, monkeypatch):
    monkeypatch.setattr(local_settings, "PROCESS_ENV_AT_LOAD", frozenset())
    result = local_settings.test_tavily_connection(env_file=tmp_path / ".env")
    assert result == {"status": "NOT TESTED", "message": "未配置 Tavily API Key。", "result_count": 0}


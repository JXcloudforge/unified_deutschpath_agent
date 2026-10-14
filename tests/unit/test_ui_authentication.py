from ui.authentication import (
    access_token_from_user,
    identity_cache_scope,
    oidc_configuration_ready,
    production_api_origin_ready,
)


def _secrets():
    return {
        "auth": {
            "redirect_uri": "https://login.deutschpath.test/oauth2callback",
            "cookie_secret": "x" * 48,
            "expose_tokens": "access",
            "auth0": {
                "client_id": "real-client-id",
                "client_secret": "real-client-secret",
                "server_metadata_url": "https://tenant.deutschpath.test/.well-known/openid-configuration",
                "client_kwargs": {"scope": "openid profile email", "audience": "https://api.deutschpath.test"},
            },
        }
    }


def test_oidc_configuration_requires_https_and_api_access_token_exposure():
    assert oidc_configuration_ready(_secrets(), "auth0", production=True)
    secrets = _secrets()
    secrets["auth"]["expose_tokens"] = "id"
    assert not oidc_configuration_ready(secrets, "auth0", production=True)
    secrets = _secrets()
    secrets["auth"]["redirect_uri"] = "http://login.deutschpath.test/oauth2callback"
    assert not oidc_configuration_ready(secrets, "auth0", production=True)


def test_oidc_configuration_rejects_placeholders_and_missing_audience():
    secrets = _secrets()
    secrets["auth"]["auth0"]["client_secret"] = "REPLACE_ME"
    assert not oidc_configuration_ready(secrets, "auth0", production=True)
    secrets = _secrets()
    secrets["auth"]["auth0"]["client_kwargs"] = {"scope": "openid"}
    assert not oidc_configuration_ready(secrets, "auth0", production=True)


def test_access_token_is_available_only_for_logged_in_user():
    class User:
        is_logged_in = True
        tokens = {"access": "api-access-token"}

    assert access_token_from_user(User()) == "api-access-token"
    User.is_logged_in = False
    assert access_token_from_user(User()) is None


def test_cache_scope_is_stable_per_issuer_and_subject_and_changes_between_users():
    alice = {"iss": "https://issuer/", "sub": "alice"}
    assert identity_cache_scope(alice) == identity_cache_scope(alice)
    assert identity_cache_scope(alice) != identity_cache_scope({"iss": "https://issuer/", "sub": "bob"})
    assert identity_cache_scope(alice) != identity_cache_scope({"iss": "https://other/", "sub": "alice"})


def test_production_api_origin_only_allows_tls_or_fixed_compose_service():
    assert production_api_origin_ready("https://api.deutschpath.test")
    assert production_api_origin_ready("http://api:8765")
    assert not production_api_origin_ready("http://127.0.0.1:8765")
    assert not production_api_origin_ready("http://attacker.invalid:8765")


def test_production_streamlit_fails_closed_without_oidc_configuration(monkeypatch):
    from pathlib import Path
    from streamlit.testing.v1 import AppTest

    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("DEUTSCHPATH_API_PRIVATE_NETWORK", raising=False)
    app = AppTest.from_file(str(Path(__file__).parents[2] / "ui" / "streamlit_app.py")).run()
    assert any("生产登录尚未配置完整" in item.value for item in app.error)
    assert not app.text_input
    assert not app.chat_input

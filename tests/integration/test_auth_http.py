from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from importlib import import_module

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from fastapi.routing import APIRoute

from app.auth.identity import IdentityMappingService
from app.auth.service import AuthService
from app.auth.verifier import OIDCAccessTokenVerifier


@dataclass
class SigningKey:
    key: object


class Resolver:
    def __init__(self, key): self.key = key
    def get_signing_key_from_jwt(self, _token): return SigningKey(self.key)


def _token(private, subject):
    now = datetime.now(timezone.utc)
    return jwt.encode({
        "iss": "https://id.example",
        "sub": subject,
        "aud": "deutschpath-api",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=5)).timestamp()),
        "scope": "chat:access",
    }, private, algorithm="RS256", headers={"typ": "at+jwt", "kid": "test"})


def test_private_http_routes_require_verified_identity_and_isolate_users(tmp_path, monkeypatch):
    api = import_module("app.api.main")
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    monkeypatch.setattr(api, "APP_ENV", "production")
    monkeypatch.setattr(api, "auth_service", AuthService(
        OIDCAccessTokenVerifier("https://id.example", "deutschpath-api", Resolver(private.public_key())),
        IdentityMappingService.from_path(tmp_path / "identities.sqlite3"),
    ))
    monkeypatch.setattr(api, "auth_service_error", None)
    alice = {"Authorization": f"Bearer {_token(private, 'alice')}", "X-User-ID": "bob"}
    bob = {"Authorization": f"Bearer {_token(private, 'bob')}"}

    with TestClient(api.app) as client:
        assert client.get("/users/me/state", headers={"X-User-ID": "alice"}).status_code == 401
        assert client.post("/sessions", headers={"X-User-ID": "alice"}).status_code == 401
        created = client.post("/sessions", headers=alice)
        assert created.status_code == 200
        session_id = created.json()["id"]
        assert len(client.get("/sessions", headers=alice).json()) == 1
        assert client.get("/sessions", headers=bob).json() == []
        assert client.get(f"/sessions/{session_id}/messages", headers=bob).status_code == 404
        assert client.patch(f"/sessions/{session_id}", headers=alice,
                            json={"title": "Verified"}).status_code == 200
        # An invalid bearer must never fall back to a simultaneously supplied header.
        assert client.get("/sessions", headers={"Authorization": "Bearer invalid", "X-User-ID": "alice"}).status_code == 401
        assert client.get("/health").status_code == 200


def test_all_non_health_http_routes_require_actor_dependency():
    api = import_module("app.api.main")

    def contains_actor_dependency(dependant):
        return any(
            dependency.call is api.get_actor_context or contains_actor_dependency(dependency)
            for dependency in dependant.dependencies
        )

    private = [route for route in api.app.routes if isinstance(route, APIRoute) and route.path != "/health"]
    assert private
    assert all(contains_actor_dependency(route.dependant) for route in private)


def test_production_bearer_fails_closed_when_oidc_is_unconfigured(monkeypatch):
    api = import_module("app.api.main")
    monkeypatch.setattr(api, "APP_ENV", "production")
    monkeypatch.setattr(api, "auth_service", None)
    monkeypatch.setattr(api, "auth_service_error", None)
    for name in ("OIDC_ISSUER", "OIDC_AUDIENCE", "OIDC_JWKS_URL"):
        monkeypatch.delenv(name, raising=False)
    with TestClient(api.app) as client:
        response = client.get("/sessions", headers={"Authorization": "Bearer syntactically-present"})
    assert response.status_code == 503

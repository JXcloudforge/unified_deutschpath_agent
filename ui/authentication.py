"""Small, transport-neutral helpers for the Streamlit OIDC boundary."""

from __future__ import annotations

from collections.abc import Mapping
import hashlib
from urllib.parse import urlparse


def oidc_configuration_ready(secrets: Mapping, provider: str, *, production: bool) -> bool:
    """Check required secrets without returning or logging any credential values."""
    auth = secrets.get("auth")
    if not isinstance(auth, Mapping):
        return False
    shared_required = ("redirect_uri", "cookie_secret")
    if any(not _configured(auth.get(name)) for name in shared_required):
        return False
    if not _exposes_access_token(auth.get("expose_tokens")):
        return False
    redirect_uri = auth.get("redirect_uri")
    if not isinstance(redirect_uri, str) or not redirect_uri.rstrip("/").endswith("/oauth2callback"):
        return False
    if production and not redirect_uri.startswith("https://"):
        return False
    cookie_secret = auth.get("cookie_secret")
    if not isinstance(cookie_secret, str) or len(cookie_secret) < 32 or _is_placeholder(cookie_secret):
        return False

    provider_config = auth.get(provider)
    if not isinstance(provider_config, Mapping):
        return False
    for name in ("client_id", "client_secret", "server_metadata_url"):
        if not _configured(provider_config.get(name)) or _is_placeholder(str(provider_config[name])):
            return False
    metadata_url = provider_config.get("server_metadata_url")
    if not isinstance(metadata_url, str) or not metadata_url.startswith("https://"):
        return False
    client_kwargs = provider_config.get("client_kwargs", {})
    # The API audience must be explicitly requested. The API remains the final
    # authority and verifies aud/signature/issuer/expiry on every request.
    if not isinstance(client_kwargs, Mapping) or not any(
        _configured(client_kwargs.get(name)) for name in ("audience", "resource")
    ):
        return False
    return True


def access_token_from_user(user: object) -> str | None:
    """Return the explicitly exposed access token only for a logged-in user."""
    try:
        if getattr(user, "is_logged_in") is not True:
            return None
        tokens = getattr(user, "tokens")
        token = tokens.get("access") if hasattr(tokens, "get") else tokens["access"]
    except (AttributeError, KeyError, TypeError):
        return None
    return token if isinstance(token, str) and token.strip() else None


def identity_cache_scope(user: object) -> str | None:
    """Hash verified OIDC subject claims for UI cache separation only.

    This value is never used for API authorization or sent as an identity.
    """
    try:
        issuer = getattr(user, "iss")
        subject = getattr(user, "sub")
    except AttributeError:
        try:
            issuer, subject = user["iss"], user["sub"]  # type: ignore[index]
        except (KeyError, TypeError):
            return None
    if not isinstance(issuer, str) or not issuer or not isinstance(subject, str) or not subject:
        return None
    return hashlib.sha256(f"{issuer}\0{subject}".encode("utf-8")).hexdigest()


def production_api_origin_ready(base_url: str) -> bool:
    """Require TLS except for the fixed, non-published Compose API service."""
    try:
        parsed = urlparse(base_url)
        port = parsed.port
    except ValueError:
        return False
    if parsed.scheme == "https" and parsed.hostname and parsed.username is None and parsed.password is None:
        return True
    return (
        parsed.scheme == "http"
        and parsed.hostname == "api"
        and port == 8765
        and not parsed.username
        and not parsed.password
        and parsed.path in {"", "/"}
    )


def _configured(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_placeholder(value: str) -> bool:
    upper = value.strip().upper()
    return any(marker in upper for marker in ("REPLACE", "YOUR_", "EXAMPLE", "<", ">"))


def _exposes_access_token(value: object) -> bool:
    if isinstance(value, str):
        return value == "access"
    return isinstance(value, (tuple, list)) and "access" in value

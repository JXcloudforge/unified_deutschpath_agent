"""Authentication facade that verifies credentials before identity mapping."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Protocol
from urllib.parse import urlparse

from .contracts import ActorContext
from .identity import IdentityMappingService
from .verifier import OIDCAccessTokenVerifier


class AuthConfigurationError(RuntimeError):
    pass


class AccessTokenVerifier(Protocol):
    def verify(self, token: str): ...


@dataclass(frozen=True, slots=True)
class OIDCSettings:
    issuer: str
    audience: str
    jwks_url: str
    identity_database: Path

    @classmethod
    def from_environment(cls, default_data_root: Path) -> OIDCSettings | None:
        names = ("OIDC_ISSUER", "OIDC_AUDIENCE", "OIDC_JWKS_URL")
        values = {name: os.getenv(name, "").strip() for name in names}
        if not any(values.values()):
            return None
        missing = [name for name, value in values.items() if not value]
        if missing:
            raise AuthConfigurationError("OIDC configuration is incomplete")
        issuer = values["OIDC_ISSUER"]
        if urlparse(issuer).scheme != "https":
            raise AuthConfigurationError("OIDC issuer must use HTTPS")
        raw_path = os.getenv("AUTH_DATABASE_PATH", "").strip()
        database = Path(raw_path) if raw_path else default_data_root / "identity.sqlite3"
        if not database.is_absolute():
            database = default_data_root / database
        return cls(issuer, values["OIDC_AUDIENCE"], values["OIDC_JWKS_URL"], database.resolve())


class AuthService:
    def __init__(self, verifier: AccessTokenVerifier, identities: IdentityMappingService) -> None:
        self._verifier = verifier
        self._identities = identities

    @classmethod
    def from_settings(cls, settings: OIDCSettings) -> AuthService:
        verifier = OIDCAccessTokenVerifier.from_jwks_url(
            settings.issuer, settings.audience, settings.jwks_url
        )
        identities = IdentityMappingService.from_path(settings.identity_database)
        return cls(verifier, identities)

    def authenticate(self, access_token: str) -> ActorContext:
        principal = self._verifier.verify(access_token)
        identity = self._identities.resolve_or_create_identity(principal)
        return ActorContext.from_verified_identity(
            user_id=identity.user_id,
            issuer=identity.issuer,
            subject=identity.subject,
            roles=identity.roles,
        )

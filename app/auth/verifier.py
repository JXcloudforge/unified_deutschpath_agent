"""OIDC-compatible JWT access-token verification using PyJWT/JWKS."""

from __future__ import annotations

from typing import Protocol
from urllib.parse import urlparse

import jwt

from .contracts import VerifiedPrincipal


class AccessTokenError(ValueError):
    """A token is invalid or is not an API access token."""


class SigningKeyResolver(Protocol):
    def get_signing_key_from_jwt(self, token: str): ...


class OIDCAccessTokenVerifier:
    """Verify signature, issuer, API audience, expiry, subject and token use."""

    ALLOWED_ALGORITHMS = ("RS256", "ES256")

    def __init__(self, issuer: str, audience: str, key_resolver: SigningKeyResolver) -> None:
        # OIDC issuer identifiers are exact strings; trailing slash is significant.
        self.issuer = issuer
        self.audience = audience
        self._key_resolver = key_resolver

    @classmethod
    def from_jwks_url(cls, issuer: str, audience: str, jwks_url: str) -> OIDCAccessTokenVerifier:
        parsed = urlparse(jwks_url)
        if parsed.scheme != "https" or not parsed.hostname:
            raise ValueError("OIDC JWKS URL must use HTTPS")
        resolver = jwt.PyJWKClient(jwks_url, cache_jwk_set=True, timeout=5)
        return cls(issuer, audience, resolver)

    def verify(self, token: str) -> VerifiedPrincipal:
        if not isinstance(token, str) or not token or len(token) > 32_768:
            raise AccessTokenError("invalid access token")
        try:
            header = jwt.get_unverified_header(token)
            signing_key = self._key_resolver.get_signing_key_from_jwt(token).key
            claims = jwt.decode(
                token,
                signing_key,
                algorithms=list(self.ALLOWED_ALGORITHMS),
                audience=self.audience,
                issuer=self.issuer,
                leeway=30,
                options={"require": ["iss", "sub", "aud", "exp"]},
            )
        except Exception as exc:
            # Never expose provider responses, tokens, or cryptographic details at
            # the HTTP boundary. The caller maps this to a generic 401 response.
            raise AccessTokenError("invalid access token") from exc

        issuer = claims.get("iss")
        subject = claims.get("sub")
        expires_at = claims.get("exp")
        if not isinstance(issuer, str) or not issuer or not isinstance(subject, str) or not subject:
            raise AccessTokenError("invalid access token")
        if isinstance(expires_at, bool) or not isinstance(expires_at, int):
            raise AccessTokenError("invalid access token")

        # API audience alone is not enough if an operator accidentally configures
        # the OIDC client ID. Require a signed access-token marker as well.
        token_type = str(header.get("typ", "")).casefold()
        token_use = str(claims.get("token_use", "")).casefold()
        scopes = _extract_scopes(claims)
        if token_type not in {"at+jwt", "application/at+jwt"} and token_use != "access" and not scopes:
            raise AccessTokenError("token is not marked for API access")

        return VerifiedPrincipal(issuer=issuer, subject=subject, expires_at=expires_at, scopes=scopes)


def _extract_scopes(claims: dict) -> tuple[str, ...]:
    value = claims.get("scope", claims.get("scp", ()))
    if isinstance(value, str):
        return tuple(sorted({scope for scope in value.split() if scope}))
    if isinstance(value, (list, tuple)) and all(isinstance(item, str) for item in value):
        return tuple(sorted({scope for item in value for scope in item.split() if scope}))
    return ()

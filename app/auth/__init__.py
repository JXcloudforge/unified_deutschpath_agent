"""Public Auth contracts and service facade."""

from .contracts import ActorContext, IdentityCommands, IdentityQueries, IdentityRecord, VerifiedPrincipal
from .identity import IdentityAccessDenied, IdentityDisabledError, IdentityMappingService
from .service import AuthConfigurationError, AuthService, OIDCSettings
from .verifier import AccessTokenError, OIDCAccessTokenVerifier

__all__ = [
    "AccessTokenError", "ActorContext", "AuthConfigurationError", "AuthService",
    "IdentityAccessDenied", "IdentityCommands", "IdentityDisabledError",
    "IdentityMappingService", "IdentityQueries", "IdentityRecord", "OIDCAccessTokenVerifier",
    "OIDCSettings", "VerifiedPrincipal",
]

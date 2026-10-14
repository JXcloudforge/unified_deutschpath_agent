"""Transport-neutral public authentication and identity DTOs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class ActorContext:
    """Server-resolved actor passed to business module Commands and Queries.

    Local-header actors exist only for loopback development. Production API
    dependencies create authenticated actors after token verification and
    issuer/subject mapping.
    """

    user_id: str
    identity_source: str = "caller_supplied_x_user_id"
    authenticated: bool = False
    roles: tuple[str, ...] = ()
    issuer: str | None = None
    subject: str | None = None

    def __post_init__(self) -> None:
        user_id = self.user_id.strip() if isinstance(self.user_id, str) else ""
        if not user_id:
            raise ValueError("actor user_id must not be blank")
        if self.authenticated and (not self.issuer or not self.subject):
            raise ValueError("authenticated actors require verified issuer and subject")
        object.__setattr__(self, "user_id", user_id)
        object.__setattr__(self, "roles", tuple(sorted(set(self.roles))))

    @classmethod
    def from_local_header(cls, user_id: str) -> ActorContext:
        """Create an explicitly untrusted local-beta namespace actor."""
        return cls(user_id=user_id)

    @classmethod
    def from_verified_identity(
        cls, *, user_id: str, issuer: str, subject: str, roles: tuple[str, ...]
    ) -> ActorContext:
        """Create an actor from Auth-owned verified and mapped identity data."""
        return cls(
            user_id=user_id,
            identity_source="oidc_access_token",
            authenticated=True,
            roles=roles,
            issuer=issuer,
            subject=subject,
        )


@dataclass(frozen=True, slots=True)
class VerifiedPrincipal:
    """Minimal verified token claims; never contains the raw token."""

    issuer: str
    subject: str
    expires_at: int
    scopes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class IdentityRecord:
    user_id: str
    issuer: str
    subject: str
    enabled: bool
    roles: tuple[str, ...]
    created_at: str


class IdentityQueries(Protocol):
    def get_identity(self, actor: ActorContext, user_id: str) -> IdentityRecord: ...


class IdentityCommands(Protocol):
    def resolve_or_create_identity(self, principal: VerifiedPrincipal) -> IdentityRecord: ...

    def set_identity_enabled(self, actor: ActorContext, user_id: str, enabled: bool) -> IdentityRecord: ...

    def set_identity_roles(self, actor: ActorContext, user_id: str, roles: tuple[str, ...]) -> IdentityRecord: ...

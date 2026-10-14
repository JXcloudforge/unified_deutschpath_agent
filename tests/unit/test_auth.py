from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from app.auth.contracts import ActorContext, VerifiedPrincipal
from app.auth.identity import IdentityAccessDenied, IdentityDisabledError, IdentityMappingService
from app.auth.identity import IdentityMappingRepository
from app.auth.verifier import AccessTokenError, OIDCAccessTokenVerifier


@dataclass
class SigningKey:
    key: object


class Resolver:
    def __init__(self, key):
        self.key = key

    def get_signing_key_from_jwt(self, _token):
        return SigningKey(self.key)


@pytest.fixture
def keypair():
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return private, private.public_key()


def issue(private, *, issuer="https://issuer.example", audience="deutschpath-api",
          exp=None, scope="chat:read", sub="subject-1", typ="at+jwt"):
    now = datetime.now(timezone.utc)
    return jwt.encode({
        "iss": issuer,
        "sub": sub,
        "aud": audience,
        "iat": int(now.timestamp()),
        "exp": int((exp or now + timedelta(minutes=10)).timestamp()),
        "scope": scope,
    }, private, algorithm="RS256", headers={"typ": typ, "kid": "test-key"})


def test_access_token_verifier_checks_signature_issuer_audience_and_expiry(keypair):
    private, public = keypair
    verifier = OIDCAccessTokenVerifier("https://issuer.example", "deutschpath-api", Resolver(public))
    principal = verifier.verify(issue(private))
    assert principal == VerifiedPrincipal("https://issuer.example", "subject-1", principal.expires_at, ("chat:read",))

    for token in (
        issue(private, exp=datetime.now(timezone.utc) - timedelta(minutes=1)),
        issue(private, issuer="https://wrong.example"),
        issue(private, issuer="https://issuer.example/"),
        issue(private, audience="other-api"),
        issue(private, scope="", typ="JWT"),
    ):
        with pytest.raises(AccessTokenError):
            verifier.verify(token)

    other_private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    with pytest.raises(AccessTokenError):
        verifier.verify(issue(other_private))


def test_identity_mapping_is_stable_and_issuer_scoped_across_restart(tmp_path):
    path = tmp_path / "auth" / "identity.sqlite3"
    repo = IdentityMappingRepository(path)
    one = VerifiedPrincipal("https://issuer-a", "same-sub", 2000)
    first = repo.resolve_or_create(one)
    second = IdentityMappingRepository(path).resolve_or_create(one)
    other_issuer = repo.resolve_or_create(VerifiedPrincipal("https://issuer-b", "same-sub", 2000))
    other_subject = repo.resolve_or_create(VerifiedPrincipal("https://issuer-a", "different-sub", 2000))
    assert first.user_id == second.user_id
    assert len({first.user_id, other_issuer.user_id, other_subject.user_id}) == 3
    assert first.roles == ("member",)


def test_disabled_identity_and_admin_managed_roles_are_enforced(tmp_path):
    service = IdentityMappingService.from_path(tmp_path / "identity.sqlite3")
    member = service.resolve_or_create_identity(VerifiedPrincipal("https://i", "member", 2000))
    untrusted_admin = ActorContext.from_verified_identity(
        user_id=member.user_id, issuer="https://i", subject="member", roles=("member",)
    )
    with pytest.raises(IdentityAccessDenied):
        service.set_identity_roles(untrusted_admin, member.user_id, ("admin",))

    admin = ActorContext.from_verified_identity(
        user_id="server-admin", issuer="https://i", subject="admin", roles=("admin",)
    )
    changed = service.set_identity_roles(admin, member.user_id, ("member", "admin"))
    assert changed.roles == ("admin", "member")
    service.set_identity_enabled(admin, member.user_id, False)
    with pytest.raises(IdentityDisabledError):
        service.resolve_or_create_identity(VerifiedPrincipal("https://i", "member", 3000))

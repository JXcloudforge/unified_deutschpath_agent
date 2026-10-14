"""Auth-owned issuer/subject mapping and account state in isolated SQLite."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

from .contracts import ActorContext, IdentityRecord, VerifiedPrincipal


class IdentityDisabledError(PermissionError):
    """The verified identity is disabled by the service owner."""


class IdentityAccessDenied(PermissionError):
    """The caller cannot administer or inspect the requested identity."""


class IdentityMappingRepository:
    """Private Auth persistence; callers receive DTOs, never rows or SQL."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS identity_mappings (
                issuer TEXT NOT NULL,
                subject TEXT NOT NULL,
                user_id TEXT NOT NULL UNIQUE,
                enabled INTEGER NOT NULL DEFAULT 1 CHECK(enabled IN (0,1)),
                roles_json TEXT NOT NULL DEFAULT '[\"member\"]',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY(issuer, subject)
            )""")

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("BEGIN IMMEDIATE")
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def _record(row: sqlite3.Row) -> IdentityRecord:
        return IdentityRecord(
            user_id=row["user_id"], issuer=row["issuer"], subject=row["subject"],
            enabled=bool(row["enabled"]), roles=tuple(json.loads(row["roles_json"])),
            created_at=row["created_at"],
        )

    def resolve_or_create(self, principal: VerifiedPrincipal) -> IdentityRecord:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM identity_mappings WHERE issuer=? AND subject=?",
                (principal.issuer, principal.subject),
            ).fetchone()
            if row is None:
                conn.execute(
                    "INSERT INTO identity_mappings(issuer,subject,user_id) VALUES(?,?,?)",
                    (principal.issuer, principal.subject, str(uuid4())),
                )
                row = conn.execute(
                    "SELECT * FROM identity_mappings WHERE issuer=? AND subject=?",
                    (principal.issuer, principal.subject),
                ).fetchone()
            if row is None:
                raise RuntimeError("identity mapping could not be read after creation")
            record = self._record(row)
            if not record.enabled:
                raise IdentityDisabledError("identity is disabled")
            return record

    def get(self, user_id: str) -> IdentityRecord | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM identity_mappings WHERE user_id=?", (user_id,)).fetchone()
            return self._record(row) if row else None

    def update_enabled(self, user_id: str, enabled: bool) -> IdentityRecord:
        with self._connect() as conn:
            changed = conn.execute(
                "UPDATE identity_mappings SET enabled=? WHERE user_id=?",
                (int(enabled), user_id),
            ).rowcount
            if changed != 1:
                raise KeyError("Identity not found")
            row = conn.execute("SELECT * FROM identity_mappings WHERE user_id=?", (user_id,)).fetchone()
            return self._record(row)

    def update_roles(self, user_id: str, roles: tuple[str, ...]) -> IdentityRecord:
        with self._connect() as conn:
            changed = conn.execute(
                "UPDATE identity_mappings SET roles_json=? WHERE user_id=?",
                (json.dumps(roles), user_id),
            ).rowcount
            if changed != 1:
                raise KeyError("Identity not found")
            row = conn.execute("SELECT * FROM identity_mappings WHERE user_id=?", (user_id,)).fetchone()
            return self._record(row)


class IdentityMappingService:
    """Auth public Commands/Queries; role and status writes stay server-side."""

    ALLOWED_ROLES = frozenset({"member", "admin"})

    def __init__(self, repository: IdentityMappingRepository) -> None:
        self._repository = repository

    @classmethod
    def from_path(cls, path: str | Path) -> IdentityMappingService:
        return cls(IdentityMappingRepository(path))

    def resolve_or_create_identity(self, principal: VerifiedPrincipal) -> IdentityRecord:
        return self._repository.resolve_or_create(principal)

    def get_identity(self, actor: ActorContext, user_id: str) -> IdentityRecord:
        if actor.user_id != user_id and "admin" not in actor.roles:
            raise IdentityAccessDenied("identity access denied")
        record = self._repository.get(user_id)
        if record is None:
            raise KeyError("Identity not found")
        return record

    def set_identity_enabled(self, actor: ActorContext, user_id: str, enabled: bool) -> IdentityRecord:
        self._require_admin(actor)
        return self._repository.update_enabled(user_id, bool(enabled))

    def set_identity_roles(self, actor: ActorContext, user_id: str, roles: tuple[str, ...]) -> IdentityRecord:
        self._require_admin(actor)
        normalized = tuple(sorted(set(roles)))
        if not normalized or not set(normalized) <= self.ALLOWED_ROLES:
            raise ValueError("roles must be a non-empty subset of the server role catalog")
        return self._repository.update_roles(user_id, normalized)

    @staticmethod
    def _require_admin(actor: ActorContext) -> None:
        if not actor.authenticated or "admin" not in actor.roles:
            raise IdentityAccessDenied("identity administration requires an authenticated admin")

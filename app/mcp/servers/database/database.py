"""Constrained SQLite operations for the Database MCP server.

The business database is intentionally separate from Stage 2's chat/CRM and
Chroma stores. MCP inputs never contain a file path or SQL statement.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import secrets
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from app.config import PROJECT_ROOT


_TABLE_RE = re.compile(r"^biz_[a-z][a-z0-9_]{0,35}$")
_COLUMN_RE = re.compile(r"^[a-z][a-z0-9_]{0,39}$")
_OPERATION_RE = re.compile(r"^[A-Za-z0-9_-]{8,100}$")
_COLUMN_TYPES = {"TEXT", "INTEGER", "REAL", "BOOLEAN"}
_FILTER_OPERATORS = {"eq": "=", "ne": "!=", "lt": "<", "lte": "<=", "gt": ">", "gte": ">="}
_MAX_COLUMNS = 20
_MAX_ROWS = 50
_MAX_RESULT_ROWS = 100
_MAX_TEXT_LENGTH = 4000
_APPROVAL_TTL_SECONDS = 300
_INTERNAL_COLUMNS = {"_mcp_operation_id", "_mcp_operation_digest"}


class DatabaseMCPError(ValueError):
    """A safe, user-correctable database request error."""


def _database_path(path: str | Path | None = None) -> Path:
    """Resolve the dedicated business DB and reject Stage 2 storage collisions."""
    raw = path if path is not None else os.getenv("MCP_DATABASE_PATH")
    stage_root_raw = os.getenv("STAGE2_DATA_PATH")
    stage_root = Path(stage_root_raw) if stage_root_raw else PROJECT_ROOT / "data"
    if not stage_root.is_absolute():
        stage_root = PROJECT_ROOT / stage_root
    stage_root = stage_root.resolve()
    if raw is None or str(raw).strip() == "":
        resolved = stage_root / "mcp_business.sqlite3"
    else:
        candidate = Path(raw).expanduser()
        if not candidate.is_absolute():
            candidate = PROJECT_ROOT / candidate
        resolved = candidate.resolve()

    stage_db = (stage_root / "stage2.db").resolve()
    chroma_root = (stage_root / "chroma").resolve()
    if resolved == stage_db or _is_within(resolved, chroma_root):
        raise DatabaseMCPError("MCP database path conflicts with protected application data")
    if resolved.exists() and resolved.is_dir():
        raise DatabaseMCPError("MCP database path must be a file path")
    return resolved


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _validate_table(table: str) -> str:
    if not isinstance(table, str) or not _TABLE_RE.fullmatch(table):
        raise DatabaseMCPError("table must use the biz_ prefix and lowercase identifier format")
    return table


def _validate_column(column: str) -> str:
    if not isinstance(column, str) or not _COLUMN_RE.fullmatch(column):
        raise DatabaseMCPError("invalid column name")
    if column.startswith("sqlite_") or column in _INTERNAL_COLUMNS:
        raise DatabaseMCPError("reserved column name")
    return column


def _identifier(value: str) -> str:
    # Callers must validate identifiers before using this quoting helper.
    return '"' + value.replace('"', '""') + '"'


def _connect(path: Path, *, readonly: bool = False) -> sqlite3.Connection:
    if readonly:
        if not path.is_file():
            raise DatabaseMCPError("business database is not initialized")
        uri = path.as_uri() + "?mode=ro"
        conn = sqlite3.connect(uri, uri=True, timeout=2.0)
        conn.set_authorizer(_readonly_authorizer)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path, timeout=2.0)
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def _managed_connection(path: Path, *, readonly: bool = False):
    """Commit/rollback the operation and always release the SQLite handle."""
    conn = _connect(path, readonly=readonly)
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def _readonly_authorizer(action: int, arg1: str | None, arg2: str | None, *_: Any) -> int:
    denied = {
        sqlite3.SQLITE_CREATE_INDEX, sqlite3.SQLITE_CREATE_TABLE,
        sqlite3.SQLITE_CREATE_TEMP_INDEX, sqlite3.SQLITE_CREATE_TEMP_TABLE,
        sqlite3.SQLITE_CREATE_TEMP_TRIGGER, sqlite3.SQLITE_CREATE_TEMP_VIEW,
        sqlite3.SQLITE_CREATE_TRIGGER, sqlite3.SQLITE_CREATE_VIEW,
        sqlite3.SQLITE_DELETE, sqlite3.SQLITE_DROP_INDEX,
        sqlite3.SQLITE_DROP_TABLE, sqlite3.SQLITE_DROP_TEMP_INDEX,
        sqlite3.SQLITE_DROP_TEMP_TABLE, sqlite3.SQLITE_DROP_TEMP_TRIGGER,
        sqlite3.SQLITE_DROP_TEMP_VIEW, sqlite3.SQLITE_DROP_TRIGGER,
        sqlite3.SQLITE_DROP_VIEW, sqlite3.SQLITE_INSERT,
        sqlite3.SQLITE_UPDATE, sqlite3.SQLITE_ALTER_TABLE,
        sqlite3.SQLITE_REINDEX, sqlite3.SQLITE_ANALYZE,
        sqlite3.SQLITE_ATTACH, sqlite3.SQLITE_DETACH,
        sqlite3.SQLITE_TRANSACTION, sqlite3.SQLITE_PRAGMA,
    }
    if action == sqlite3.SQLITE_PRAGMA:
        if (arg1 or "").casefold() == "table_info" and isinstance(arg2, str) and _TABLE_RE.fullmatch(arg2):
            return sqlite3.SQLITE_OK
        return sqlite3.SQLITE_DENY
    if action in denied:
        return sqlite3.SQLITE_DENY
    if action == sqlite3.SQLITE_FUNCTION and (arg1 or arg2 or "").casefold() == "load_extension":
        return sqlite3.SQLITE_DENY
    return sqlite3.SQLITE_OK


def _business_tables(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_schema WHERE type='table' AND name GLOB 'biz_*' ORDER BY name"
    ).fetchall()
    return [row[0] for row in rows if _TABLE_RE.fullmatch(row[0])]


def _table_columns(conn: sqlite3.Connection, table: str) -> dict[str, str]:
    table = _validate_table(table)
    if table not in _business_tables(conn):
        raise DatabaseMCPError("table is not available")
    rows = conn.execute(f"PRAGMA table_info({_identifier(table)})").fetchall()
    return {row[1]: row[2].upper() for row in rows if row[1] not in _INTERNAL_COLUMNS}


def _canonical_payload(table: str, rows: list[dict[str, Any]]) -> str:
    payload = json.dumps({"table": table, "rows": rows}, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _validate_column_specs(columns: list[dict[str, Any]]) -> list[tuple[str, str]]:
    if not isinstance(columns, list) or not 1 <= len(columns) <= _MAX_COLUMNS:
        raise DatabaseMCPError(f"columns must contain 1 to {_MAX_COLUMNS} entries")
    result: list[tuple[str, str]] = []
    seen: set[str] = set()
    for item in columns:
        if not isinstance(item, dict) or set(item) != {"name", "type"}:
            raise DatabaseMCPError("each column requires exactly name and type")
        name = _validate_column(item["name"])
        column_type = item["type"]
        if not isinstance(column_type, str) or column_type.upper() not in _COLUMN_TYPES:
            raise DatabaseMCPError("column type must be TEXT, INTEGER, REAL, or BOOLEAN")
        if name in seen:
            raise DatabaseMCPError("duplicate column name")
        seen.add(name)
        result.append((name, column_type.upper()))
    return result


def _validate_rows(rows: list[dict[str, Any]], columns: dict[str, str]) -> list[dict[str, Any]]:
    if not isinstance(rows, list) or not 1 <= len(rows) <= _MAX_ROWS:
        raise DatabaseMCPError(f"rows must contain 1 to {_MAX_ROWS} entries")
    normalized: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict) or not row or not set(row).issubset(columns):
            raise DatabaseMCPError("each row must contain only known business columns")
        clean: dict[str, Any] = {}
        for key, value in row.items():
            _validate_column(key)
            kind = columns[key]
            if value is None:
                clean[key] = None
            elif kind == "TEXT":
                if not isinstance(value, str) or len(value) > _MAX_TEXT_LENGTH:
                    raise DatabaseMCPError(f"{key} must be text of at most {_MAX_TEXT_LENGTH} characters")
                clean[key] = value
            elif kind == "INTEGER":
                if isinstance(value, bool) or not isinstance(value, int):
                    raise DatabaseMCPError(f"{key} must be an integer")
                clean[key] = value
            elif kind == "REAL":
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                    raise DatabaseMCPError(f"{key} must be a finite number")
                clean[key] = float(value)
            elif kind == "BOOLEAN":
                if not isinstance(value, bool):
                    raise DatabaseMCPError(f"{key} must be a boolean")
                clean[key] = int(value)
        normalized.append(clean)
    return normalized


class WriteApprovalStore:
    """Host-side, one-use approvals; no approval-granting MCP tool is exposed."""

    def __init__(self, database_path: str | Path | None = None) -> None:
        self.path = _database_path(database_path)

    def issue(self, operation_id: str, table: str, rows: list[dict[str, Any]], *, ttl_seconds: int = _APPROVAL_TTL_SECONDS) -> str:
        if not isinstance(operation_id, str) or not _OPERATION_RE.fullmatch(operation_id):
            raise DatabaseMCPError("operation_id must be 8 to 100 safe characters")
        table = _validate_table(table)
        if not isinstance(ttl_seconds, int) or isinstance(ttl_seconds, bool) or not 1 <= ttl_seconds <= 900:
            raise DatabaseMCPError("approval expiry must be between 1 and 900 seconds")
        with _managed_connection(self.path) as conn:
            columns = _table_columns(conn, table)
            normalized = _validate_rows(rows, columns)
            digest = _canonical_payload(table, normalized)
            ticket = secrets.token_urlsafe(32)
            conn.execute(
                "CREATE TABLE IF NOT EXISTS _mcp_write_approvals (ticket_hash TEXT PRIMARY KEY, operation_id TEXT NOT NULL, table_name TEXT NOT NULL, payload_digest TEXT NOT NULL, expires_at INTEGER NOT NULL, consumed_at INTEGER)"
            )
            conn.execute(
                "INSERT INTO _mcp_write_approvals(ticket_hash, operation_id, table_name, payload_digest, expires_at) VALUES (?, ?, ?, ?, ?)",
                (hashlib.sha256(ticket.encode()).hexdigest(), operation_id, table, digest, int(time.time()) + ttl_seconds),
            )
        return ticket


def issue_write_approval(database_path: str | Path, operation_id: str, table: str, rows: list[dict[str, Any]], *, ttl_seconds: int = _APPROVAL_TTL_SECONDS) -> str:
    """Trusted local host API to issue a one-time ticket after user confirmation.

    This function is not registered as an MCP tool. Its caller must be a trusted
    local application component and should keep the returned ticket out of model
    context until the user has confirmed the exact payload.
    """
    return WriteApprovalStore(database_path).issue(operation_id, table, rows, ttl_seconds=ttl_seconds)


class DatabaseMCP:
    """Safe operations used by the protocol-facing MCP tools."""

    def __init__(self, database_path: str | Path | None = None) -> None:
        self.path = _database_path(database_path)

    def create_table(self, table: str, columns: list[dict[str, Any]]) -> dict[str, Any]:
        try:
            table = _validate_table(table)
            specs = _validate_column_specs(columns)
            fields = [f"{_identifier(name)} {kind}" for name, kind in specs]
            ddl = ", ".join([
                '"_mcp_operation_id" TEXT NOT NULL UNIQUE',
                '"_mcp_operation_digest" TEXT NOT NULL',
                *fields,
            ])
            with _managed_connection(self.path) as conn:
                if table in _business_tables(conn):
                    return {"ok": False, "status": "already_exists", "error": "table already exists"}
                conn.execute(f"CREATE TABLE {_identifier(table)} ({ddl})")
            return {"ok": True, "status": "created", "table": table, "columns": [{"name": n, "type": t} for n, t in specs]}
        except (DatabaseMCPError, sqlite3.Error, OSError) as exc:
            message = str(exc) if isinstance(exc, DatabaseMCPError) else "database operation failed"
            return {"ok": False, "status": "error", "error": message}

    def insert_rows(self, table: str, operation_id: str, rows: list[dict[str, Any]], approval_ticket: str) -> dict[str, Any]:
        try:
            table = _validate_table(table)
            if not isinstance(operation_id, str) or not _OPERATION_RE.fullmatch(operation_id):
                raise DatabaseMCPError("operation_id must be 8 to 100 safe characters")
            if not isinstance(approval_ticket, str) or not 32 <= len(approval_ticket) <= 200:
                raise DatabaseMCPError("a valid local approval ticket is required")
            with _managed_connection(self.path) as conn:
                columns = _table_columns(conn, table)
                normalized = _validate_rows(rows, columns)
                digest = _canonical_payload(table, normalized)
                existing = conn.execute(
                    f"SELECT _mcp_operation_digest FROM {_identifier(table)} WHERE _mcp_operation_id = ?",
                    (operation_id,),
                ).fetchone()
                if existing:
                    return {"ok": False, "status": "duplicate", "same_payload": existing[0] == digest, "inserted_rows": 0}
                ticket_hash = hashlib.sha256(approval_ticket.encode()).hexdigest()
                approvals_table = conn.execute(
                    "SELECT 1 FROM sqlite_schema WHERE type='table' AND name='_mcp_write_approvals'"
                ).fetchone()
                approval = None
                if approvals_table:
                    approval = conn.execute(
                        "SELECT operation_id, table_name, payload_digest, expires_at, consumed_at FROM _mcp_write_approvals WHERE ticket_hash = ?",
                        (ticket_hash,),
                    ).fetchone()
                now = int(time.time())
                if not approval or approval[0] != operation_id or approval[1] != table or approval[2] != digest or approval[3] < now or approval[4] is not None:
                    return {"ok": False, "status": "not_approved", "error": "no matching unexpired local approval"}
                updated = conn.execute(
                    "UPDATE _mcp_write_approvals SET consumed_at = ? WHERE ticket_hash = ? AND consumed_at IS NULL AND expires_at >= ?",
                    (now, ticket_hash, now),
                ).rowcount
                if updated != 1:
                    return {"ok": False, "status": "not_approved", "error": "approval is expired or already used"}
                names = list(columns)
                sql_columns = ["_mcp_operation_id", "_mcp_operation_digest", *names]
                insert_sql = f"INSERT INTO {_identifier(table)} ({', '.join(_identifier(n) for n in sql_columns)}) VALUES ({', '.join('?' for _ in sql_columns)})"
                for index, row in enumerate(normalized):
                    values = [operation_id if index == 0 else f"{operation_id}:{index}", digest, *(row.get(name) for name in names)]
                    conn.execute(insert_sql, values)
            return {"ok": True, "status": "inserted", "inserted_rows": len(normalized), "operation_id": operation_id}
        except (DatabaseMCPError, sqlite3.Error, OSError) as exc:
            message = str(exc) if isinstance(exc, DatabaseMCPError) else "database operation failed"
            return {"ok": False, "status": "error", "error": message}

    def query_readonly(self, table: str, columns: list[str], filters: list[dict[str, Any]] | None = None, limit: int = 50) -> dict[str, Any]:
        try:
            table = _validate_table(table)
            if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= _MAX_RESULT_ROWS:
                raise DatabaseMCPError(f"limit must be between 1 and {_MAX_RESULT_ROWS}")
            if not isinstance(columns, list) or not columns:
                raise DatabaseMCPError("columns must be a non-empty list")
            with _managed_connection(self.path, readonly=True) as conn:
                available = _table_columns(conn, table)
                selected = [_validate_column(name) for name in columns]
                if len(set(selected)) != len(selected) or not set(selected).issubset(available):
                    raise DatabaseMCPError("columns contain duplicates or unavailable fields")
                clauses: list[str] = []
                values: list[Any] = []
                if filters is None:
                    filters = []
                if not isinstance(filters, list) or len(filters) > 10:
                    raise DatabaseMCPError("filters must contain at most 10 entries")
                for item in filters:
                    if not isinstance(item, dict) or set(item) != {"column", "op", "value"}:
                        raise DatabaseMCPError("each filter requires exactly column, op, and value")
                    key = _validate_column(item["column"])
                    op = item["op"]
                    if key not in available or not isinstance(op, str) or op not in {*_FILTER_OPERATORS, "contains"}:
                        raise DatabaseMCPError("filter column or operator is not supported")
                    value = item["value"]
                    if isinstance(value, (dict, list)):
                        raise DatabaseMCPError("filter values must be scalar")
                    if op == "contains":
                        if available[key] != "TEXT" or not isinstance(value, str) or len(value) > _MAX_TEXT_LENGTH:
                            raise DatabaseMCPError("contains filter requires bounded text")
                        escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
                        clauses.append(f"{_identifier(key)} LIKE ? ESCAPE '\\'")
                        values.append(f"%{escaped}%")
                    else:
                        if value is None:
                            raise DatabaseMCPError("filter values cannot be null")
                        value = _validate_rows([{key: value}], {key: available[key]})[0][key]
                        clauses.append(f"{_identifier(key)} {_FILTER_OPERATORS[op]} ?")
                        values.append(value)
                where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
                sql = f"SELECT {', '.join(_identifier(c) for c in selected)} FROM {_identifier(table)}{where} LIMIT ?"
                result = conn.execute(sql, [*values, limit]).fetchall()
                return {"ok": True, "columns": selected, "rows": [dict(row) for row in result], "row_count": len(result)}
        except (DatabaseMCPError, sqlite3.Error, OSError) as exc:
            message = str(exc) if isinstance(exc, DatabaseMCPError) else "read-only query failed"
            return {"ok": False, "status": "error", "error": message}

    def schema_resource(self) -> str:
        if not self.path.is_file():
            return json.dumps({"tables": []}, ensure_ascii=False)
        try:
            with _managed_connection(self.path, readonly=True) as conn:
                tables = []
                for table in _business_tables(conn):
                    columns = conn.execute(f"PRAGMA table_info({_identifier(table)})").fetchall()
                    tables.append({"table": table, "columns": [{"name": row[1], "type": row[2].upper(), "nullable": not bool(row[3])} for row in columns if row[1] not in _INTERNAL_COLUMNS]})
            return json.dumps({"tables": tables}, ensure_ascii=False)
        except sqlite3.Error as exc:
            raise DatabaseMCPError("could not read business schema") from exc

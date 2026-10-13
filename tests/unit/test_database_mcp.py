from __future__ import annotations

import hashlib

import pytest

from app.mcp.servers.database.database import (
    DatabaseMCP,
    DatabaseMCPError,
    _database_path,
    issue_write_approval,
)


def _table(database: DatabaseMCP) -> None:
    result = database.create_table(
        "biz_vocab",
        [{"name": "word", "type": "TEXT"}, {"name": "level", "type": "TEXT"}],
    )
    assert result["ok"] is True


def test_create_query_and_schema_are_confined_to_business_db(tmp_path):
    db_path = tmp_path / "business.sqlite3"
    database = DatabaseMCP(db_path)
    _table(database)
    ticket = issue_write_approval(
        db_path, "operation-0001", "biz_vocab", [{"word": "lernen", "level": "A1"}]
    )
    inserted = database.insert_rows(
        "biz_vocab", "operation-0001", [{"word": "lernen", "level": "A1"}], ticket
    )
    assert inserted["status"] == "inserted"
    queried = database.query_readonly("biz_vocab", ["word", "level"], [{"column": "level", "op": "eq", "value": "A1"}])
    assert queried == {"ok": True, "columns": ["word", "level"], "rows": [{"word": "lernen", "level": "A1"}], "row_count": 1}
    assert '"tables"' in database.schema_resource()
    assert str(db_path) not in database.schema_resource()


def test_unapproved_and_payload_mismatched_writes_are_rejected(tmp_path):
    database = DatabaseMCP(tmp_path / "business.sqlite3")
    _table(database)
    rows = [{"word": "lernen", "level": "A1"}]
    assert database.insert_rows("biz_vocab", "operation-0001", rows, "x" * 40)["status"] == "not_approved"
    ticket = issue_write_approval(database.path, "operation-0001", "biz_vocab", rows)
    changed = database.insert_rows("biz_vocab", "operation-0001", [{"word": "lernen", "level": "B1"}], ticket)
    assert changed["status"] == "not_approved"
    assert database.query_readonly("biz_vocab", ["word"])["row_count"] == 0


def test_approval_is_one_time_and_operation_is_idempotent(tmp_path):
    database = DatabaseMCP(tmp_path / "business.sqlite3")
    _table(database)
    rows = [{"word": "lernen", "level": "A1"}]
    ticket = issue_write_approval(database.path, "operation-0001", "biz_vocab", rows)
    assert database.insert_rows("biz_vocab", "operation-0001", rows, ticket)["status"] == "inserted"
    replay = database.insert_rows("biz_vocab", "operation-0001", rows, ticket)
    assert replay["status"] == "duplicate"
    assert database.query_readonly("biz_vocab", ["word"])["row_count"] == 1


def test_invalid_names_fields_types_and_limits_are_rejected(tmp_path):
    database = DatabaseMCP(tmp_path / "business.sqlite3")
    assert database.create_table("users", [{"name": "x", "type": "TEXT"}])["ok"] is False
    assert database.create_table("biz_bad", [{"name": "word; DROP TABLE x", "type": "TEXT"}])["ok"] is False
    _table(database)
    assert database.query_readonly("biz_vocab", ["sqlite_schema"])["ok"] is False
    assert database.query_readonly("biz_vocab", ["word"], limit=101)["ok"] is False
    ticket = issue_write_approval(database.path, "operation-0002", "biz_vocab", [{"word": "lernen", "level": "A1"}])
    result = database.insert_rows("biz_vocab", "operation-0002", [{"word": 7, "level": "A1"}], ticket)
    assert result["ok"] is False


def test_readonly_query_does_not_modify_database(tmp_path):
    path = tmp_path / "business.sqlite3"
    database = DatabaseMCP(path)
    _table(database)
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    assert database.query_readonly("biz_vocab", ["word"])["ok"] is True
    after = hashlib.sha256(path.read_bytes()).hexdigest()
    assert after == before


def test_application_storage_path_collision_is_rejected(tmp_path, monkeypatch):
    stage = tmp_path / "stage"
    stage.mkdir()
    monkeypatch.setenv("STAGE2_DATA_PATH", str(stage))
    with pytest.raises(DatabaseMCPError):
        _database_path(stage / "stage2.db")
    with pytest.raises(DatabaseMCPError):
        _database_path(stage / "chroma" / "chroma.sqlite3")


def test_database_file_is_not_created_by_resource_or_query(tmp_path):
    path = tmp_path / "not-yet-created.sqlite3"
    database = DatabaseMCP(path)
    assert database.schema_resource() == '{"tables": []}'
    assert database.query_readonly("biz_vocab", ["word"])["ok"] is False
    assert not path.exists()

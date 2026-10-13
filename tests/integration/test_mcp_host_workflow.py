from __future__ import annotations

from pathlib import Path

import pytest

from app.mcp.host import MCPHost


FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "ocr" / "vocabulary_table.png"


def test_real_dual_server_workflow_requires_confirmation_and_verifies_write(tmp_path):
    host = MCPHost(tmp_path / "isolated-state")
    db_capabilities = host.discover("database")
    ocr_capabilities = host.discover("ocr")
    assert {item["name"] for item in db_capabilities["tools"]} == {"db_create_table", "db_insert_rows", "db_query_readonly"}
    assert [item["uri"] for item in db_capabilities["resources"]] == ["db://schema"]
    assert [item["name"] for item in db_capabilities["prompts"]] == ["ocr_to_db_workflow"]
    assert {item["name"] for item in ocr_capabilities["tools"]} == {"ocr_extract"}
    assert ocr_capabilities["resources"] == [] and ocr_capabilities["prompts"] == []
    assert host.read_resource("db://schema")[0]["text"] == '{"tables": []}'
    assert host.get_prompt("ocr_to_db_workflow")
    staged = host.stage_image("user-a", "session-a", "words.png", FIXTURE.read_bytes())
    with pytest.raises(KeyError):
        host.preview("user-b", "session-a", staged["image_id"], "en")
    with pytest.raises(KeyError):
        host.preview("user-a", "session-b", staged["image_id"], "en")

    preview = host.preview("user-a", "session-a", staged["image_id"], "en")
    assert preview["success"] is True
    assert preview["status"] == "awaiting_confirmation"
    assert preview["rows"] == [
        {"word": "Haus", "meaning": "house", "level": "A1"},
        {"word": "gehen", "meaning": "to go", "level": "A1"},
        {"word": "verstehen", "meaning": "understand", "level": "A2"},
    ]
    assert "approval_ticket" not in preview
    assert host.read_resource("db://schema")[0]["text"] == '{"tables": []}'
    assert not host.database_path.exists()

    confirmed = host.confirm_and_commit("user-a", "session-a", preview["operation_id"], preview["rows"], True)
    assert confirmed["status"] == "verified"
    assert confirmed["inserted_rows"] == 3
    assert confirmed["rows"] == preview["rows"]
    with host._connect() as conn:
        events = conn.execute("SELECT tool_name,source,status FROM mcp_tool_events ORDER BY id").fetchall()
        workflow = conn.execute("SELECT status,rows_digest FROM mcp_workflows").fetchone()
    assert [(row["tool_name"], row["source"], row["status"]) for row in events] == [
        ("ocr_extract", "ocr", "success"),
        ("db_create_table", "database", "success"),
        ("db_insert_rows", "database", "success"),
        ("db_query_readonly", "database", "success"),
    ]
    assert workflow["status"] == "verified"
    assert len(workflow["rows_digest"]) == 64
    replay = host.confirm_and_commit("user-a", "session-a", preview["operation_id"], preview["rows"], True)
    assert replay["replayed"] is True and replay["inserted_rows"] == 3
    with host._connect() as conn:
        stored_rows = conn.execute("SELECT COUNT(*) FROM mcp_tool_events WHERE operation_id=? AND tool_name='db_insert_rows'", (preview["operation_id"],)).fetchone()[0]
    assert stored_rows == 1
    changed = [dict(row) for row in preview["rows"]]
    changed[0]["meaning"] = "changed after commit"
    with pytest.raises(RuntimeError, match="different reviewed content"):
        host.confirm_and_commit("user-a", "session-a", preview["operation_id"], changed, True)
    # Windows refuses to delete SQLite files that still have an open connection.
    host.database_path.unlink()
    host.state_path.unlink()


def test_confirmation_is_required_and_edited_payload_is_exactly_written(tmp_path):
    host = MCPHost(tmp_path / "isolated-state")
    staged = host.stage_image("u", "s", "words.png", FIXTURE.read_bytes())
    preview = host.preview("u", "s", staged["image_id"], "en")
    rows = [dict(item) for item in preview["rows"]]
    rows[0]["meaning"] = "home"
    with pytest.raises(ValueError, match="confirmation"):
        host.confirm_and_commit("u", "s", preview["operation_id"], rows, False)
    result = host.confirm_and_commit("u", "s", preview["operation_id"], rows, True)
    assert result["rows"][0]["meaning"] == "home"


def test_staged_file_replacement_is_rejected(tmp_path):
    host = MCPHost(tmp_path / "isolated-state")
    staged = host.stage_image("u", "s", "words.png", FIXTURE.read_bytes())
    with host._connect() as conn:
        image_path = Path(conn.execute("SELECT path FROM mcp_images WHERE image_id=?", (staged["image_id"],)).fetchone()[0])
    image_path.write_bytes(b"replaced")
    with pytest.raises(RuntimeError, match="changed"):
        host.preview("u", "s", staged["image_id"], "en")


def test_file_change_after_preview_invalidates_pending_confirmation(tmp_path):
    host = MCPHost(tmp_path / "isolated-state")
    staged = host.stage_image("u", "s", "words.png", FIXTURE.read_bytes())
    preview = host.preview("u", "s", staged["image_id"], "en")
    with host._connect() as conn:
        image_path = Path(conn.execute("SELECT path FROM mcp_images WHERE image_id=?", (staged["image_id"],)).fetchone()[0])
    image_path.write_bytes(b"changed after OCR")
    with pytest.raises(RuntimeError, match="changed after upload"):
        host.confirm_and_commit("u", "s", preview["operation_id"], preview["rows"], True)
    assert not host.database_path.exists()


def test_disconnected_ocr_server_fails_controlled_and_records_operation(tmp_path, monkeypatch):
    host = MCPHost(tmp_path / "isolated-state")
    staged = host.stage_image("u", "s", "words.png", FIXTURE.read_bytes())

    async def disconnected(*_args, **_kwargs):
        raise ConnectionError("server process exited")

    monkeypatch.setattr(host, "_call", disconnected)
    with pytest.raises(RuntimeError, match="unavailable or disconnected"):
        host.preview("u", "s", staged["image_id"], "en")
    with host._connect() as conn:
        event = conn.execute("SELECT tool_name,source,status FROM mcp_tool_events").fetchone()
    assert tuple(event) == ("ocr_extract", "ocr", "failed")


def test_registry_rejects_unknown_tools_and_unexpected_parameters(tmp_path):
    host = MCPHost(tmp_path / "isolated-state")
    with pytest.raises(RuntimeError, match="unknown MCP tool"):
        host.call_tool("arbitrary_sql", {"query": "DROP TABLE users"})
    with pytest.raises(ValueError, match="invalid arguments"):
        host.call_tool("db_query_readonly", {"table": "biz_vocabulary", "columns": ["word"], "sql": "DROP TABLE x"})

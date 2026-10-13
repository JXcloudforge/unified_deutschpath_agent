"""Trusted Host adapters for the two local MCP servers.

Only this module chooses server commands, paths, and write approvals. Model and
browser inputs can select a registered operation but never supply those values.
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from contextlib import contextmanager
import hashlib
import json
import os
import re
import shutil
import sqlite3
import sys
from pathlib import Path
from typing import Any
from uuid import uuid4

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from app.config import PROJECT_ROOT
from app.mcp.servers.database.database import issue_write_approval


class MCPHostError(RuntimeError):
    pass


_TABLE_NAME = re.compile(r"^biz_[a-z][a-z0-9_]{0,35}$")
_OPERATION_ID = re.compile(r"^[A-Za-z0-9_-]{8,100}$")


def _result_payload(result: Any) -> Any:
    if result.isError:
        raise MCPHostError("MCP tool returned an error")
    if result.structuredContent is not None:
        return result.structuredContent
    if result.content:
        first = result.content[0]
        if getattr(first, "text", None):
            return json.loads(first.text)
    raise MCPHostError("MCP tool returned no structured result")


class MCPHost:
    """Bounded, one-workflow client to real B4/B5 stdio servers."""
    def __init__(self, root: str | Path, database_path: str | Path | None = None) -> None:
        self.root = Path(root).resolve()
        self.image_root = self.root / "mcp_ocr_inputs"
        self.image_root.mkdir(parents=True, exist_ok=True)
        self.database_path = Path(database_path or (self.root / "mcp_business.sqlite3")).resolve()
        self.state_path = self.root / "mcp_host_state.sqlite3"
        self.root.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.state_path)
        try:
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS mcp_images(image_id TEXT PRIMARY KEY,user_id TEXT NOT NULL,session_id TEXT NOT NULL,path TEXT NOT NULL,sha256 TEXT NOT NULL,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS mcp_workflows(operation_id TEXT PRIMARY KEY,user_id TEXT NOT NULL,session_id TEXT NOT NULL,image_id TEXT NOT NULL,image_sha256 TEXT NOT NULL,table_name TEXT NOT NULL,ocr_json TEXT NOT NULL,rows_json TEXT NOT NULL,rows_digest TEXT NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS mcp_tool_events(id INTEGER PRIMARY KEY AUTOINCREMENT,operation_id TEXT NOT NULL,user_id TEXT NOT NULL,session_id TEXT NOT NULL,tool_name TEXT NOT NULL,source TEXT NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
            """)
        finally:
            conn.close()

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.state_path, timeout=5)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    TOOL_REGISTRY = {
        "ocr_extract": {"purpose": "extract text from one Host-authorized session image", "server": "ocr", "read_only": True, "permission": "session_image_read", "timeout_seconds": 45, "error_type": "MCPHostError", "parameter_schema": {"type": "object", "properties": {"image_id": {"type": "string", "minLength": 1, "maxLength": 80}, "language": {"type": "string", "enum": ["en", "de"]}}, "required": ["image_id", "language"], "additionalProperties": False}},
        "db_create_table": {"purpose": "create constrained vocabulary schema", "server": "database", "read_only": False, "permission": "reviewed_workflow", "timeout_seconds": 45, "error_type": "MCPHostError", "parameter_schema": {"type": "object", "properties": {"table": {"type": "string", "pattern": "^biz_[a-z][a-z0-9_]{0,35}$"}, "columns": {"type": "array", "minItems": 1, "maxItems": 20}}, "required": ["table", "columns"], "additionalProperties": False}},
        "db_insert_rows": {"purpose": "insert reviewed rows", "server": "database", "read_only": False, "permission": "one_time_host_approval", "timeout_seconds": 45, "error_type": "MCPHostError", "parameter_schema": {"type": "object", "properties": {"table": {"type": "string", "pattern": "^biz_[a-z][a-z0-9_]{0,35}$"}, "operation_id": {"type": "string", "minLength": 8, "maxLength": 100}, "rows": {"type": "array", "minItems": 1, "maxItems": 50}, "approval_ticket": {"type": "string", "minLength": 32}}, "required": ["table", "operation_id", "rows", "approval_ticket"], "additionalProperties": False}},
        "db_query_readonly": {"purpose": "verify structured query results", "server": "database", "read_only": True, "permission": "session_workflow", "timeout_seconds": 45, "error_type": "MCPHostError", "parameter_schema": {"type": "object", "properties": {"table": {"type": "string", "pattern": "^biz_[a-z][a-z0-9_]{0,35}$"}, "columns": {"type": "array", "minItems": 1}, "filters": {"type": ["array", "null"], "maxItems": 10}, "limit": {"type": "integer", "minimum": 1, "maximum": 100}}, "required": ["table", "columns", "filters", "limit"], "additionalProperties": False}},
    }

    def stage_image(self, user_id: str, session_id: str, filename: str, data: bytes) -> dict[str, Any]:
        if len(data) > 10 * 1024 * 1024 or not data:
            raise ValueError("image must be non-empty and at most 10 MiB")
        from PIL import Image, UnidentifiedImageError
        from io import BytesIO
        try:
            with Image.open(BytesIO(data)) as image:
                if image.format not in {"PNG", "JPEG", "WEBP", "BMP", "TIFF"} or image.width * image.height > 20_000_000:
                    raise ValueError("unsupported image format or dimensions")
                image.verify()
                image_format = image.format.lower()
        except (UnidentifiedImageError, OSError) as exc:
            raise ValueError("uploaded content is not a valid supported image") from exc
        image_id = uuid4().hex
        suffix = ".jpg" if image_format == "jpeg" else f".{image_format}"
        target = self.image_root / f"{image_id}{suffix}"
        target.write_bytes(data)
        digest = hashlib.sha256(data).hexdigest()
        with self._connect() as conn:
            conn.execute("INSERT INTO mcp_images(image_id,user_id,session_id,path,sha256) VALUES(?,?,?,?,?)", (image_id,user_id,session_id,str(target),digest))
        return {"image_id": image_id, "filename": Path(filename).name, "sha256": digest, "bytes": len(data)}

    def _image(self, user_id: str, session_id: str, image_id: str):
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM mcp_images WHERE image_id=? AND user_id=? AND session_id=?", (image_id,user_id,session_id)).fetchone()
        if row is None:
            raise KeyError("image is not authorized for this user and session")
        path = Path(row["path"])
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != row["sha256"]:
            raise MCPHostError("staged image changed after upload")
        return row, path

    def _record_tool_event(self, operation_id: str, user_id: str, session_id: str,
                           tool_name: str, source: str, status: str) -> None:
        with self._connect() as conn:
            conn.execute("INSERT INTO mcp_tool_events(operation_id,user_id,session_id,tool_name,source,status) VALUES(?,?,?,?,?,?)",
                         (operation_id,user_id,session_id,tool_name,source,status))

    def latest_image_id(self, user_id: str, session_id: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute("SELECT image_id FROM mcp_images WHERE user_id=? AND session_id=? ORDER BY rowid DESC LIMIT 1", (user_id,session_id)).fetchone()
        return row["image_id"] if row else None

    def pending_workflow(self, user_id: str, session_id: str):
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM mcp_workflows WHERE user_id=? AND session_id=? AND status='awaiting_confirmation' ORDER BY rowid DESC LIMIT 1", (user_id,session_id)).fetchone()
        if row is None:
            return None
        image, _path = self._image(user_id,session_id,row["image_id"])
        if image["sha256"] != row["image_sha256"]:
            raise MCPHostError("workflow image changed after OCR")
        return {"success": True, "operation_id": row["operation_id"], "table": row["table_name"], "session_id": session_id, "ocr": json.loads(row["ocr_json"]), "rows": json.loads(row["rows_json"]), "status": row["status"]}

    def _run(self, awaitable):
        try:
            return asyncio.run(asyncio.wait_for(awaitable, timeout=45))
        except asyncio.TimeoutError as exc:
            raise MCPHostError("MCP operation timed out") from exc
        except MCPHostError:
            raise
        except Exception as exc:
            raise MCPHostError("MCP server is unavailable or disconnected") from exc

    @asynccontextmanager
    async def _session(self, server: str, *, image_dir: Path | None = None):
        env = {key: os.environ[key] for key in ("PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "USERPROFILE", "APPDATA", "LOCALAPPDATA") if key in os.environ}
        env["PYTHONIOENCODING"] = "utf-8"
        env["STAGE2_DATA_PATH"] = str(self.root)
        if server == "ocr":
            env["OCR_INPUT_DIR"] = str(image_dir or self.image_root)
            module = "app.mcp.servers.ocr.server"
        else:
            env["MCP_DATABASE_PATH"] = str(self.database_path)
            module = "app.mcp.servers.database.server"
        parameters = StdioServerParameters(command=sys.executable, args=["-m", module], env=env, cwd=str(PROJECT_ROOT))
        async with stdio_client(parameters) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                yield session

    async def _call(self, server: str, tool: str, args: dict, *, image_dir: Path | None = None):
        async with self._session(server, image_dir=image_dir) as session:
            available = await session.list_tools()
            if tool not in {item.name for item in available.tools}:
                raise MCPHostError("requested tool is not in the allowlisted server registry")
            return _result_payload(await session.call_tool(tool, args))

    def call_tool(self, tool: str, args: dict, *, image_dir: Path | None = None):
        if tool not in self.TOOL_REGISTRY:
            raise MCPHostError("unknown MCP tool")
        self._validate(tool, args)
        return self._run(self._call(self.TOOL_REGISTRY[tool]["server"], tool, args, image_dir=image_dir))

    async def _discover(self, server: str) -> dict[str, Any]:
        async with self._session(server) as session:
            tools = await session.list_tools()
            resources = await session.list_resources()
            prompts = await session.list_prompts()
            return {
                "tools": [item.model_dump(mode="json") for item in tools.tools],
                "resources": [item.model_dump(mode="json") for item in resources.resources],
                "prompts": [item.model_dump(mode="json") for item in prompts.prompts],
            }

    def discover(self, server: str) -> dict[str, Any]:
        if server not in {"database", "ocr"}:
            raise ValueError("unknown MCP server")
        return self._run(self._discover(server))

    async def _read_resource(self, uri: str):
        async with self._session("database") as session:
            result = await session.read_resource(uri)
            return [item.model_dump(mode="json") for item in result.contents]

    def read_resource(self, uri: str):
        if uri != "db://schema":
            raise ValueError("resource is not allowlisted")
        return self._run(self._read_resource(uri))

    async def _get_prompt(self, name: str):
        async with self._session("database") as session:
            result = await session.get_prompt(name)
            return [item.model_dump(mode="json") for item in result.messages]

    def get_prompt(self, name: str):
        if name != "ocr_to_db_workflow":
            raise ValueError("prompt is not allowlisted")
        return self._run(self._get_prompt(name))

    @staticmethod
    def _validate(tool: str, args: dict) -> None:
        required = {
            "ocr_extract": {"image_id", "language"},
            "db_create_table": {"table", "columns"},
            "db_insert_rows": {"table", "operation_id", "rows", "approval_ticket"},
            "db_query_readonly": {"table", "columns", "filters", "limit"},
        }[tool]
        if not isinstance(args, dict) or set(args) != required:
            raise ValueError(f"invalid arguments for {tool}")
        if tool == "ocr_extract" and (not isinstance(args["image_id"], str) or args["language"] not in {"en", "de"}):
            raise ValueError("invalid OCR arguments")
        if tool == "db_insert_rows" and (not isinstance(args["operation_id"], str) or not isinstance(args["rows"], list) or not isinstance(args["approval_ticket"], str)):
            raise ValueError("invalid database write arguments")
        if tool.startswith("db_") and (not isinstance(args["table"], str) or not _TABLE_NAME.fullmatch(args["table"])):
            raise ValueError("database table is outside the biz_ allowlist")
        if tool == "db_create_table":
            columns = args["columns"]
            if not isinstance(columns, list) or not 1 <= len(columns) <= 20 or any(not isinstance(col, dict) or set(col) != {"name", "type"} or not isinstance(col["name"], str) or not isinstance(col["type"], str) or col["type"].upper() not in {"TEXT", "INTEGER", "REAL", "BOOLEAN"} for col in columns):
                raise ValueError("invalid database column schema")
        if tool == "db_insert_rows":
            if not _OPERATION_ID.fullmatch(args["operation_id"]) or not 1 <= len(args["rows"]) <= 50 or not 32 <= len(args["approval_ticket"]) <= 200:
                raise ValueError("invalid operation, row count, or Host approval credential")
            if any(not isinstance(row, dict) or not row or any(not isinstance(key, str) or isinstance(value, (dict, list)) or (isinstance(value, str) and len(value) > 4000) for key, value in row.items()) for row in args["rows"]):
                raise ValueError("invalid row payload")
        if tool == "db_query_readonly":
            if not isinstance(args["columns"], list) or not args["columns"] or not all(isinstance(column, str) for column in args["columns"]):
                raise ValueError("invalid query columns")
            if not isinstance(args["filters"], list) or len(args["filters"]) > 10 or isinstance(args["limit"], bool) or not isinstance(args["limit"], int) or not 1 <= args["limit"] <= 100:
                raise ValueError("invalid read-only query limits")

    def preview(self, user_id: str, session_id: str, image_id: str, language: str = "de", table: str = "biz_vocabulary") -> dict[str, Any]:
        if table != "biz_vocabulary":
            raise ValueError("B6 preview currently supports the reviewed vocabulary table only")
        image, path = self._image(user_id, session_id, image_id)
        operation_id = uuid4().hex
        job_dir = self.image_root / f"job-{uuid4().hex}"
        job_dir.mkdir()
        try:
            job_image = job_dir / path.name
            shutil.copyfile(path, job_image)
            if hashlib.sha256(job_image.read_bytes()).hexdigest() != image["sha256"]:
                raise MCPHostError("staged image changed while preparing OCR")
            try:
                ocr = self.call_tool("ocr_extract", {"image_id": job_image.stem, "language": language}, image_dir=job_dir)
            except Exception:
                self._record_tool_event(operation_id,user_id,session_id,"ocr_extract","ocr","failed")
                raise
        finally:
            shutil.rmtree(job_dir, ignore_errors=True)
        if not ocr.get("success"):
            self._record_tool_event(operation_id,user_id,session_id,"ocr_extract","ocr",str(ocr.get("status", "failed"))[:40])
            return {"success": False, "operation_id": operation_id, "session_id": session_id, "error": ocr.get("error", "OCR failed"), "ocr": ocr}
        candidates = ocr.get("tables", [])
        if not candidates or len(candidates[0].get("rows", [])) < 2:
            self._record_tool_event(operation_id,user_id,session_id,"ocr_extract","ocr","no_reviewable_table")
            return {"success": False, "operation_id": operation_id, "session_id": session_id, "error": "OCR returned no reviewable table rows", "ocr": ocr}
        candidate = candidates[0]["rows"]
        headers = [str(cell.get("text", "")).strip().lower() for cell in candidate[0]]
        rows = [{headers[index]: str(cell.get("text", "")).strip() for index, cell in enumerate(row) if index < len(headers)} for row in candidate[1:]]
        if not rows or any(set(item) != {"word", "meaning", "level"} or any(not value for value in item.values()) for item in rows):
            self._record_tool_event(operation_id,user_id,session_id,"ocr_extract","ocr","invalid_table_layout")
            return {"success": False, "operation_id": operation_id, "session_id": session_id, "error": "OCR table layout is incomplete; review it manually", "ocr": ocr}
        rows_json = json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(rows_json.encode()).hexdigest()
        with self._connect() as conn:
            conn.execute("INSERT INTO mcp_workflows(operation_id,user_id,session_id,image_id,image_sha256,table_name,ocr_json,rows_json,rows_digest,status) VALUES(?,?,?,?,?,?,?,?,?,?)", (operation_id,user_id,session_id,image_id,image["sha256"],table,json.dumps(ocr,ensure_ascii=False),rows_json,digest,"awaiting_confirmation"))
            conn.execute("INSERT INTO mcp_tool_events(operation_id,user_id,session_id,tool_name,source,status) VALUES(?,?,?,?,?,?)", (operation_id,user_id,session_id,"ocr_extract","ocr","success"))
        return {"success": True, "operation_id": operation_id, "table": table, "ocr": ocr, "rows": rows, "status": "awaiting_confirmation"}

    def confirm_and_commit(self, user_id: str, session_id: str, operation_id: str, rows: list[dict[str, Any]], confirmed: bool) -> dict[str, Any]:
        if confirmed is not True or not isinstance(rows, list) or not rows:
            raise ValueError("explicit confirmation and reviewed rows are required")
        with self._connect() as conn:
            workflow = conn.execute("SELECT * FROM mcp_workflows WHERE operation_id=? AND user_id=? AND session_id=?", (operation_id,user_id,session_id)).fetchone()
        if workflow is None:
            raise KeyError("operation is not authorized for this user and session")
        if workflow["status"] == "verified":
            replay_json = json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            if hashlib.sha256(replay_json.encode()).hexdigest() != workflow["rows_digest"]:
                raise MCPHostError("operation was already completed with different reviewed content")
            columns = list(rows[0]) if rows else []
            verified = self.call_tool("db_query_readonly", {"table": workflow["table_name"], "columns": columns, "filters": [], "limit": 100})
            if not verified.get("ok"):
                raise MCPHostError("completed operation could not be re-queried")
            return {"operation_id": operation_id, "status": "verified", "inserted_rows": len(rows), "rows": verified["rows"], "replayed": True}
        if workflow["status"] != "awaiting_confirmation":
            raise MCPHostError("operation is no longer awaiting confirmation")
        _image, _path = self._image(user_id, session_id, workflow["image_id"])
        if len(rows) > 50 or any(not isinstance(row, dict) or set(row) != {"word", "meaning", "level"} or any(not isinstance(value, str) or not value.strip() or len(value) > 4000 for value in row.values()) for row in rows):
            raise ValueError("reviewed rows must contain bounded word, meaning, and level text fields")
        approved_json = json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        approved_digest = hashlib.sha256(approved_json.encode()).hexdigest()
        operation = workflow["operation_id"]
        with self._connect() as conn:
            claimed = conn.execute("UPDATE mcp_workflows SET status='committing' WHERE operation_id=? AND status='awaiting_confirmation'", (operation,)).rowcount
        if claimed != 1:
            raise MCPHostError("operation is already being processed")
        # The exact reviewed payload is persisted before approval issuance; the
        # ticket binds this payload digest and is never returned by this API.
        with self._connect() as conn:
            conn.execute("UPDATE mcp_workflows SET rows_json=?,rows_digest=? WHERE operation_id=?", (approved_json,approved_digest,operation))
        try:
            created = self.call_tool("db_create_table", {"table": workflow["table_name"], "columns": [
                {"name": "word", "type": "TEXT"}, {"name": "meaning", "type": "TEXT"}, {"name": "level", "type": "TEXT"},
            ]})
            if created.get("status") not in {"created", "already_exists"}:
                raise MCPHostError("business table creation was not completed")
            schema_text = self.read_resource("db://schema")[0]["text"]
            schema = json.loads(schema_text)
            table_schema = next((item for item in schema["tables"] if item["table"] == workflow["table_name"]), None)
            expected_schema = {"word": "TEXT", "meaning": "TEXT", "level": "TEXT"}
            if table_schema is None or {col["name"]: col["type"] for col in table_schema["columns"]} != expected_schema:
                raise MCPHostError("business table schema does not match the reviewed workflow")
            ticket = issue_write_approval(self.database_path, operation, workflow["table_name"], rows)
            result = self.call_tool("db_insert_rows", {"table": workflow["table_name"], "operation_id": operation, "rows": rows, "approval_ticket": ticket})
            if result.get("status") != "inserted":
                raise MCPHostError(f"database write was not completed: {result.get('status', 'error')}")
            columns = list(rows[0])
            verified = self.call_tool("db_query_readonly", {"table": workflow["table_name"], "columns": columns, "filters": [], "limit": 100})
            verified_rows = verified.get("rows", [])
            expected = sorted(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows)
            actual = sorted(json.dumps({key: row.get(key) for key in columns}, ensure_ascii=False, sort_keys=True) for row in verified_rows)
            if not verified.get("ok") or not set(expected).issubset(set(actual)):
                raise MCPHostError("database write could not be verified")
        except Exception:
            with self._connect() as conn:
                conn.execute("UPDATE mcp_workflows SET status='failed' WHERE operation_id=? AND status='committing'", (operation,))
            raise
        with self._connect() as conn:
            conn.execute("UPDATE mcp_workflows SET status='verified' WHERE operation_id=? AND status='committing'", (operation,))
            for name, status in (("db_create_table", "success"), ("db_insert_rows", "success"), ("db_query_readonly", "success")):
                conn.execute("INSERT INTO mcp_tool_events(operation_id,user_id,session_id,tool_name,source,status) VALUES(?,?,?,?,?,?)", (operation,user_id,session_id,name,"database",status))
        return {"operation_id": operation, "status": "verified", "inserted_rows": result["inserted_rows"], "rows": verified["rows"], "replayed": False}

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _payload(result):
    if result.structuredContent is not None:
        return result.structuredContent
    if result.content and getattr(result.content[0], "text", None):
        return json.loads(result.content[0].text)
    return None


def test_real_stdio_mcp_handshake_discovery_and_calls(tmp_path):
    async def exercise():
        env = os.environ.copy()
        env["MCP_DATABASE_PATH"] = str(tmp_path / "isolated-business.sqlite3")
        env["STAGE2_DATA_PATH"] = str(tmp_path / "isolated-stage2")
        parameters = StdioServerParameters(
            command=sys.executable,
            args=["-m", "app.mcp.servers.database.server"],
            env=env,
            cwd=PROJECT_ROOT,
        )
        async with stdio_client(parameters) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                initialized = await session.initialize()
                assert initialized.protocolVersion
                assert initialized.serverInfo.name == "Deutschpath Database MCP"
                assert "tools" in initialized.capabilities.model_fields_set
                tools = await session.list_tools()
                assert {tool.name for tool in tools.tools} == {
                    "db_create_table", "db_insert_rows", "db_query_readonly"
                }
                created = await session.call_tool("db_create_table", {
                    "table": "biz_words",
                    "columns": [{"name": "word", "type": "TEXT"}],
                })
                assert _payload(created)["status"] == "created"
                denied = await session.call_tool("db_insert_rows", {
                    "table": "biz_words", "operation_id": "protocol-op-01",
                    "rows": [{"word": "Haus"}], "approval_ticket": "x" * 40,
                })
                assert _payload(denied)["status"] == "not_approved"
                invalid = await session.call_tool("db_create_table", {
                    "table": "stage2_users", "columns": [{"name": "id", "type": "TEXT"}],
                })
                assert _payload(invalid)["ok"] is False
                readonly = await session.call_tool("db_query_readonly", {
                    "table": "biz_words", "columns": ["word"], "limit": 50,
                })
                assert _payload(readonly)["row_count"] == 0
                resources = await session.list_resources()
                schema_resource = next(item for item in resources.resources if str(item.uri) == "db://schema")
                schema = await session.read_resource(schema_resource.uri)
                assert "biz_words" in schema.contents[0].text
                assert str(tmp_path) not in schema.contents[0].text
                prompts = await session.list_prompts()
                assert "ocr_to_db_workflow" in {item.name for item in prompts.prompts}
                prompt = await session.get_prompt("ocr_to_db_workflow")
                prompt_text = "\n".join(message.content.text for message in prompt.messages if hasattr(message.content, "text"))
                assert "user" in prompt_text.lower() and "db_query_readonly" in prompt_text
                assert not created.isError and not denied.isError and not readonly.isError
        assert (tmp_path / "isolated-business.sqlite3").is_file()
        assert not (tmp_path / "isolated-stage2" / "stage2.db").exists()

    asyncio.run(asyncio.wait_for(exercise(), timeout=20))

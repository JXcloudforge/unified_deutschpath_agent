from __future__ import annotations

import asyncio
import json
import os
import shutil
import sys
from pathlib import Path

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


PROJECT_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "ocr"


def _payload(result):
    if result.structuredContent is not None:
        return result.structuredContent
    if result.content and getattr(result.content[0], "text", None):
        return json.loads(result.content[0].text)
    return None


def test_real_stdio_ocr_mcp_protocol_and_failures(tmp_path):
    input_dir = tmp_path / "authorized-input"
    input_dir.mkdir()
    shutil.copy2(FIXTURES / "english.png", input_dir / "english.png")
    shutil.copy2(FIXTURES / "german.png", input_dir / "german.png")
    shutil.copy2(FIXTURES / "vocabulary_table.png", input_dir / "table.png")
    (input_dir / "broken.png").write_bytes(b"broken image")

    async def exercise():
        env = os.environ.copy()
        env["OCR_INPUT_DIR"] = str(input_dir)
        parameters = StdioServerParameters(
            command=sys.executable,
            args=["-m", "app.mcp.servers.ocr.server"],
            env=env,
            cwd=PROJECT_ROOT,
        )
        async with stdio_client(parameters) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                initialized = await session.initialize()
                assert initialized.protocolVersion
                assert initialized.serverInfo.name == "Deutschpath OCR MCP"
                tools = await session.list_tools()
                assert {tool.name for tool in tools.tools} == {"ocr_extract"}
                assert not (await session.list_resources()).resources
                assert not (await session.list_prompts()).prompts

                en = _payload(await session.call_tool("ocr_extract", {"image_id": "english", "language": "en"}))
                assert en["success"] is True and "Good morning" in en.get("raw_text", ""), en
                de = _payload(await session.call_tool("ocr_extract", {"image_id": "german", "language": "de"}))
                assert de["success"] is True and "Straße" in de["raw_text"]
                table = _payload(await session.call_tool("ocr_extract", {"image_id": "table", "language": "en"}))
                assert table["success"] is True and len(table["tables"][0]["rows"]) == 4

                denied = _payload(await session.call_tool("ocr_extract", {"image_id": "../english", "language": "en"}))
                assert denied["success"] is False and denied["status"] == "invalid_image_input"
                missing = _payload(await session.call_tool("ocr_extract", {"image_id": "outside", "language": "en"}))
                assert missing["success"] is False and missing["status"] == "invalid_image_input"
                corrupt = _payload(await session.call_tool("ocr_extract", {"image_id": "broken", "language": "en"}))
                assert corrupt["success"] is False and corrupt["status"] == "invalid_image_input"
                invalid_language = _payload(await session.call_tool("ocr_extract", {"image_id": "english", "language": "fr"}))
                assert invalid_language["success"] is False and invalid_language["status"] == "invalid_language"
                invalid_parameter = await session.call_tool("ocr_extract", {"image_id": 123, "language": "en"})
                assert invalid_parameter.isError is True

    asyncio.run(asyncio.wait_for(exercise(), timeout=75))

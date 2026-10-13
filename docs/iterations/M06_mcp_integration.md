# M06 — MCP servers and Host workflow

## Purpose

Connect restricted database and OCR capabilities through the MCP protocol while requiring explicit human approval before business-data writes.

## Scope and implementation

- `app/mcp/servers/database/` exposes restricted tools, `db://schema`, and the workflow prompt over stdio.
- `app/mcp/servers/ocr/` exposes real RapidOCR extraction over stdio with constrained image access.
- `app/mcp/host.py` launches and calls MCP servers, binds staged images to user/session, tracks pending operations, and enforces confirmation.
- `app/mcp/planner.py` selects among the Host's bounded operations independently of the Stage 3 intent Router.
- Confirmation triggers a database write followed by read-only verification; OCR output is treated as untrusted data.

## Request chain

`ChatService → MCPToolPlanner → MCPHost → OCR MCP and/or Database MCP → review payload → explicit confirmation → database write → verification → answer`.

## Validation and limits

SDK protocol tests are in `tests/integration/test_database_mcp_protocol.py` and `tests/integration/test_ocr_mcp_protocol.py`; Host workflow coverage is in `tests/integration/test_mcp_host_workflow.py`. `scripts/mcp_b6_http_acceptance.py` is the isolated HTTP end-to-end acceptance entry. MCP Inspector GUI demonstration is separate and must not be claimed from SDK tests.

## Evidence locations

- Source: `app/mcp/host.py`, `app/mcp/planner.py`, `app/mcp/servers/database/`, `app/mcp/servers/ocr/`
- Tests: `tests/unit/test_database_mcp.py`, `tests/unit/test_ocr_mcp.py`, protocol and Host integration tests
- E2E: `scripts/mcp_b6_http_acceptance.py`

## Reuse and implementation notes

- **Previous capability/problem:** M05 produced RAG/web evidence but did not expose local OCR/database actions through a standard protocol with approval.
- **New functions:** two stdio MCP servers, tools/resources/prompts, protocol client/Host, bounded planner, user/session-bound image staging, review, approval, write and verification; API Settings and session UX are product surfaces on the same app.
- **Technology roles:** MCP SDK carries initialize/list/read/get/call; Database server constrains SQLite operations; RapidOCR supplies image recognition; Host enforces authorization and one-time approval; Streamlit presents review and status.
- **Core interfaces:** `ocr_extract`, `db_create_table`, `db_insert_rows`, `db_query_readonly`, `db://schema`, `ocr_to_db_workflow`, `MCPHost`, `MCPToolPlanner`.
- **Implementation/call chain:** `User → ChatService/Planner → Host MCP client → OCR → review → explicit confirmation → Database MCP → read-only query verification → answer`.
- **Decoupling/reuse:** Stage 3 Router stays three-class; planner is separate; business MCP DB is distinct from chat/CRM DB; OCR output is untrusted. Each server can be used by another MCP-compatible host within its schema/security contract.
- **Acceptance:** SDK protocol tests are not MCP Inspector GUI acceptance; isolated E2E is tested separately.
- **Known limits:** no native model Function Calling claim, production identity system, or Inspector PASS without its distinct demonstration; OCR quality is limited to tested inputs.

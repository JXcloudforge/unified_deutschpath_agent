# Database MCP Server (B4)

The standalone server runs over MCP stdio and uses the official MCP Python SDK
`mcp==1.30.0`. It is independent of the FastAPI chat/CRM database and Chroma.

From the project root, set a dedicated database path and run:

```powershell
$env:MCP_DATABASE_PATH = (Join-Path $PWD 'data\mcp_business.sqlite3')
python -m app.mcp.servers.database.server
```

If `MCP_DATABASE_PATH` is omitted, the server uses
`<STAGE2_DATA_PATH or project data>/mcp_business.sqlite3`. The server rejects the
Stage 2 `stage2.db` path and any path inside the Chroma directory. Importing the
server does not create a database. `db://schema` reports only tables named with
the `biz_` prefix and does not reveal local paths.

## Tools

- `db_create_table`: creates a new `biz_` table with at most 20 validated
  `TEXT`, `INTEGER`, `REAL`, or `BOOLEAN` columns; existing tables are preserved.
- `db_insert_rows`: accepts at most 50 rows and uses parameterized writes in one
  SQLite transaction. It requires a one-use local approval ticket bound to the
  exact operation ID, table, and row payload. The operation ID prevents replay.
- `db_query_readonly`: accepts selected fields and structured filters only,
  uses a SQLite read-only connection, and returns at most 100 rows.

The trusted host may issue an approval only after the user confirms the exact
payload:

```python
from app.mcp.servers.database import issue_write_approval

ticket = issue_write_approval(
    database_path,
    operation_id,
    table,
    rows,
)
```

This host-side function is not registered as an MCP tool. Keep the returned
ticket outside model context until confirmation. The current B4 standalone
server does not include the B6 chat confirmation UI or MCP client integration.

The registered prompt `ocr_to_db_workflow` documents OCR review, user
confirmation, approved writing, and read-back verification. OCR itself is not
part of B4.

## B4 acceptance record (2026-10-12)

The SDK stdio client initialized a separate server process and negotiated
protocol `2025-11-25`. Server info was `Deutschpath Database MCP` version
`1.30.0`; initialization advertised `tools`, `resources`, and `prompts`
(plus the SDK's `experimental` capability). Discovery returned exactly the
three tools above, `db://schema`, and `ocr_to_db_workflow`. Protocol calls
covered table creation, denied unapproved writes, read-only query, schema read,
and prompt retrieval.

MCP Inspector verification is **BLOCKED**: Node `v24.19.0` is present, but
`npm` and `npx` are not installed or available on PATH, so the official
Inspector CLI could not be launched. SDK protocol verification is independent
and passed. TestClient remains excluded from the project's non-HTTP regression
because of the previously isolated Windows AnyIO issue.

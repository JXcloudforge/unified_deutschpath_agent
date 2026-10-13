"""Official MCP stdio server exposing bounded business-database operations."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from .database import DatabaseMCP


def build_server(database_path: str | None = None) -> FastMCP:
    database = DatabaseMCP(database_path)
    server = FastMCP(
        "Deutschpath Database MCP",
        instructions=(
            "Access only approved biz_ business tables through the declared tools. "
            "Never submit SQL or a database path. Writes require a one-time approval "
            "ticket issued by the trusted local host after the user confirms the payload."
        ),
        log_level="WARNING",
    )

    @server.tool()
    def db_create_table(table: str, columns: list[dict[str, Any]]) -> dict[str, Any]:
        """Create a new biz_ table with 1-20 named TEXT/INTEGER/REAL/BOOLEAN columns."""
        return database.create_table(table, columns)

    @server.tool()
    def db_insert_rows(
        table: str,
        operation_id: str,
        rows: list[dict[str, Any]],
        approval_ticket: str,
    ) -> dict[str, Any]:
        """Insert at most 50 validated rows using an exact, one-use host approval."""
        return database.insert_rows(table, operation_id, rows, approval_ticket)

    @server.tool()
    def db_query_readonly(
        table: str,
        columns: list[str],
        filters: list[dict[str, Any]] | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Read selected columns from a biz_ table using structured filters only."""
        return database.query_readonly(table, columns, filters, limit)

    @server.resource(
        "db://schema",
        name="db_schema",
        description="Schema for MCP business tables only; excludes app state and local paths.",
        mime_type="application/json",
    )
    def db_schema() -> str:
        return database.schema_resource()

    @server.prompt(name="ocr_to_db_workflow")
    def ocr_to_db_workflow() -> str:
        """Standard human-confirmed OCR extraction and database verification workflow."""
        return (
            "OCR to database workflow:\n"
            "1. Obtain the OCR result from the authorized OCR service.\n"
            "2. Show the raw recognized text and candidate table rows to the user.\n"
            "3. Ask the user to review and correct every field; do not infer missing data.\n"
            "4. After explicit confirmation, have the trusted local host issue a one-use "
            "approval ticket bound to the exact table, operation ID, and rows.\n"
            "5. Call db_insert_rows with that ticket; never claim a write succeeded unless "
            "the tool returns status=inserted.\n"
            "6. Call db_query_readonly to verify the inserted values.\n"
            "7. Report the verified result and any failure without fabricating completion."
        )

    return server


def main() -> None:
    # FastMCP's stdio transport reserves stdout for protocol frames.
    build_server().run(transport="stdio")


if __name__ == "__main__":
    main()

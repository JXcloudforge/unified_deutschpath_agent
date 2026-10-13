# MCP orchestration integration point (B3 design only)

B3 leaves the Stage 3 request path unchanged. When B4–B6 are authorized, call a bounded Tool Planner from UnifiedOrchestrator after the existing three-class intent decision and before evidence assembly. This is an optional capability for a routed request; it must not add a fourth Router intent or replace rag, web_search, or no_tool.

- Reuse the 01_agent ToolRegistry only after confirming its schemas and adapting its registration boundary to the existing orchestrator.
- Reuse 02_crm_agent ToolExecutor validation patterns behind a small adapter; retain explicit per-tool authorization, bounded steps, deduplication, and confirmation for writes.
- Map validated MCP results to source-labelled evidence and pass them through the existing EvidenceAggregator and ContextBuilder; preserve tool identity and server provenance.
- Keep one request loop: UnifiedOrchestrator dispatches, the planner selects a bounded tool, the MCP client executes it, and the current context/LLM path answers. Do not create a second autonomous Agent loop.
- Tool failure yields a controlled failure, never fabricated success. Persist tool-call traces only after reviewing SQLite migrations and designing a rollback plan.

This is a design note only. It adds no MCP server, client, planner, registry, schema, or persistence code.

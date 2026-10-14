# Feature status

Status labels describe implementation and evidence separately. Provider keys
configured in a local `.env` do not prove remote connectivity. Router results
on engineering candidates are not formal independent acceptance results.

| Module | Feature and source entry | Tests / evidence | Implementation | Acceptance status |
|---|---|---|---|---|
| LLM | `app/llm/client.py`: `FakeLLM`, `DeepSeekLLM`, `build_llm` | `tests/unit/test_config.py`, `tests/unit/test_local_settings.py`, `tests/integration/test_stage2_flow.py` | IMPLEMENTED | Fake/offline TESTED; DeepSeek key is configured locally; live call NOT VERIFIED in this maintenance run |
| CRM | `app/users/service.py`, `app/users/repository.py`, `/users/me/*` | `tests/unit/test_user_state.py`, `scripts/http_acceptance.py --crm` | IMPLEMENTED | TESTED with isolated HTTP and SQLite data |
| Session / M07 Conversation | `app/chat/contracts.py`, `app/chat/context.py`, `app/chat/service.py`, `/sessions` | `tests/unit/test_chat_contracts.py`, `tests/integration/test_chat_service.py`, `tests/integration/test_architecture_acceptance.py`, M07 suite `206 passed, 1 skipped`; `scripts/mcp_b6_http_acceptance.py` | IMPLEMENTED (M07 initial) | Command/Query DTOs, bounded history and owner scope TESTED; HTTP/MCP confirmation E2E TESTED; context is character bounded (not exact token budget); summary persistence NOT IMPLEMENTED; archive/restore BLOCKED pending schema approval |
| RAG | `app/rag/`, `ChromaVectorStore` | `tests/unit/test_vector_store_lifecycle.py`, `tests/integration/test_stage2_flow.py` | IMPLEMENTED | TESTED with isolated Chroma and deterministic embeddings |
| Files | `app/files/service.py`, parser registry | `tests/unit/test_files.py`, `scripts/http_acceptance.py --crm` | IMPLEMENTED | TXT/MD/PDF/DOCX paths TESTED; parser limits documented in code |
| Router | `app/routing/` | `tests/unit/test_intent_router.py`, `tests/unit/test_hybrid_router.py`, `evals/` | IMPLEMENTED | Three-way and `mixed_sources` contracts TESTED; candidate results are development evidence; formal 98% NOT VERIFIED |
| Web Search | `app/web/tavily.py`, `SearchQueryBuilder` | `tests/unit/test_tavily_provider.py`, `tests/integration/test_web_search_orchestration.py` | IMPLEMENTED | Offline/error paths TESTED; Tavily key configured locally; live connectivity NOT VERIFIED in this maintenance run |
| Evidence | `app/agent/evidence.py`, orchestrator mixed path | `tests/unit/test_evidence.py`, `tests/integration/test_mixed_sources.py` | IMPLEMENTED | TESTED with controlled providers; historical live Mixed Sources PASS is in prior P0 evidence |
| Database MCP | `app/mcp/servers/database/` | `tests/unit/test_database_mcp.py`, `tests/integration/test_database_mcp_protocol.py` | IMPLEMENTED | Real SDK protocol tests TESTED; separate business SQLite |
| OCR MCP | `app/mcp/servers/ocr/` | `tests/unit/test_ocr_mcp.py`, `tests/integration/test_ocr_mcp_protocol.py`, `tests/fixtures/ocr/` | IMPLEMENTED | Real RapidOCR fixtures and stdio protocol TESTED; OCR quality is bounded by the recorded fixture set |
| MCP Host | `app/mcp/host.py`, `app/mcp/planner.py` | `tests/integration/test_mcp_host_workflow.py`, `scripts/mcp_b6_http_acceptance.py` | IMPLEMENTED | Confirmation-gated OCR→DB→query flow TESTED by isolated workflow acceptance |
| UI | `ui/streamlit_app.py`, `ui/api_client.py` | `tests/unit/test_ui_profile.py` | IMPLEMENTED | Streamlit AppTest TESTED; real browser interaction NOT VERIFIED in this maintenance run |
| API Settings | `ui/local_settings.py`, collapsed Streamlit expander | `tests/unit/test_local_settings.py`, `tests/unit/test_ui_profile.py` | IMPLEMENTED | Password input, local save rules, and status handling TESTED; credentials are never recorded here |
| System information / release notes | `app/version.py`, `ui/version_info.py`, allowlisted `docs/releases/` | `tests/unit/test_version_info.py`, `tests/unit/test_ui_profile.py` | IMPLEMENTED | Version comes from pyproject metadata; local release-note panel covered by AppTest; this is documentation, not an update service |
| Technical evolution timeline | `docs/iterations/manifest.json`, `docs/iterations/M01–M06` | `tests/unit/test_version_info.py`, `tests/unit/test_ui_profile.py` | IMPLEMENTED | Manifest validation and six collapsed milestone panels are AppTest-covered; records summarize current source and evidence |

## Planned / blocked

- Session archive and restore: BLOCKED until the additive `archived_at`
  migration, backup, integrity verification, and rollback plan in
  `docs/p1_2_archive_migration.md` is approved.
- Permanent session deletion: PLANNED only; requires a cross-storage cleanup
  and recovery design for Messages, Attachments, Chroma, OCR, and MCP state.
- MCP Inspector GUI: NOT VERIFIED by this maintenance run; SDK protocol tests
  are not Inspector acceptance.
- Router 98%: NOT VERIFIED on an independent human-labeled frozen set.

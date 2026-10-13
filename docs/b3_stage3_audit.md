# B3 Stage 3 audit status

## Current call paths

- No-tool: ChatService -> UnifiedOrchestrator -> three-class Router -> ContextBuilder with user/history context -> LLM. The existing orchestration tests assert that this path does not call RAG or Web Search.
- RAG: ChatService -> UnifiedOrchestrator -> Router -> current attachment (direct context or `session:<id>` Chroma namespace) -> knowledge namespace fallback -> ContextBuilder -> LLM. Existing tests cover session namespace and user/session separation.
- Web: Router -> SearchQueryBuilder -> WebSearchProvider -> evidence text -> LLM. The answer cites URLs returned by the provider. QueryGuard blocks common PII/secrets/private-content markers; a block never falls back to the original query.
- Mixed sources: Router marks `mixed_sources` on `web_search`; local attachment/session retrieval stays local while only the public query reaches WebSearchProvider. EvidenceAggregator retains local/web provenance, deduplicates, and bounds context. Existing fake-provider tests cover failures and prompt-injection instructions.

## Health and evaluation

`/health` now reads the active orchestrator dependencies and reports configured router mode, router initialization, provider initialization, Tavily key presence, and remote connectivity as `not_tested`. Key presence is not described as a successful connection. The legacy `stage` field remains for response compatibility.

The checked-in 300-case report is an engineering-candidate result from an earlier run (260/300, 86.67%, macro F1 0.8688; mixed-source 15/15). It is not a current B3 rerun and is not human-validated. The previous 29-case Hybrid experiment is also engineering-authored and human review pending. Neither establishes the 98% target. `evals/b3_router_review_candidates.csv` contains 150 new unreviewed candidates with blank labels, including 15 attachment-plus-current-information cases; follow the annotation guide and freeze adjudicated labels before evaluating.

## B3-R recovery and verification

The B3 run and B3-R run observed different execution access: B3's Python process could not resolve `D:\python\python.exe`, while B3-R PowerShell ran from the actual D: project directory and `Test-Path` found both the base interpreter and `.venv\Scripts\python.exe`. The base and venv both report Python 3.14.6; `sys.prefix` is the project `.venv`, `sys.base_prefix` is `D:\python`, and the required range `>=3.14,<3.15` matches. The configured FastAPI/Uvicorn/Starlette/AnyIO/httpx/Chroma/pytest packages import successfully. Evidence indicates a per-turn sandbox/filesystem view difference, not a damaged project venv. The venv launcher still emits a `Failed to find real location` warning, but continues to execute the interpreter and tests.

The current `.env` contains two `STAGE2_EMBEDDING_PROVIDER` entries: line 4 says `deterministic`, line 7 says `e5`; python-dotenv resolves the later value (`e5`). With that effective setting, faulthandler showed app import inside `sentence_transformers`/Torch source inspection for over 20 seconds. No model download was allowed. Explicitly setting the process environment to `deterministic` made app import complete promptly. This config explains a heavy, quiet startup path, but does not prove it alone caused the B3 shell's missing logs; B3-R also confirmed ordinary sandboxed loopback clients are denied.

The ordinary restricted process could bind a loopback socket but could not connect to it (`WinError 10013`). The explicitly authorized local-only elevated test context could connect/accept successfully. No external search was sent by the HTTP acceptance.

- Full non-TestClient regression: 133 passed, 0 failed, 0 skipped; the existing `tests/integration/test_api_smoke.py` remains outside this run per its known TestClient/AnyIO portal issue. The five Streamlit AppTests initially blocked in the restricted context but passed under the authorized loopback context. A consolidated rerun used only that one TestClient exclusion.
- `compileall -q app ui scripts tests`: PASS.
- Existing real Uvicorn start script and HTTP acceptance (`--crm`): PASS using FakeLLM, deterministic embeddings, a fresh `.pytest-b3-http-data-4` directory, and no Tavily key. `/health`, session/message/history, CRM profile/events, attachment upload, and user/session isolation checks succeeded. Web search returned a controlled offline failure. Uvicorn logged application shutdown complete after Ctrl+C; Chroma lifecycle tests passed.
- Current 300-case Rules candidate rerun: 268/300 (89.33%), macro F1 0.8945, mixed-source 15/15. The old checked-in report was 260/300 and is stale relative to current code. Neither dataset is human-validated.
- Real Hybrid holdout script attempted 12 DeepSeek calls out of 29 cases; all 12 failed and were safely handled by rules fallback. With failed-call timing now recorded, average request duration was 7.60 ms and p95 15.73 ms. The displayed 23/29 Hybrid decisions are fallback decisions, not successful DeepSeek classifications; actual Hybrid model evaluation is NOT VERIFIED.
- No Tavily key was configured; Tavily real search remains NOT TESTED. The 150-case review file remains unlabelled.

The Stage 3 engineering regression gate passes. The 98% intent target remains NOT MET; real Tavily and successful DeepSeek Hybrid evaluation remain unverified. B3 does not claim those quality/service indicators as passed.

## Data-safety note

The first B3-R run collected the then-current health test, whose module-level import constructed the default app before the isolation fixture was added. That import may have opened the repository's default `data/chroma`. At inspection, `data/chroma/chroma.sqlite3` had a last-write time of 2026-10-12 18:06:45 while `data/stage2.db` retained its 2026-09-22 timestamp. No chat or user-state requests, RAG query/upsert, or upload request was sent to the default data path; module import did construct repositories and execute `CREATE TABLE IF NOT EXISTS` DDL against `stage2.db`. No pre-run Chroma timestamp or file hash was recorded, so a Chroma metadata touch cannot be ruled out. The health test now imports the app only after setting a fresh `tmp_path` and closes that Chroma client. Later test and HTTP runs used isolated paths. The default Chroma store was not restored, deleted, or otherwise edited after discovery.

## B4–B6 integration point

See `stage3_mcp_integration.md`. No MCP implementation or persistence schema was added in B3.

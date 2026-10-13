# Stage 3 Engineering Freeze Acceptance

Date: 2026-10-10
Scope: Stage 3 engineering freeze only. No final Git commit, tag, or push was made.

## Status summary

| Area | Status | Evidence |
| --- | --- | --- |
| Stage 2 baseline: FastAPI, chat persistence, SQLite, RAG, file parsing, uploads | PASS | Included in the final non-HTTP regression. |
| P1 intent routes: `rag`, `web_search`, `no_tool` | PASS | Router unit and orchestration tests pass. |
| P2 Tavily provider boundary | PASS | Mock request, response parsing, timeout, HTTP error, missing-key, and safety tests pass. |
| P3 mixed local + web evidence | PASS | Fake-provider integration tests verify local/session evidence, web URLs, isolated namespaces, and controlled partial failure. |
| P4 hybrid routing engineering work | PARTIAL | Real DeepSeek was previously called successfully, but the candidate dataset is not a formally human-validated 98% acceptance set. |
| P4.5 outbound-query safety | PASS | Sensitive candidate tests verify rejection before the provider; mixed paths preserve local evidence without sending its body externally. |
| Final non-HTTP regression | PASS | `77 passed, 0 failed` on 2026-10-10. |
| Python syntax compilation | PASS | `python -m compileall -q app ui scripts` completed with no syntax errors. |
| Real Tavily API | NOT TESTED | No `TAVILY_API_KEY` was configured; no external request was sent. |
| Controlled real HTTP acceptance | PARTIAL | The project contains `scripts/http_acceptance.py` for isolated Uvicorn verification; this freeze did not rerun it because the Web/Mixed live path cannot be completed without Tavily credentials. |
| In-process FastAPI TestClient smoke test | BLOCKED | A minimal reproduction previously showed Windows Python 3.14 AnyIO/TestClient portal initialization blocking. It is excluded from the 77-test result. |

## Verified commands

```powershell
.\.venv\Scripts\python.exe -m pytest -q --ignore tests/integration/test_api_smoke.py --basetemp .pytest-stage3-freeze
# 77 passed, 0 failed

.\.venv\Scripts\python.exe -m compileall -q app ui scripts
# completed successfully
```

The virtual-environment launcher emits a stale-path diagnostic for `D:\python\python.exe`,
but the commands above completed with the project environment and its installed packages.
This is an environment-maintenance risk, not a passing TestClient result.

## Security and data boundary

- `.env` is ignored and `.env.example` contains empty placeholders only.
- Runtime SQLite, Chroma, and upload data are ignored; no production data was deleted or modified during freeze preparation.
- `SearchQueryBuilder` rejects common PII, secret, internal-document, and attachment-body patterns. It fails closed and never substitutes the full original private request after rejection.
- `TavilySearchProvider` repeats this check at the final outbound boundary, so direct provider calls cannot bypass the Orchestrator guard.
- Web snippets are labelled untrusted evidence. They cannot become orchestration instructions; prompt-injection and fabricated-citation attempts are tested as untrusted text.

## Remaining work before full Stage 3 release acceptance

1. Set `TAVILY_API_KEY` locally and run `scripts/verify_tavily_live.py` with public queries only.
2. Start Uvicorn with an isolated `STAGE2_DATA_PATH`, then run `scripts/http_acceptance.py`; perform the real Web Search and mixed-source acceptance cases with tool-call logging.
3. Build and human-review an independent routing evaluation dataset before claiming the required 98% classification accuracy.
4. Resolve or version-pin the Windows Python 3.14 / AnyIO / Starlette TestClient compatibility problem, then restore the HTTP smoke test to the default test run.
5. Recreate the local `.venv` if the stale `D:\python\python.exe` launcher diagnostic persists.

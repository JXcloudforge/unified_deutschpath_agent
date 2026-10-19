# Engineering Portfolio Evidence | Deutschpath Unified Agent

> Portfolio documentation draft. Scope: public repository **v0.2.1** (local integration release). This page does **not** claim production deployment, independent 98% Router accuracy, or that all source code was manually typed by one person.

## 1. What problem does the project solve?

The project combines German-learning chat, learner state, session-specific document retrieval, and controlled tool/workflow actions. An answer in a chat window is not sufficient evidence that a business operation has completed. The engineering focus is the path from a user request to an authorized, verifiable outcome.

**Role positioning:** AI-assisted application engineering. Project work is organized around requirement decomposition, module/API contracts, architecture trade-offs, AI Coding collaboration, test design, diff review, and evidence-based acceptance. Specific personal contributions should be corroborated through commits, design records, and interview demonstrations; the existence of code alone does not prove sole authorship.

## 2. Verified public repository architecture

```text
Streamlit UI
   -> FastAPI / Auth & API DTOs
   -> Conversation Service / UserState Service
   -> UnifiedOrchestrator
      -> Intent Router: rag | web_search | no_tool
      -> RAG Service: File Parsing -> Chroma -> Retrieval -> Evidence
      -> LLM Adapter: FakeLLM / optional DeepSeek
   -> bounded M08 Orchestration: Proposal -> Clarification -> Confirm
      -> Conversation Command -> Conversation Query (read-back)
   -> module-owned SQLite / Chroma
```

Principal tools: Python 3.14, FastAPI/Uvicorn, Streamlit, SQLite, ChromaDB, MCP SDK, RapidOCR, pytest. External DeepSeek/Tavily require configuration and separate live validation. See [Technical Stack](../TECH_STACK.md) and [Module Boundaries](../architecture/MODULE_BOUNDARIES.md).

**Boundary choices**
- UI consumes HTTP DTOs; it does not access Chat SQLite directly.
- Conversation/UserState/RAG modules own their data access; orchestration uses published Command/Query contracts.
- MCP is a tool protocol, not an approval substitute. Mutating tools require explicit controls, and business read-back must verify actual result.
- The intent Router covers three choices only; M08 supports a bounded session-renaming workflow, not arbitrary autonomous planning.
- A saved approval/proposal state is not equivalent to a completed database transaction.

## 3. A concrete engineering incident: wrong running process

**Problem:** A local UI did not enter the expected M08 rename proposal flow.

**Diagnosis:** Process command line and `/health` showed the active service came from an older development directory, with M08 disabled. In addition, the parser missed a Chinese rename wording, and the UI client did not preserve the orchestration response DTO.

**Decision:** Do not retrain the LLM or rewrite the Agent. Provide isolated DemoMode and process/health checks; patch the parser and UI DTO forwarding; read back the renamed session via Conversation Query, then refresh the title.

**Evidence:** [v0.2.1 release report](../releases/v0.2.1.md) contains the original problem, root cause, scope, commands, tests, and limits.

## 4. Reproduce safely (Windows / PowerShell)

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\scripts\start_app.ps1 -DemoMode
```

DemoMode is bound to loopback and uses FakeLLM and isolated demo data. Do not treat it as public deployment. See [Demo Guide](../demo/README.md). In separate terminals or after stopping the demo, run the repository's tests:

```powershell
.\scripts\run_tests.ps1
& .\.venv\Scripts\python.exe -m pytest -q tests/integration/test_api_smoke.py
```

**Evidence recorded at v0.2.1 release (not rerun for this portfolio draft):** 276 passed / 1 skipped / 0 failed for the suite, and independent API smoke 1 passed. Other M08/M09/MCP loopback acceptances are described in the release report. See test scope and exclusions before quoting totals.

## 5. Quality gates and current limits

- **Data:** document/source/version/ACL; vector index is not the authority on permissions.
- **Execution:** effective model/Router version, process path, request trace, authorized Tool/Command parameters.
- **Result:** business Query or database read-back plus negative-path tests; HTTP 200 alone is insufficient.
- **Change control:** Objective, Scope, Contract, Tests, Evidence, Rollback; preserve unchanged working behavior.
- **Release decisions:** PASS / FAIL / BLOCKED / NOT VERIFIED according to evidence, not marketing language.

**NOT VERIFIED for production:** real OIDC public multi-user integration, end-to-end real provider availability/cost, 150-label independent Router evaluation, MCP Inspector GUI, Docker/Caddy HTTPS/recovery/monitoring. [Release blockers](../RELEASE_BLOCKERS.md) contain details.

## 6. Interview story in 90 seconds

> I worked on a German-learning AI application that combines chat, learner state, session document RAG, and carefully bounded actions. The core design uses Streamlit and FastAPI, with Router, RAG, LLM, Conversation, and UserState behind interfaces; Chat owns its SQLite, while RAG owns Chroma. I focused on using AI Coding as an implementation accelerator while controlling requirements, interface boundaries, test cases and evidence. In one release, the UI showed that orchestration was missing. Instead of changing prompts, the team traced the running process and health config to an older instance, fixed a parser wording gap and response DTO handling, then verified actual session renaming via a business read-back. The v0.2.1 release includes reproducible test records; it is a local integrated release, not a validated public production deployment.

## 7. Interviewer verification route

1. Read [README](../../README.md) and [Architecture](../../ARCHITECTURE.md).
2. Inspect [Module Boundaries](../architecture/MODULE_BOUNDARIES.md).
3. Reproduce isolated [DemoMode](../demo/README.md) and run tests.
4. Trace one M08 command-to-query flow and inspect negative tests.
5. Compare the release claims and [unclosed blockers](../RELEASE_BLOCKERS.md).

*This file is documentation only. No production database, model artifacts or business code were changed in this documentation branch.*

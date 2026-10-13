# Changelog

This file records repository evidence and current working-tree state. A line
does not imply a Git commit or release tag unless one is listed explicitly.

## v0.1.1.dev0 — development candidate — 2026-10-13

### Final engineering freeze supplement — 2026-10-13

- **Documentation:** added retrospective M01–M06 technical records and a
  controlled `docs/iterations/manifest.json`; the README now contains the
  evolution index and State → Reasoning → Action diagram.
- **UI:** the system-information panel reads release history and six
  expandable milestones from repository-controlled manifest data. It shows
  concise feature/technology/chain/problem/status fields, not source files.
  Version remains sourced from `pyproject.toml` through `app/version.py`.
- **Verification:** current non-TestClient suite **200 passed, 1 skipped**;
  `compileall` passed. Isolated real-Uvicorn HTTP covered health, sessions,
  chat, RAG, offline Web fallback, CRM, and attachments. OCR → explicit review
  and confirmation → Database MCP write → query verification passed with three
  rows. Existing FastAPI OpenAPI and Streamlit health passed; launcher
  identity/preflight passed without stopping existing services.
- **External providers:** DeepSeek and Tavily were configured in the existing
  backend, but no external request was made in this freeze run; live status is
  **NOT TESTED** here. Historical P0 results remain historical evidence.
- **Git:** no commit, push, tag, index, or remote change. Target GitHub
  repository was checked read-only and appeared empty at this review; `origin`
  still points to the legacy CRM-agent repository. See
  `docs/releases/GITHUB_PUBLISH_CHECKLIST.md` before publication.

- **Maintenance:** removed verified generated pytest/acceptance directories from
  the main project and old 04 test runs, plus the archived 03/04 virtual
  environments. Workspace file usage fell from about 2.60 GiB to about 0.55 GiB
  (net reduction about 2.05 GiB). Formal data, root `.env`, and current `.venv`
  were kept. Unique historical credentials, databases, uploads, and nested Git
  metadata were preserved in the existing external backup root before removal
  of eligible work copies. This cleanup removed 02 fully; ACL-protected 01 and
  04 residuals and the 03 work copy remain.
- **Added:** `scripts/run_tests.ps1` runs the non-TestClient suite with pytest
  cache disabled and an isolated GUID directory under the system temp folder.
  It removes only its own run directory; `-KeepFailedArtifacts` explicitly
  preserves that directory on failure.
- **Tests:** 197 passed, 1 skipped in 83.82 seconds; `compileall` passed.
  A fresh isolated real-Uvicorn HTTP run passed health, session/chat, CRM,
  attachment, RAG, and controlled offline Web behavior. OCR → approval →
  Database MCP E2E passed with three verified rows and graceful shutdown. The
  live Streamlit health endpoint returned 200. Pytest left no owned temp run.
- **Known limits:** stale listeners on 8765/8501 were gracefully stopped after
  confirming their project process paths; 8000 was not touched. The isolated
  `.p1-2-browser-acceptance` databases were empty, its logs were retained in
  `docs/history/`, and its data directory was removed. The 03 legacy work copy
  remains because 21 generated test directories are inaccessible under their
  current Windows ACLs. The ZIP was absent from the main root; the existing
  `../Deutschpath_agent_archive/legacy/03_deutsch_chat.zip` remains unchanged.
- **Git:** no commit or tag was created; existing staged/unstaged state and
  the legacy `agent` gitlink state were left untouched.

- **Added:** session title search and persistent rename in the local Streamlit
  interface; the FastAPI route scopes updates to the supplied local user ID.
- **Changed:** the application version now comes from `pyproject.toml` and is
  shown by FastAPI and Streamlit as `v0.1.1.dev0`.
- **Changed:** the local editable package metadata now matches `pyproject.toml`;
  refreshed with `pip install -e . --no-deps --no-build-isolation` and no
  dependency changes.
- **Changed:** one recommended `start.bat` coordinates the existing backend and
  frontend launch scripts and checks project ownership, health, and ports.
- **Maintained:** generated a source-focused external archive copy of all four
  historical project directories; every copied file was rechecked by SHA256.
- **Tests:** 197 passed, 1 skipped in the final non-TestClient suite; the skip
  is Windows symlink creation unavailable in the active account. `compileall`
  passed. Isolated real Uvicorn/HTTP, Streamlit health, launcher identity, and
  OCR→confirmation→Database MCP acceptance passed.
- **Known limits:** archive/restore UI awaits an additive database migration;
  live browser interaction and external provider connectivity are separate
  acceptance items. Formal independent 98% Router acceptance is not verified.
- **Git:** no commit or tag was created. Existing staged/unstaged work remains;
  the Windows TestClient smoke remains excluded and is not counted as passed.

- **Added:** release records for `v0.1.0-beta.1` and `v0.1.1.dev0`. The
  Streamlit settings sidebar now displays version and release notes from a
  fixed document allowlist; the version remains sourced from `pyproject.toml`.
- **Fixed:** `start.bat` readiness checks now inspect the server process under
  its PowerShell service window. The previous check inspected only the
  PowerShell wrapper and falsely timed out after successfully starting FastAPI.
- **Tests:** this final cleanup run passed 199 tests with 1 Windows symlink
  skip; compileall, real-Uvicorn HTTP/CRM, isolated OCR→approval→Database MCP
  E2E, and `start.bat` current-version checks passed. The full test run used and
  removed its own system-temp data directory.
- **Evidence:** cleanup sizes, protected-data checks, ACL-limited historical
  leftovers, and startup acceptance are recorded in
  `docs/history/final-cleanup-20261013.md`.

## v0.1.0-beta — B0–B7 integration record

The repository retains the historical B0–B7 evidence in
`docs/v0.1_beta_acceptance.md`, `docs/v0.1_migration_manifest.md`, and the
stage-specific audit documents. That record describes the beta integration of
the Agent, CRM/User State, chat API and UI, Stage 2 RAG, Stage 3 routing and
web evidence, Database MCP, OCR MCP, and the MCP Host workflow. Historical
reports are preserved as written; their test totals are not substituted for
the current maintenance run.

## v0.1.1 — earlier worktree changes

Earlier v0.1.1 P0/P1-1/P1-2 changes exist in the current working tree and
historical evaluation files. The P1-2 archive-field migration proposal is in
`docs/p1_2_archive_migration.md`. No formal release tag was found or created.

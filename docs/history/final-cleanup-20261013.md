# Final cleanup and release information — 2026-10-13

## Historical directories and protected data

- The external source archive at `../Deutschpath_agent_archive` was rechecked
  before cleanup: all 584 manifest entries matched their source SHA256 values.
- `02_crm_agent/` was removed. Its 97 Git tracked paths now appear as unstaged
  worktree deletions; the current index was not changed. Recovery is documented
  in `legacy-deletion-git-impact-20261013.txt` and the source archive.
- `01_agent/` has no accessible source/data files left; its nested `.git`
  remains because Windows denied deleting an object. The full nested metadata
  was copied and SHA256-verified under the existing external backup root.
- `04_stage2_unified_agent/` has no accessible files left; `.pytest_cache/` and
  `.pytest-stage2/` remain because Windows denied access. Its `.env`, data,
  uploads, and HTTP acceptance data were preserved and verified externally.
- `03_deutsch_chat/` remains because its 21 `.test-tmp-*` directories could not
  be safely inspected or deleted under their current ACLs. Its chat DB and
  Chroma diagnostic data were copied and verified externally. The existing
  `../Deutschpath_agent_archive/legacy/03_deutsch_chat.zip` was preserved; its
  archived database entries were not extracted or altered.
- The root `.p1-2-browser-acceptance/` held no rows in the isolated stage2 or
  MCP databases. Its backend/frontend logs were moved to this `docs/history/`
  directory, then the test database directory was removed. Ports 8765 and 8501
  were confirmed stopped; port 8000 remained untouched.
- The new preservation directory contains 295 preserved files plus its
  manifest: **7,434,815 bytes**. All manifest files verified successfully. The
  pre-existing B4 backup still passes all 10 manifest hashes. No
  `Deutschpath_agent_B7_backup_*` sibling was found during this check; none was
  modified.

## Disk usage

These are readable-file totals from the repository scanner; ACL-inaccessible
legacy paths are excluded from the readable totals.

| Location | Before this cleanup | After this cleanup |
|---|---:|---:|
| Main project readable files | 590,721,415 bytes (563.36 MiB) | 576,856,631 bytes (550.13 MiB) |
| Main project change | — | −13,864,784 bytes (−13.22 MiB) |
| New protected preservation files | — | +7,434,815 bytes (+7.09 MiB) |
| Net across main project and new preservation directory | — | **−6,429,969 bytes (−6.13 MiB)** |

The previous maintenance run had already reduced the workspace from about
2.60 GiB to about 0.55 GiB by removing old virtual environments and generated
test runs. This cleanup did not make another full project copy.

## Version information

- Current source version: `0.1.1.dev0`, read from `pyproject.toml` through
  `app/version.py`; status is an unreleased development candidate.
- Added fixed-path release notes for `v0.1.0-beta.1` and `v0.1.1.dev0`.
- Streamlit's collapsed **系统信息 · 版本更新** panel reads only those
  allowlisted documents and `docs/CHANGELOG.md`; it does not read local
  credentials or business data.
- No release commit or tag was created. The 300-case Router result remains
  development-candidate evidence; formal independent 98% acceptance remains
  **NOT VERIFIED**.

## Validation

- Full non-TestClient pytest: **199 passed, 1 skipped**, 1 upstream Chroma
  deprecation warning. The skip is Windows symlink creation unavailable.
- `compileall`: PASS.
- Isolated real-Uvicorn HTTP: `/health` 200, current OpenAPI version
  `0.1.1.dev0`, sessions/chat/history, RAG, controlled Web failure, CRM, and
  attachment checks passed; graceful shutdown.
- Database/OCR MCP confirmation-gated HTTP E2E: PASS; 3 rows inserted after
  explicit confirmation and read-back verification; graceful shutdown.
- `start.bat`: PASS after fixing readiness checks to inspect the Python server
  descendant under each PowerShell wrapper. FastAPI 8765 and Streamlit 8501
  health checks passed. The run used an isolated temp data path, then stopped
  both services. Personal OS on 8000 remained running.
- Browser UI loaded at `http://127.0.0.1:8501/`; the sidebar exposed the
  version-update expander. AppTest verified version/status and switching to the
  beta.1 history. A screenshot was not captured because the desktop browser
  automation session stopped after it could not determine the browser URL.

## Remaining cleanup limits

Windows denied removal of the nested `01_agent/.git` object and old test cache
directories in 03/04. They remain in their original paths and are not counted
as deleted. No ACL or ownership change was attempted. The root `.git`, index,
HEAD, active `.venv`, `.env`, and formal `data/` remain untouched.

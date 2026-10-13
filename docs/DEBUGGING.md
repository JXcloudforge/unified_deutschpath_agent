# Local operation and debugging

## One-click start

From the project root, double-click `start.bat` or run it from PowerShell. It
checks `.venv`, the declared Python version, imports, ports, and app health; it
starts backend and UI in separate PowerShell windows and opens the UI in the
default browser. It reuses an occupied port only if the listener is this
project's matching version and its health endpoint passes. Otherwise it exits
with the owning PID and leaves that process untouched.

Press **Ctrl+C in each Deutschpath server window** to stop its service. Stop the
Streamlit window first, then FastAPI. The launcher does not stop services it
did not start.

## Manual start

Open two PowerShell windows in the project root:

```powershell
.\scripts\start_backend.ps1
.\scripts\start_frontend.ps1
```

The API binds to `127.0.0.1:8765`; Streamlit binds to `127.0.0.1:8501`. Port
8000 belongs to Personal OS and is not used by Deutschpath. `GET /` may return
404; validate the API with `/health` and OpenAPI instead:

```powershell
Invoke-RestMethod http://127.0.0.1:8765/health
(Invoke-RestMethod http://127.0.0.1:8765/openapi.json).info
Invoke-WebRequest http://127.0.0.1:8501/_stcore/health -UseBasicParsing
```

## Port conflict

```powershell
Get-NetTCPConnection -State Listen -LocalPort 8765,8501
Get-CimInstance Win32_Process -Filter "ProcessId=<PID>" |
  Select-Object ProcessId,ExecutablePath,CommandLine
```

Do not stop a process solely because it owns a port. Confirm its executable,
command line, project root, OpenAPI title/version, and health response. The
launcher refuses unrelated listeners and does not touch port 8000.

## Provider configuration

- The root `.env` is local and Git-ignored. `.env.example` has empty key values.
- A process environment value takes precedence over `.env`; restart FastAPI
  after changing either source. The health response reports configured status
  and source, never the key value.
- DeepSeek not configured: confirm `DEEPSEEK_API_KEY` status in the local
  Streamlit API Settings panel. Empty key selects FakeLLM and returns an offline
  explanation. That does not demonstrate a live model call.
- Tavily failure: check `TAVILY_API_KEY`, network, quota, provider HTTP status,
  and QueryGuard. Key presence is configuration only; use an explicit live
  search check to establish connectivity.
- Never paste keys into chat, command history, issue reports, or test logs.

## RAG and file uploads

- Supported formats are TXT, MD, PDF, and DOCX. Check parser errors and whether
  the uploaded file contains extractable text.
- Small attachment content can enter the prompt directly; larger files use
  Chroma namespace `session:<session_id>`.
- Default runtime root is `data/`. `STAGE2_DATA_PATH` relocates SQLite, Chroma,
  uploads, OCR staging, and Host state together. Do not delete or replace this
  directory to troubleshoot; first back it up and use an isolated path.
- Deterministic embeddings are the offline test provider. E5 may require model
  cache/download and uses more resources.

## SQLite and Chroma

The current database/vector paths are determined by `STAGE2_DATA_PATH` and
`MCP_DATABASE_PATH`. The active API's `/health` reports providers but does not
reveal storage contents. For database inspection, stop the relevant local
service first and make a SQLite backup with the SQLite backup API. Keep backups
outside Git. Do not copy a live Chroma directory as a routine troubleshooting
step.

## MCP and OCR

- The Database and OCR servers use local stdio; they do not expose HTTP ports.
- Run protocol regression with:

  ```powershell
  .\.venv\Scripts\python.exe -m pytest -q tests/integration/test_database_mcp_protocol.py tests/integration/test_ocr_mcp_protocol.py
  ```

- The complete OCR-to-DB flow uses a temporary data root and fixture image:

  ```powershell
  .\.venv\Scripts\python.exe scripts/mcp_b6_http_acceptance.py
  ```

- OCR failures: check supported image type, size, image integrity, configured
  language data, and the returned structured error. OCR output is untrusted and
  database writes remain confirmation-gated.
- MCP Inspector is separate from SDK protocol tests; a passing pytest protocol
  test must not be described as Inspector GUI acceptance.

## Tests and logs

Run the non-TestClient regression through the cleanup-aware entry point:

```powershell
.\.venv\Scripts\python.exe -m compileall -q app ui scripts tests
.\scripts\run_tests.ps1
```

The runner allocates one GUID-named directory beneath the system temporary
folder, disables pytest's cache provider, and removes only that run directory
after completion. To preserve a failing run for diagnosis, opt in explicitly:

```powershell
.\scripts\run_tests.ps1 -KeepFailedArtifacts
```

The Windows TestClient smoke is excluded because its AnyIO portal issue is
tracked separately; it is not counted as a pass. Additional pytest arguments
can be passed through `-PytestArgs`, for example
`-PytestArgs @('tests/unit/test_health.py')`.

The TestClient smoke is excluded because the known Windows AnyIO portal issue
is a separate blocked test. The excluded test is not counted as passed. API and
Uvicorn logs are printed in their server windows; acceptance scripts may write
temporary logs beneath their isolated temp directory.

For a fresh HTTP test, use a new `STAGE2_DATA_PATH`, blank provider keys,
deterministic embeddings, and a free non-production port. Never point test
commands at formal `data/` or the Personal OS service.

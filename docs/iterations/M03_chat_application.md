# M03 — Chat application

## Purpose

Provide one local chat UI and one FastAPI backend with persistent sessions, history, file attachment flow, and explicit API configuration controls.

## Scope and implementation

- `app/api/main.py` creates the application services and exposes health, session, chat, CRM, file, and MCP Host routes.
- `app/chat/service.py` coordinates message persistence, attachment lookup, orchestration, and assistant-message persistence.
- `app/chat/repository.py` stores sessions and messages in SQLite.
- `ui/streamlit_app.py` is the recommended UI; `ui/api_client.py` centralizes backend requests.
- `ui/local_settings.py` and `ui/version_info.py` provide local configuration and repository-controlled release information.

## Request chain

`Streamlit → Stage2ApiClient → FastAPI → ChatService → ChatRepository/UnifiedOrchestrator → persisted response → session history refresh`.

## Validation and limits

App behavior is covered by `tests/unit/test_ui_profile.py` and chat service integration tests. `scripts/http_acceptance.py` exercises real Uvicorn HTTP. Session archive/restore remains blocked pending a schema migration; permanent deletion is not offered. Local `X-User-ID` is not production authentication.

## Evidence locations

- Source: `app/api/main.py`, `app/chat/`, `ui/streamlit_app.py`, `ui/api_client.py`
- Tests: `tests/unit/test_ui_profile.py`, `tests/integration/test_chat_service.py`, `tests/unit/test_health.py`

## Reuse and implementation notes

- **Previous capability/problem:** M01/M02 supplied answering and learner state but no web chat, durable history, or session selection.
- **New functions:** Streamlit interface, FastAPI backend, one API client, session create/list/rename, message persistence/history, attachment transport, and user scoping.
- **Technology roles:** Streamlit manages presentation state; HTTP client centralizes request/timeout behavior; FastAPI validates routes; `ChatService` coordinates repository/file/agent work; SQLite persists data.
- **Core interfaces:** `/health`, `/sessions`, chat send/history endpoints; `Stage2ApiClient`; `ChatService.create_session/send_message`; `ChatRepository` session/message methods.
- **Implementation/call chain:** user message is saved before orchestration; the assistant response is saved after completion; UI reads selected-session history and recovers uncertain POST results by querying history.
- **Decoupling/reuse:** UI can be replaced without bypassing APIs; services and repositories can be reused without Streamlit.
- **Acceptance:** AppTest and real Uvicorn HTTP acceptance are separate evidence; current-turn results are reported separately.
- **Known limits:** session archive/restore awaits a separately approved migration; user ID is not production authentication.

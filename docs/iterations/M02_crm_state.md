# M02 — CRM and learning state

## Purpose

Persist a learner profile and learning events under the same application identity used by chat, without maintaining a parallel CRM database.

## Scope and implementation

- `app/users/models.py` defines user-state and learning-event models.
- `app/users/repository.py` owns SQLite persistence.
- `app/users/service.py` validates and updates current/target level, learning goal, preferences, and event history.
- FastAPI exposes user-scoped profile and event operations through `app/api/main.py`.

## Request chain

`HTTP user-scoped route → UserStateService → UserStateRepository/SQLite → validated response`; the orchestrator reads learner context when constructing an answer.

## Validation and limits

Unit coverage is in `tests/unit/test_user_state.py`; isolated real HTTP checks are available through `scripts/http_acceptance.py --crm`. `X-User-ID` remains a local beta identifier, not production authentication.

## Evidence locations

- Source: `app/users/models.py`, `app/users/repository.py`, `app/users/service.py`
- Tests: `tests/unit/test_user_state.py`, `tests/integration/test_chat_service.py`
- HTTP acceptance: `scripts/http_acceptance.py`

## Reuse and implementation notes

- **Previous capability/problem:** M01 could answer a prompt but did not retain a structured learner profile between requests.
- **New functions:** current and target CEFR levels, learning goal, preferences, event recording/listing, persistence, and context contribution.
- **Technology roles:** models validate and serialize; repository handles parameterized SQLite persistence; service owns validation and convenient operations; FastAPI provides user-scoped transport.
- **Core types/interfaces:** `UserState`, `LearningEvent`, `LearningEventIn`, `UserStateService.get_user_state/update_user_state/save_learning_event/list_learning_events`.
- **Implementation/call chain:** `API → service validation → repository transaction → SQLite`; Agent reads resulting state and puts bounded learner fields in context.
- **Decoupling/reuse:** CRM operations do not leak into the orchestrator; another product can mount the repository/service under its own API and data root.
- **Acceptance:** unit tests plus isolated HTTP checks cited above. They do not validate production identity/authentication.
- **Known limits:** caller-provided `X-User-ID` is a local beta boundary only.

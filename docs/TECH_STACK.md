# Technology stack

## Declared and observed versions

Python constraints and dependency ranges are declared in `pyproject.toml`.
The versions below were read from the active `.venv` on 2026-10-13; the project
does not currently pin every package to an exact lockfile version.

| Component | Declared / observed version | Purpose and actual use |
|---|---|---|
| Application package | `0.1.1.dev0` in pyproject and editable distribution | Current development candidate; no release tag |
| Python | `>=3.14,<3.15`; observed 3.14.6 | Runtime for API, UI, tests, and MCP subprocesses |
| FastAPI | `>=0.115,<1`; observed 0.141.1 | HTTP API and application lifespan |
| Uvicorn | `>=0.30,<1`; observed 0.52.4 | ASGI server, loopback port 8765 by default |
| Streamlit | `>=1.40,<2`; observed 1.65.0 | Local chat interface, port 8501 by default |
| Pydantic | transitive; observed 2.13.4 | API schemas and validation |
| SQLite | Python stdlib; SQLite 3.50.4 | Chat/User State persistence and isolated MCP business database |
| ChromaDB | `>=1,<2`; observed 1.5.9 | Local knowledge and session RAG vector collections |
| DeepSeek API | external OpenAI-compatible endpoint | Optional `DeepSeekLLM`; selected only when `DEEPSEEK_API_KEY` is present |
| Tavily | HTTP adapter in `app/web/tavily.py` | Optional real web provider, guarded query builder and bounded result count |
| MCP Python SDK | `mcp==1.30.0`; observed 1.30.0 | stdio client/server protocol for Database and OCR MCP |
| RapidOCR | `rapidocr==3.10.0`; observed 3.10.0 | Local OCR engine, no model download at app startup |
| ONNX Runtime | observed 1.29.0 | CPU inference backend used by RapidOCR |
| pytest | `pytest>=8,<9`; observed 8.4.2 | Unit, integration, MCP protocol, and AppTest suite |
| HTTPX | `>=0.27,<1`; observed 0.28.1 | DeepSeek/Tavily adapters and real HTTP acceptance |
| sentence-transformers | `>=5.7,<6`; observed 5.7.0 | Optional E5 embedding provider; deterministic provider is the offline default |

## Request and tool relationships

- FastAPI `app/api/main.py` creates one `ChatService`, `UnifiedOrchestrator`,
  RAG service, User State service, and MCP Host.
- `ChatService` persists user/assistant messages through `ChatRepository`.
- The Stage 3 router chooses only `rag`, `web_search`, or `no_tool`; the
  `mixed_sources` flag remains evidence metadata.
- `MCPToolPlanner` is separate from that router. Trusted `MCPHost` adapters
  launch the two local stdio servers using the installed MCP SDK.
- SQLite and Chroma paths are rooted under `STAGE2_DATA_PATH`; the MCP business
  SQLite is separately configurable with `MCP_DATABASE_PATH`.
- Environment variables win over root `.env`; `.env.example` is the public
  configuration template. No credential values belong in docs or Git.
- `docs/iterations/manifest.json` is repository-owned presentation metadata for
  the Streamlit technical evolution panel; it is not a runtime service registry
  and cannot direct the UI to arbitrary file paths.

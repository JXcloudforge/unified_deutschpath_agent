from __future__ import annotations

import os
import ipaddress
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

from fastapi import Depends, FastAPI, File, Header, HTTPException, Query, Request, UploadFile
from pydantic import BaseModel, Field

from app.agent import UnifiedOrchestrator
from app.auth import AuthService, OIDCSettings
from app.auth.contracts import ActorContext
from app.auth.identity import IdentityDisabledError
from app.auth.verifier import AccessTokenError
from app.auth.service import AuthConfigurationError
from app.chat import ChatService
from app.config import setting_source
from app.files import FileService
from app.llm import build_llm
from app.mcp.host import MCPHost, MCPHostError
from app.mcp.planner import MCPToolPlanner
from app.orchestration import OrchestrationService
from app.orchestration.chat_adapter import ConversationListSessionsQuery, ConversationRenameExecutor, M08ChatAdapter
from app.rag import RAGService, build_embedding
from app.rag.vector_store import ChromaVectorStore
from app.routing import HybridIntentRouter, LLMIntentRouter, RuleBasedIntentRouter
from app.suggestions import FollowUpSuggestionService
from app.users import UserStateService
from app.users.models import LearningEvent, LearningEventIn, ProfileUpdate, UserState
from app.version import VERSION
from app.web import TavilySearchProvider

ROOT = Path(os.getenv("STAGE2_DATA_PATH", "data"))
MAX_ATTACHMENT_BYTES = 20 * 1024 * 1024
APP_ENV = os.getenv("APP_ENV", "development").strip().lower()
M08_LOCAL_ENABLED = os.getenv("M08_LOCAL_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}
rag = RAGService(ChromaVectorStore(ROOT / "chroma", build_embedding()))
llm = build_llm()
rules_router = RuleBasedIntentRouter()
router_mode = os.getenv("STAGE3_ROUTER", "rules").strip().lower()
router = HybridIntentRouter(rules_router, LLMIntentRouter(llm)) if router_mode == "hybrid" else rules_router
users = UserStateService.from_path(ROOT / "stage2.db")
mcp_host = MCPHost(ROOT)
mcp_tool_planner = MCPToolPlanner()
web_search = TavilySearchProvider()
orchestrator = UnifiedOrchestrator(rag, users, llm, router=router, web_search=web_search)
chat = ChatService.from_path(
    ROOT / "stage2.db",
    orchestrator,
    FileService(),
    mcp_host=mcp_host,
    mcp_planner=mcp_tool_planner,
)
m08_chat_adapter = None
m08_orchestration = None
if M08_LOCAL_ENABLED and APP_ENV == "development":
    m08_orchestration = OrchestrationService(
        ROOT / "orchestration.sqlite3", router, chat,
        {"rename_session": ConversationRenameExecutor(chat, chat),
         "list_sessions": ConversationListSessionsQuery(chat)},
    )
    m08_chat_adapter = M08ChatAdapter(chat, chat, m08_orchestration)
elif (ROOT / "orchestration.sqlite3").is_file():
    # Even with M08 writes disabled, M09 must observe a persisted pending state
    # and suppress recommendations instead of implying the operation is done.
    m08_orchestration = OrchestrationService(ROOT / "orchestration.sqlite3", router, chat, {})
suggestion_queries = FollowUpSuggestionService(chat, m08_orchestration)


@asynccontextmanager
async def lifespan(_: FastAPI):
    if m08_chat_adapter is not None and m08_orchestration is not None:
        m08_orchestration.recover_interrupted_executions()
    yield
    rag.store.close()


app = FastAPI(title="Deutschpath Unified Agent", version=VERSION, lifespan=lifespan)

auth_service: AuthService | None = None
auth_service_error: Exception | None = None


def _get_auth_service() -> AuthService | None:
    """Build OIDC services lazily so an unconfigured local install still starts."""
    global auth_service, auth_service_error
    if auth_service is not None:
        return auth_service
    if auth_service_error is not None:
        raise auth_service_error
    try:
        settings = OIDCSettings.from_environment(ROOT)
        if settings is None:
            return None
        auth_service = AuthService.from_settings(settings)
        return auth_service
    except Exception as exc:
        auth_service_error = exc
        raise


def get_actor_context(
    request: Request,
    authorization: str | None = Header(None),
    x_user_id: str | None = Header(None),
) -> ActorContext:
    """Resolve an authenticated actor; allow only loopback beta IDs in dev."""
    if authorization:
        scheme, separator, token = authorization.partition(" ")
        if not separator or scheme.casefold() != "bearer" or not token.strip():
            raise HTTPException(401, "Bearer access token required")
        try:
            service = _get_auth_service()
            if service is None:
                raise HTTPException(503, "OIDC authentication is not configured")
            return service.authenticate(token.strip())
        except HTTPException:
            raise
        except AccessTokenError:
            raise HTTPException(401, "Invalid access token")
        except IdentityDisabledError:
            raise HTTPException(403, "Account is disabled")
        except AuthConfigurationError:
            raise HTTPException(503, "OIDC authentication is unavailable")
        except Exception:
            # Provider/network/storage details and credentials must not leak.
            raise HTTPException(503, "Authentication service is unavailable")

    if is_loopback_development_request(request) and x_user_id and x_user_id.strip():
        return ActorContext.from_local_header(x_user_id)
    raise HTTPException(401, "Authentication required")


def is_loopback_development_request(request: Request) -> bool:
    """Recognize a direct loopback peer for the local beta identity fallback."""
    if APP_ENV != "development":
        return False
    if any(name in request.headers for name in ("forwarded", "x-forwarded-for", "x-forwarded-host", "x-forwarded-proto")):
        return False
    peer = request.scope.get("client")
    if not peer or not peer[0]:
        return False
    try:
        # Starlette's in-process TestClient uses this synthetic peer name.
        return peer[0] == "testclient" or ipaddress.ip_address(peer[0]).is_loopback
    except ValueError:
        return False


def is_local_development_request(request: Request) -> bool:
    return M08_LOCAL_ENABLED and is_loopback_development_request(request)

class MessageIn(BaseModel):
    content: str
    include_suggestions: bool = False

class SessionTitleIn(BaseModel):
    title: str = Field(min_length=1, max_length=100)

class OCRPreviewIn(BaseModel):
    image_id: str
    language: str = "de"

class OCRConfirmIn(BaseModel):
    operation_id: str
    rows: list[dict[str, str]]
    confirmed: bool

@app.get("/health")
def health():
    """Report local wiring and configuration without claiming remote connectivity."""
    active_router = router
    active_web_provider = web_search
    router_initialized = isinstance(active_router, (RuleBasedIntentRouter, HybridIntentRouter))
    effective_router_mode = "hybrid" if isinstance(active_router, HybridIntentRouter) else "rules"
    web_provider_initialized = isinstance(active_web_provider, TavilySearchProvider)
    web_key_configured = web_provider_initialized and bool(getattr(active_web_provider, "api_key", ""))
    active_llm = llm
    return {
        "status": "ok",
        "stage": 2,  # Kept for compatibility with the existing health response.
        "router": effective_router_mode if router_initialized else "unavailable",
        "router_configured_mode": router_mode,
        "router_initialized": router_initialized,
        "web_search": "configured" if web_key_configured else "not_configured",
        "web_provider_initialized": web_provider_initialized,
        "tavily_api_key_configured": web_key_configured,
        "tavily_connectivity": "not_tested",
        "llm_provider": type(active_llm).__name__,
        "llm_model": getattr(active_llm, "model", os.getenv("DEEPSEEK_MODEL", "deepseek-chat")),
        "deepseek_api_key_configured": type(active_llm).__name__ == "DeepSeekLLM",
        "deepseek_config_source": setting_source("DEEPSEEK_API_KEY"),
        "tavily_config_source": setting_source("TAVILY_API_KEY"),
        "m08_local_orchestration": bool(m08_chat_adapter),
        "app_environment": APP_ENV,
    }

@app.get("/users/me/state", response_model=UserState)
def get_user_state(actor: ActorContext = Depends(get_actor_context)):
    return users.get_user_state(actor.user_id)


@app.patch("/users/me/state", response_model=UserState)
def update_user_state(payload: ProfileUpdate, actor: ActorContext = Depends(get_actor_context)):
    return users.update_user_state(actor.user_id, **payload.model_dump(exclude_unset=True))


@app.get("/users/me/events", response_model=list[LearningEvent])
def learning_events(limit: int = Query(20, ge=1, le=100), actor: ActorContext = Depends(get_actor_context)):
    return users.list_learning_events(actor.user_id, limit=limit)


@app.post("/users/me/events", response_model=LearningEvent, status_code=201)
def save_learning_event(payload: LearningEventIn, actor: ActorContext = Depends(get_actor_context)):
    return users.save_learning_event(actor.user_id, **payload.model_dump())


@app.post("/sessions")
def create_session(actor: ActorContext = Depends(get_actor_context)):
    return chat.create_session(actor).to_dict()

@app.get("/sessions")
def list_sessions(actor: ActorContext = Depends(get_actor_context)):
    return [session.to_dict() for session in chat.list_sessions(actor)]

@app.patch("/sessions/{session_id}")
def rename_session(session_id: str, payload: SessionTitleIn, request: Request, actor: ActorContext = Depends(get_actor_context)):
    if not actor.authenticated and not is_loopback_development_request(request):
        raise HTTPException(403, "Local development actors require a direct localhost client")
    try:
        return chat.rename_session(actor, session_id, payload.title).to_dict()
    except KeyError:
        raise HTTPException(404, "Session not found")
    except ValueError as exc:
        raise HTTPException(422, str(exc))

@app.post("/sessions/{session_id}/messages")
def send_message(session_id: str, payload: MessageIn, request: Request, actor: ActorContext = Depends(get_actor_context)):
    if m08_chat_adapter is not None and not is_local_development_request(request):
        raise HTTPException(403, "M08 local orchestration accepts direct localhost requests only")
    try:
        handled = m08_chat_adapter.handle(actor, session_id, payload.content) if m08_chat_adapter else None
        result = handled or chat.send_message(actor, session_id, payload.content)
        response = result.to_dict()
        if payload.include_suggestions and result.orchestration is None:
            try:
                response["suggestions"] = [
                    item.to_dict() for item in suggestion_queries.get_follow_up_suggestions(actor, session_id)
                ]
            except Exception as exc:
                # Suggestions are optional and must never hide a successful answer.
                import logging
                logging.getLogger(__name__).warning("Follow-up suggestions unavailable (%s)", type(exc).__name__)
        return response
    except KeyError: raise HTTPException(404, "Session not found")
    except ValueError as exc: raise HTTPException(422, str(exc))
    except RuntimeError: raise HTTPException(502, "Agent service failed")

@app.get("/sessions/{session_id}/messages")
def messages(session_id: str, actor: ActorContext = Depends(get_actor_context)):
    try: return [message.to_dict() for message in chat.get_messages(actor, session_id)]
    except KeyError: raise HTTPException(404, "Session not found")

@app.post("/sessions/{session_id}/attachments")
def upload(session_id: str, request: Request, file: UploadFile = File(...), actor: ActorContext = Depends(get_actor_context)):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".txt", ".md", ".pdf", ".docx"}:
        raise HTTPException(415, "Supported file types are TXT, MD, PDF, and DOCX")
    content_length = request.headers.get("content-length")
    if content_length and content_length.isdecimal() and int(content_length) > MAX_ATTACHMENT_BYTES + 1024 * 1024:
        raise HTTPException(413, "Attachment is too large")
    try:
        chat.get_session(actor, session_id)
    except KeyError:
        raise HTTPException(404, "Session not found")
    payload = file.file.read(MAX_ATTACHMENT_BYTES + 1)
    if len(payload) > MAX_ATTACHMENT_BYTES:
        raise HTTPException(413, "Attachment is too large")
    upload_path = ROOT / "uploads" / f"{uuid4()}{suffix}"
    upload_path.parent.mkdir(parents=True, exist_ok=True)
    upload_path.write_bytes(payload)
    try: return chat.upload(actor, session_id, upload_path)
    except (ValueError, FileNotFoundError) as exc: raise HTTPException(422, str(exc))


@app.post("/sessions/{session_id}/ocr/images")
def upload_ocr_image(session_id: str, request: Request, file: UploadFile = File(...), actor: ActorContext = Depends(get_actor_context)):
    owner = actor.user_id
    try:
        chat.get_session(actor, session_id)
        payload = file.file.read(10 * 1024 * 1024 + 1)
        staged = mcp_host.stage_image(owner, session_id, file.filename or "image", payload)
        return {"image_id": staged["image_id"], "filename": staged["filename"], "bytes": staged["bytes"]}
    except KeyError:
        raise HTTPException(404, "Session not found")
    except ValueError as exc:
        raise HTTPException(422, str(exc))


@app.post("/sessions/{session_id}/ocr/preview")
def ocr_preview(session_id: str, payload: OCRPreviewIn, request: Request, actor: ActorContext = Depends(get_actor_context)):
    owner = actor.user_id
    try:
        chat.get_session(actor, session_id)
        result = mcp_host.preview(owner, session_id, payload.image_id, payload.language)
        if result.get("success"):
            result["session_id"] = session_id
            result["message"] = "识别候选已生成；请逐项核对。数据库尚未写入。"
        return result
    except KeyError:
        raise HTTPException(404, "Session or authorized image not found")
    except (MCPHostError, ValueError) as exc:
        raise HTTPException(422, str(exc))


@app.post("/sessions/{session_id}/ocr/confirm")
def ocr_confirm(session_id: str, payload: OCRConfirmIn, request: Request, actor: ActorContext = Depends(get_actor_context)):
    owner = actor.user_id
    try:
        chat.get_session(actor, session_id)
        result = mcp_host.confirm_and_commit(owner, session_id, payload.operation_id, payload.rows, payload.confirmed)
        if result.get("replayed"):
            return result
        # Keep the tool outcome visible in ordinary persisted chat history. The
        # deterministic verified fields are authoritative if the LLM is offline.
        evidence = {"status": result["status"], "inserted_rows": result["inserted_rows"], "rows": result["rows"]}
        try:
            answer = orchestrator.answer_from_tool_result(
                user_message="Save the reviewed vocabulary rows and verify them.",
                tool_name="db_insert_rows + db_query_readonly", result=evidence,
                workflow_status="database write and read-only verification succeeded",
            )
        except Exception:
            answer = "已写入并查询验证词汇数据：" + str(evidence["rows"])
        final = f"数据库状态：verified。{answer}"
        assistant_message = chat.append_assistant_message(actor, session_id, final)
        result["assistant_message_id"] = assistant_message.id
        return result
    except KeyError:
        raise HTTPException(404, "Session or operation not found")
    except (MCPHostError, ValueError) as exc:
        raise HTTPException(422, str(exc))

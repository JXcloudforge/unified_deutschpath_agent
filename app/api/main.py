from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, Header, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

from app.agent import UnifiedOrchestrator
from app.chat import ChatRepository, ChatService
from app.config import setting_source
from app.files import FileService
from app.llm import build_llm
from app.mcp.host import MCPHost, MCPHostError
from app.mcp.planner import MCPToolPlanner
from app.rag import RAGService, build_embedding
from app.rag.vector_store import ChromaVectorStore
from app.routing import HybridIntentRouter, LLMIntentRouter, RuleBasedIntentRouter
from app.users import UserStateRepository, UserStateService
from app.users.models import LearningEvent, LearningEventIn, ProfileUpdate, UserState
from app.version import VERSION
from app.web import TavilySearchProvider

ROOT = Path(os.getenv("STAGE2_DATA_PATH", "data"))
rag = RAGService(ChromaVectorStore(ROOT / "chroma", build_embedding()))
llm = build_llm()
rules_router = RuleBasedIntentRouter()
router_mode = os.getenv("STAGE3_ROUTER", "rules").strip().lower()
router = HybridIntentRouter(rules_router, LLMIntentRouter(llm)) if router_mode == "hybrid" else rules_router
users = UserStateService(UserStateRepository(ROOT / "stage2.db"))
mcp_host = MCPHost(ROOT)
mcp_tool_planner = MCPToolPlanner()
chat = ChatService(ChatRepository(ROOT / "stage2.db"), UnifiedOrchestrator(rag, users, llm, router=router, web_search=TavilySearchProvider()), FileService(), mcp_host=mcp_host, mcp_planner=mcp_tool_planner)


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    rag.store.close()


app = FastAPI(title="Deutschpath Unified Agent", version=VERSION, lifespan=lifespan)

class MessageIn(BaseModel):
    content: str

class SessionTitleIn(BaseModel):
    title: str = Field(min_length=1, max_length=100)

class OCRPreviewIn(BaseModel):
    image_id: str
    language: str = "de"

class OCRConfirmIn(BaseModel):
    operation_id: str
    rows: list[dict[str, str]]
    confirmed: bool

def user_id(value: str | None) -> str:
    if not value or not value.strip():
        raise HTTPException(401, "X-User-ID is required")
    return value.strip()

@app.get("/health")
def health():
    """Report local wiring and configuration without claiming remote connectivity."""
    active_router = chat.orchestrator.router
    active_web_provider = chat.orchestrator.web_search
    router_initialized = isinstance(active_router, (RuleBasedIntentRouter, HybridIntentRouter))
    effective_router_mode = "hybrid" if isinstance(active_router, HybridIntentRouter) else "rules"
    web_provider_initialized = isinstance(active_web_provider, TavilySearchProvider)
    web_key_configured = web_provider_initialized and bool(getattr(active_web_provider, "api_key", ""))
    active_llm = chat.orchestrator.llm
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
    }

# Adapt 02's thin CRM handlers to 04's existing header identity and state service.
# X-User-ID identifies local beta data; it is not authenticated authorization.
@app.get("/users/me/state", response_model=UserState)
def get_user_state(x_user_id: str | None = Header(None)):
    return users.get_user_state(user_id(x_user_id))


@app.patch("/users/me/state", response_model=UserState)
def update_user_state(payload: ProfileUpdate, x_user_id: str | None = Header(None)):
    return users.update_user_state(user_id(x_user_id), **payload.model_dump(exclude_unset=True))


@app.get("/users/me/events", response_model=list[LearningEvent])
def learning_events(limit: int = Query(20, ge=1, le=100), x_user_id: str | None = Header(None)):
    return users.list_learning_events(user_id(x_user_id), limit=limit)


@app.post("/users/me/events", response_model=LearningEvent, status_code=201)
def save_learning_event(payload: LearningEventIn, x_user_id: str | None = Header(None)):
    return users.save_learning_event(user_id(x_user_id), **payload.model_dump())


@app.post("/sessions")
def create_session(x_user_id: str | None = Header(None)): return chat.create_session(user_id(x_user_id))

@app.get("/sessions")
def list_sessions(x_user_id: str | None = Header(None)): return chat.repository.list_sessions(user_id(x_user_id))

@app.patch("/sessions/{session_id}")
def rename_session(session_id: str, payload: SessionTitleIn, x_user_id: str | None = Header(None)):
    try:
        return chat.repository.rename_session(user_id(x_user_id), session_id, payload.title)
    except KeyError:
        raise HTTPException(404, "Session not found")
    except ValueError as exc:
        raise HTTPException(422, str(exc))

@app.post("/sessions/{session_id}/messages")
def send_message(session_id: str, payload: MessageIn, x_user_id: str | None = Header(None)):
    try: return chat.send_message(user_id(x_user_id), session_id, payload.content)
    except KeyError: raise HTTPException(404, "Session not found")
    except ValueError as exc: raise HTTPException(422, str(exc))
    except RuntimeError: raise HTTPException(502, "Agent service failed")

@app.get("/sessions/{session_id}/messages")
def messages(session_id: str, x_user_id: str | None = Header(None)):
    try: return chat.repository.messages(user_id(x_user_id), session_id)
    except KeyError: raise HTTPException(404, "Session not found")

@app.post("/sessions/{session_id}/attachments")
def upload(session_id: str, file: UploadFile = File(...), x_user_id: str | None = Header(None)):
    suffix = Path(file.filename or "").suffix.lower()
    upload_path = ROOT / "uploads" / f"{uuid4()}{suffix}"
    upload_path.parent.mkdir(parents=True, exist_ok=True)
    upload_path.write_bytes(file.file.read())
    try: return chat.upload(user_id(x_user_id), session_id, upload_path)
    except (ValueError, FileNotFoundError) as exc: raise HTTPException(422, str(exc))


@app.post("/sessions/{session_id}/ocr/images")
def upload_ocr_image(session_id: str, file: UploadFile = File(...), x_user_id: str | None = Header(None)):
    owner = user_id(x_user_id)
    try:
        chat.repository.get_session(owner, session_id)
        payload = file.file.read(10 * 1024 * 1024 + 1)
        staged = mcp_host.stage_image(owner, session_id, file.filename or "image", payload)
        return {"image_id": staged["image_id"], "filename": staged["filename"], "bytes": staged["bytes"]}
    except KeyError:
        raise HTTPException(404, "Session not found")
    except ValueError as exc:
        raise HTTPException(422, str(exc))


@app.post("/sessions/{session_id}/ocr/preview")
def ocr_preview(session_id: str, payload: OCRPreviewIn, x_user_id: str | None = Header(None)):
    owner = user_id(x_user_id)
    try:
        chat.repository.get_session(owner, session_id)
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
def ocr_confirm(session_id: str, payload: OCRConfirmIn, x_user_id: str | None = Header(None)):
    owner = user_id(x_user_id)
    try:
        chat.repository.get_session(owner, session_id)
        result = mcp_host.confirm_and_commit(owner, session_id, payload.operation_id, payload.rows, payload.confirmed)
        if result.get("replayed"):
            return result
        # Keep the tool outcome visible in ordinary persisted chat history. The
        # deterministic verified fields are authoritative if the LLM is offline.
        evidence = {"status": result["status"], "inserted_rows": result["inserted_rows"], "rows": result["rows"]}
        try:
            answer = chat.orchestrator.answer_from_tool_result(
                user_message="Save the reviewed vocabulary rows and verify them.",
                tool_name="db_insert_rows + db_query_readonly", result=evidence,
                workflow_status="database write and read-only verification succeeded",
            )
        except Exception:
            answer = "已写入并查询验证词汇数据：" + str(evidence["rows"])
        final = f"数据库状态：verified。{answer}"
        result["assistant_message"] = chat.repository.add_message(owner, session_id, "assistant", final)
        result["assistant_message_id"] = result["assistant_message"]["id"]
        result.pop("assistant_message")
        return result
    except KeyError:
        raise HTTPException(404, "Session or operation not found")
    except (MCPHostError, ValueError) as exc:
        raise HTTPException(422, str(exc))

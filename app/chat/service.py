from __future__ import annotations

from pathlib import Path

from app.agent.orchestrator import UnifiedOrchestrator
from app.files.service import FileService
from .context import ConversationContextBuilder
from .contracts import (
    ActorContext,
    ConversationContextSnapshot,
    ConversationMessage,
    ConversationSession,
    SendMessageResult,
)
from .repository import ChatRepository


class ChatService:
    """Public Conversation facade; repository access stays inside this module."""

    def __init__(
        self,
        repository: ChatRepository,
        orchestrator: UnifiedOrchestrator,
        files: FileService,
        *,
        mcp_host=None,
        mcp_planner=None,
        context_builder: ConversationContextBuilder | None = None,
    ) -> None:
        self._repository = repository
        self._orchestrator = orchestrator
        self._files = files
        self._mcp_host, self._mcp_planner = mcp_host, mcp_planner
        self._context_builder = context_builder or ConversationContextBuilder()

    @classmethod
    def from_path(
        cls,
        database_path: str | Path,
        orchestrator: UnifiedOrchestrator,
        files: FileService,
        *,
        mcp_host=None,
        mcp_planner=None,
        context_builder: ConversationContextBuilder | None = None,
    ) -> ChatService:
        """Construct the Conversation persistence adapter inside its owner module."""
        return cls(
            ChatRepository(database_path), orchestrator, files,
            mcp_host=mcp_host, mcp_planner=mcp_planner, context_builder=context_builder,
        )

    def create_session(self, actor: ActorContext) -> ConversationSession:
        return ConversationSession.from_record(self._repository.create_session(actor.user_id))

    def get_session(self, actor: ActorContext, session_id: str) -> ConversationSession:
        return ConversationSession.from_record(self._repository.get_session(actor.user_id, session_id))

    def list_sessions(self, actor: ActorContext) -> list[ConversationSession]:
        return [ConversationSession.from_record(row) for row in self._repository.list_sessions(actor.user_id)]

    def rename_session(self, actor: ActorContext, session_id: str, title: str) -> ConversationSession:
        return ConversationSession.from_record(
            self._repository.rename_session(actor.user_id, session_id, title)
        )

    def get_messages(self, actor: ActorContext, session_id: str) -> list[ConversationMessage]:
        return [
            ConversationMessage.from_record(row)
            for row in self._repository.messages(actor.user_id, session_id)
        ]

    def get_context_snapshot(self, actor: ActorContext, session_id: str) -> ConversationContextSnapshot:
        """Return bounded, immutable history after enforcing session ownership."""
        return self._context_builder.build(session_id, self.get_messages(actor, session_id))

    def append_assistant_message(
        self, actor: ActorContext, session_id: str, content: str
    ) -> ConversationMessage:
        if not content.strip():
            raise ValueError("assistant message content must not be blank")
        record = self._repository.add_message(
            actor.user_id, session_id, "assistant", content.strip()
        )
        return ConversationMessage.from_record(record)

    def append_user_message(self, actor: ActorContext, session_id: str, content: str,
                            *, preserve_session_title: bool = False) -> ConversationMessage:
        """Persist one user turn for an application workflow that supplies its own response."""
        if not content.strip():
            raise ValueError("message content must not be blank")
        return self._append_user_message(actor, session_id, content,
                                         preserve_session_title=preserve_session_title)

    def send_message(self, actor: ActorContext, session_id: str, content: str) -> SendMessageResult:
        if not content.strip():
            raise ValueError("message content must not be blank")
        user_id = actor.user_id
        if self._mcp_host is not None and self._mcp_planner is not None:
            latest_image = self._mcp_host.latest_image_id(user_id, session_id)
            pending = self._mcp_host.pending_workflow(user_id, session_id)
            plan = self._mcp_planner.plan(
                content,
                image_id=latest_image,
                pending_operation_id=pending["operation_id"] if pending else None,
            )
            if plan.action == "execute_read":
                return self._run_ocr_plan(actor, session_id, content, plan.image_id or "", plan.language)
            if plan.action == "human_confirmation_required" and pending:
                user_message = self._append_user_message(actor, session_id, content)
                assistant_message = self.append_assistant_message(
                    actor, session_id,
                    "数据仍待人工核对。请检查下方表格，勾选确认后再写入；我不会代替你确认。",
                )
                return SendMessageResult(user_message, assistant_message, pending)

        history = self.get_context_snapshot(actor, session_id).to_llm_history()
        user_message = self._append_user_message(actor, session_id, content)
        try:
            attachment = self._latest_attachment(actor, session_id)
            answer = self._orchestrator.answer(
                user_id=user_id,
                message=content.strip(),
                history=history,
                session_id=session_id,
                attachment=attachment,
            )
        except Exception as exc:
            # Preserve the user message, exactly as 03_deutsch_chat does.
            raise RuntimeError("agent service failed") from exc
        assistant_message = self.append_assistant_message(actor, session_id, answer)
        return SendMessageResult(user_message, assistant_message)

    def _append_user_message(self, actor: ActorContext, session_id: str, content: str,
                             *, preserve_session_title: bool = False) -> ConversationMessage:
        record = self._repository.add_message(actor.user_id, session_id, "user", content.strip(),
                                              preserve_session_title=preserve_session_title)
        return ConversationMessage.from_record(record)

    def _run_ocr_plan(
        self, actor: ActorContext, session_id: str, content: str, image_id: str, language: str
    ) -> SendMessageResult:
        user_message = self._append_user_message(actor, session_id, content)
        try:
            result = self._mcp_host.preview(actor.user_id, session_id, image_id, language)
        except Exception as exc:
            result = {"success": False, "error": str(exc)}
        if result.get("success"):
            result["session_id"] = session_id
            try:
                summary = self._orchestrator.answer_from_tool_result(
                    user_message=content, tool_name="ocr_extract", result=result["ocr"],
                    workflow_status="OCR candidate only; database has not been written",
                )
            except Exception:
                summary = "OCR 已完成，候选数据等待人工核对。"
            assistant_content = f"{summary}\n\n工作流状态：OCR 候选已生成，数据库尚未写入。"
            result["message"] = "请在下方复核候选数据；未确认前不会写入。"
        else:
            assistant_content = f"OCR 工具执行失败，数据库未写入：{result.get('error', '未知错误')}"
        assistant_message = self.append_assistant_message(actor, session_id, assistant_content)
        return SendMessageResult(user_message, assistant_message, result)

    def upload(self, actor: ActorContext, session_id: str, path: str | Path) -> dict:
        document = self._files.parse(path)
        self._repository.add_attachment(
            actor.user_id, session_id, document.filename, document.file_type,
            str(Path(path).resolve()),
        )
        self._orchestrator.rag.index_documents(f"session:{session_id}", [document])
        return {"filename": document.filename, "file_type": document.file_type, "characters": len(document.text)}

    def _latest_attachment(self, actor: ActorContext, session_id: str):
        """Small uploads enter the bounded chat prompt; larger ones use Session RAG."""
        attachments = self._repository.attachments(actor.user_id, session_id)
        return self._files.parse(attachments[-1]["stored_path"]) if attachments else None

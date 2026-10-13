from __future__ import annotations

from pathlib import Path

from app.agent.orchestrator import UnifiedOrchestrator
from app.files.service import FileService
from .repository import ChatRepository


class ChatService:
    def __init__(self, repository: ChatRepository, orchestrator: UnifiedOrchestrator, files: FileService,
                 *, mcp_host=None, mcp_planner=None) -> None:
        self.repository, self.orchestrator, self.files = repository, orchestrator, files
        self.mcp_host, self.mcp_planner = mcp_host, mcp_planner

    def create_session(self, user_id: str) -> dict:
        return self.repository.create_session(user_id)

    def send_message(self, user_id: str, session_id: str, content: str) -> dict:
        if not content.strip():
            raise ValueError("message content must not be blank")
        if self.mcp_host is not None and self.mcp_planner is not None:
            latest_image = self.mcp_host.latest_image_id(user_id, session_id)
            pending = self.mcp_host.pending_workflow(user_id, session_id)
            plan = self.mcp_planner.plan(content, image_id=latest_image,
                                         pending_operation_id=pending["operation_id"] if pending else None)
            if plan.action == "execute_read":
                return self._run_ocr_plan(user_id, session_id, content, plan.image_id or "", plan.language)
            if plan.action == "human_confirmation_required" and pending:
                user_message = self.repository.add_message(user_id, session_id, "user", content.strip())
                assistant_message = self.repository.add_message(
                    user_id, session_id, "assistant",
                    "数据仍待人工核对。请检查下方表格，勾选确认后再写入；我不会代替你确认。",
                )
                return {"user_message": user_message, "assistant_message": assistant_message,
                        "tool_operation": pending}
        history = [{"role": item["role"], "content": item["content"]} for item in self.repository.messages(user_id, session_id)[-20:]]
        user_message = self.repository.add_message(user_id, session_id, "user", content.strip())
        try:
            attachment = self._latest_attachment(user_id, session_id)
            answer = self.orchestrator.answer(
                user_id=user_id, message=content.strip(), history=history,
                session_id=session_id, attachment=attachment,
            )
        except Exception as exc:
            # Preserve the user message, exactly as 03_deutsch_chat does.
            raise RuntimeError("agent service failed") from exc
        return {"user_message": user_message, "assistant_message": self.repository.add_message(user_id, session_id, "assistant", answer)}

    def _run_ocr_plan(self, user_id: str, session_id: str, content: str, image_id: str, language: str) -> dict:
        user_message = self.repository.add_message(user_id, session_id, "user", content.strip())
        try:
            result = self.mcp_host.preview(user_id, session_id, image_id, language)
        except Exception as exc:
            result = {"success": False, "error": str(exc)}
        if result.get("success"):
            result["session_id"] = session_id
            try:
                summary = self.orchestrator.answer_from_tool_result(
                    user_message=content, tool_name="ocr_extract", result=result["ocr"],
                    workflow_status="OCR candidate only; database has not been written",
                )
            except Exception:
                summary = "OCR 已完成，候选数据等待人工核对。"
            assistant_content = f"{summary}\n\n工作流状态：OCR 候选已生成，数据库尚未写入。"
            result["message"] = "请在下方复核候选数据；未确认前不会写入。"
        else:
            assistant_content = f"OCR 工具执行失败，数据库未写入：{result.get('error', '未知错误')}"
        assistant_message = self.repository.add_message(user_id, session_id, "assistant", assistant_content)
        return {"user_message": user_message, "assistant_message": assistant_message,
                "tool_operation": result}

    def upload(self, user_id: str, session_id: str, path: str | Path) -> dict:
        document = self.files.parse(path)
        self.repository.add_attachment(user_id, session_id, document.filename, document.file_type, str(Path(path).resolve()))
        self.orchestrator.rag.index_documents(f"session:{session_id}", [document])
        return {"filename": document.filename, "file_type": document.file_type, "characters": len(document.text)}

    def _latest_attachment(self, user_id: str, session_id: str):
        """Small uploads enter the real chat prompt; larger ones fall back to Session RAG."""
        attachments = self.repository.attachments(user_id, session_id)
        return self.files.parse(attachments[-1]["stored_path"]) if attachments else None

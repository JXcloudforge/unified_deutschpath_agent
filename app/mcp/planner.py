"""Small deterministic MCP planner kept separate from the 3-way search router."""
from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class MCPToolPlan:
    action: str
    tool_name: str | None = None
    image_id: str | None = None
    operation_id: str | None = None
    language: str = "de"


_OCR_REQUEST = re.compile(r"识别|提取.*文字|ocr|recogniz|extract.*text|read.*image|单词表.*读取", re.IGNORECASE)
_WRITE_REQUEST = re.compile(r"保存|写入|入库|存到数据库|save.*database|write.*database|store.*database", re.IGNORECASE)


class MCPToolPlanner:
    """Offline bounded selector; it cannot create approvals or perform writes."""
    def plan(self, message: str, *, image_id: str | None = None, pending_operation_id: str | None = None) -> MCPToolPlan:
        if not isinstance(message, str):
            return MCPToolPlan("none")
        if _OCR_REQUEST.search(message) and image_id:
            language = "en" if re.search(r"英语|英文|english", message, re.IGNORECASE) else "de"
            return MCPToolPlan("execute_read", "ocr_extract", image_id=image_id, language=language)
        if _WRITE_REQUEST.search(message) and pending_operation_id:
            return MCPToolPlan("human_confirmation_required", operation_id=pending_operation_id)
        return MCPToolPlan("none")

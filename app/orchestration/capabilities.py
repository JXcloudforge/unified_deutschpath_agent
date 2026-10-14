"""Auditable declarations for the small set of real M08-C adapters."""
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Capability:
    name: str
    owner_module: str
    operation: str
    parameters: str
    side_effect: bool
    authorization: str
    offline_testable: bool
    real_executor: bool


CAPABILITIES = (
    Capability("rename_session", "Conversation", "Command", "session_id + title",
        True, "ActorContext + owner Query + explicit user confirmation", True, True),
    Capability("list_sessions", "Conversation", "Query", "ActorContext",
        False, "ActorContext user scope", True, True),
    Capability("search_knowledge", "RAG", "Query", "namespace + query + top_k",
        False, "RAG namespace boundary", True, False),
    Capability("web_search", "Web", "Query", "query + max_results",
        False, "query guard + provider configuration", PartiallyOffline := True, False),
    Capability("ocr_commit", "MCP Host / Database MCP", "Confirmed tool workflow",
        "host operation_id + reviewed rows + confirmed flag", True,
        "MCP Host user/session binding and explicit review", True, False),
    Capability("create_learning_task", "CRM / User State", "Command", "not available",
        True, "not defined", False, False),
)

"""Narrow Chat application adapter for the locally gated rename-session workflow."""
from __future__ import annotations

import json
import re
from dataclasses import asdict

from app.chat.contracts import ActorContext, ConversationCommands, ConversationQueries, SendMessageResult
from app.orchestration.contracts import Orchestration, OrchestrationStatus
from app.orchestration.service import ExecutionUncertainError, OrchestrationService


_RENAME_INTENT = re.compile(r"(?:会话|对话).{0,18}(?:改名|重命名)|rename\s+(?:this\s+)?session", re.I)
_NAME_CAPTURE = re.compile(r"(?:改名为|重命名为|改为|改成|命名为|rename\s+(?:this\s+)?session\s+to)\s*(.*)$", re.I)
_RENAME_THEN_LIST = re.compile(
    r"^(?:先)?把当前会话(?:改名(?:为)?|重命名(?:为)?)\s*(.*?)\s*(?:，|,)?\s*(?:然后|再)\s*(?:列出|显示)(?:一下)?我的会话[。.!！]?$"
)
_REVISION_CAPTURE = re.compile(r"^(?:改成|改为|名称改为|名字改为)\s*(.+)$", re.I)
_CONFIRM = {"确认", "确认执行", "确认修改", "是的，确认", "confirm", "confirm rename", "yes, confirm"}
_CANCEL = {"取消", "取消操作", "不用了", "cancel"}
_UNSAFE_NAME_MARKERS = re.compile(r"[?？\n]|(?:然后|并且|同时|另外| and then )", re.I)
_UNSUPPORTED_TASK_WRITE = re.compile(r"(?:创建|新增|删除|更新|修改|保存|写入).{0,25}(?:任务|学习计划|数据库|CRM|task|study plan)", re.I)


class ConversationRenameExecutor:
    """Use only public Conversation Command and Query contracts; never SQL/Repository."""
    def __init__(self, commands: ConversationCommands, queries: ConversationQueries) -> None:
        self._commands, self._queries = commands, queries

    def execute(self, *, actor: ActorContext, session_id: str, orchestration_id: str,
                idempotency_key: str, proposal: str) -> str:
        try:
            action = json.loads(proposal)
        except (TypeError, json.JSONDecodeError) as exc:
            raise ValueError("invalid rename proposal") from exc
        if (action.get("action_type") != "rename_session" or action.get("session_id") != session_id
                or not isinstance(action.get("new_name"), str)):
            raise ValueError("rename proposal does not match its authorized session")
        new_name = action["new_name"]
        try:
            self._commands.rename_session(actor, session_id, new_name)
        except Exception as exc:
            # The Command can commit before its return Query; do not assume a failed
            # response means the database transaction did not commit.
            raise ExecutionUncertainError("rename command outcome must be queried") from exc
        try:
            session = self._queries.get_session(actor, session_id)
        except Exception as exc:
            raise ExecutionUncertainError("rename result could not be queried") from exc
        if session.title != new_name:
            raise ExecutionUncertainError("rename result does not match the proposal")
        return json.dumps({"session_id": session.id, "title": session.title}, ensure_ascii=False)

    def reconcile(self, *, actor: ActorContext, session_id: str, orchestration_id: str,
                  proposal: str, parameters: dict) -> str | None:
        expected = parameters.get("new_name") or parameters.get("title")
        if not isinstance(expected, str):
            return None
        try:
            session = self._queries.get_session(actor, session_id)
        except Exception:
            return None
        if session.title != expected:
            return None
        return json.dumps({"session_id": session.id, "title": session.title}, ensure_ascii=False)


class ConversationListSessionsQuery:
    """Read-only adapter for the public Conversation list query."""
    def __init__(self, queries: ConversationQueries) -> None:
        self._queries = queries

    def execute(self, *, actor: ActorContext, session_id: str, orchestration_id: str,
                idempotency_key: str, proposal: str) -> str:
        sessions = self._queries.list_sessions(actor)
        return json.dumps([{"title": item.title} for item in sessions], ensure_ascii=False)


class M08ChatAdapter:
    """Coordinates M07 and M08 for one deliberately bounded action family."""
    def __init__(self, commands: ConversationCommands, queries: ConversationQueries,
                 orchestration: OrchestrationService) -> None:
        self._commands, self._queries, self._orchestration = commands, queries, orchestration

    def handle(self, actor: ActorContext, session_id: str, content: str) -> SendMessageResult | None:
        text = content.strip()
        if not text:
            return None
        # The Context Query authenticates session ownership before M08 action lookup.
        self._queries.get_context_snapshot(actor, session_id)
        multi_plan = _parse_rename_then_list(text, session_id)
        is_rename, parsed = _parse_rename(text)
        if multi_plan is not None:
            is_rename, parsed = True, multi_plan["title"]
        try:
            pending = self._orchestration.get_pending_action(actor, session_id)
        except ValueError:
            if is_rename or normalized_control(text):
                return self._respond(actor, session_id, text,
                    "当前会话有多个待处理操作。为避免确认错项，请先通过独立操作编号处理；本次没有执行写入。", None)
            return None
        normalized = text.casefold().strip(" .。!！")
        if pending is None:
            latest = self._orchestration.get_latest_orchestration(actor, session_id)
            if normalized in _CONFIRM and latest and latest.status is OrchestrationStatus.SUCCEEDED:
                return self._respond(actor, session_id, text, "该计划已经完成，没有再次执行。", latest)
            if multi_plan is None and _has_unsupported_multi_intent(text):
                return self._respond(actor, session_id, text,
                    "目前仅支持‘重命名当前会话，然后列出我的会话’这一有界组合；本次没有执行写入。", None)
            if not is_rename:
                if _UNSUPPORTED_TASK_WRITE.search(text):
                    return self._respond(actor, session_id, text,
                        "目前只支持重命名当前会话；该任务/数据库写入能力尚未接入，因此没有执行操作。", None)
                return None
            if parsed == "ambiguous":
                return self._respond(actor, session_id, text, "我无法确定新的会话名称。请只提供一个名称，例如：把当前会话改名为德语复习。", None)
            return self._start_rename(actor, session_id, text, parsed, multi_plan=multi_plan)

        if pending.status is OrchestrationStatus.EXECUTING:
            return self._respond(actor, session_id, text,
                "该操作仍在执行中；本次确认没有启动第二次写入，请稍后查询状态。", pending)
        if pending.status is OrchestrationStatus.UNCERTAIN:
            if normalized not in _CONFIRM:
                if parsed is None:
                    return None
                return self._respond(actor, session_id, text, "上一项重命名结果正在核查；为避免重复写入，暂不接受新提案。", pending)
            return self._reconcile(actor, session_id, text, pending)

        if normalized in _CANCEL:
            cancelled = self._orchestration.cancel_pending_action(actor, pending.orchestration_id)
            return self._respond(actor, session_id, text, "已取消待处理的会话重命名，没有修改会话。", cancelled)
        if normalized in _CONFIRM:
            if pending.status is not OrchestrationStatus.AWAITING_CONFIRMATION:
                return self._respond(actor, session_id, text, "还缺少会话名称；请先回复你希望使用的名称。", pending)
            return self._confirm(actor, session_id, text, pending)

        if parsed == "ambiguous":
            return self._respond(actor, session_id, text, "名称或操作有歧义。请只提供一个新名称，或回复“取消”。", pending)
        if pending.status is OrchestrationStatus.NEEDS_CLARIFICATION:
            if is_rename:
                if parsed is None:
                    return self._respond(actor, session_id, text, "请补充一个明确的新会话名称。", pending)
                title = parsed
            else:
                title = _simple_name(text)
                if title is None:
                    return self._respond(actor, session_id, text, "请只回复一个会话名称，例如：德语复习。", pending)
            self._orchestration.submit_clarification(actor, pending.orchestration_id, title, missing_fields=())
        elif pending.status is OrchestrationStatus.AWAITING_CONFIRMATION and is_rename:
            if parsed is None:
                return self._respond(actor, session_id, text, "请提供新的会话名称；原提案仍等待确认。", pending)
            title = parsed
        elif pending.status is OrchestrationStatus.AWAITING_CONFIRMATION:
            revision = _REVISION_CAPTURE.match(text)
            if revision:
                title = _clean_name(revision.group(1))
                if not title:
                    return self._respond(actor, session_id, text, "新名称不能为空；旧提案仍等待确认。", pending)
            else:
                return None
        else:
            return None

        if pending.status is OrchestrationStatus.AWAITING_CONFIRMATION:
            revised_plan = multi_plan or _parse_rename_then_list(pending.original_input, session_id)
            proposal = _multi_proposal(session_id, title) if revised_plan is not None else _proposal(session_id, title)
            revised = self._orchestration.revise_pending_action(
                actor, pending.orchestration_id, proposal)
        else:
            # A clarification reply has just moved the proposal to READY.
            current = self._orchestration.get_orchestration_status(actor, pending.orchestration_id)
            if current.status is not OrchestrationStatus.READY:
                return self._respond(actor, session_id, text, "仍有必要信息未补齐，请说明新的会话名称。", current)
            inherited_multi = _parse_rename_then_list(current.original_input, session_id)
            proposal = _multi_proposal(session_id, title) if inherited_multi is not None else _proposal(session_id, title)
            revised = self._orchestration.propose_action(actor, current.orchestration_id, proposal)
        return self._respond(actor, session_id, text,
                             _confirmation_prompt(title, include_list=revised_plan is not None) if pending.status is OrchestrationStatus.AWAITING_CONFIRMATION else _confirmation_prompt(title, include_list=inherited_multi is not None), revised)

    def _start_rename(self, actor, session_id: str, text: str, title: str | None, *, multi_plan=None):
        fields = ("new_name",) if title is None else ()
        operation = self._orchestration.start_orchestration(actor, session_id, text, missing_fields=fields)
        user_message = self._commands.append_user_message(actor, session_id, text, preserve_session_title=True)
        if title is None:
            assistant_text = ("你希望将当前会话改成什么名称？补齐后我会再列出你的会话。"
                              if multi_plan is not None else "你希望将当前会话改成什么名称？")
        else:
            proposal = _multi_proposal(session_id, title) if multi_plan is not None else _proposal(session_id, title)
            operation = self._orchestration.propose_action(actor, operation.orchestration_id, proposal)
            assistant_text = _confirmation_prompt(title, include_list=multi_plan is not None)
        assistant = self._commands.append_assistant_message(actor, session_id, assistant_text)
        return SendMessageResult(user_message, assistant, orchestration=_public_operation(operation))

    def _confirm(self, actor, session_id: str, text: str, pending: Orchestration):
        try:
            result = self._orchestration.confirm_pending_action(
                actor, pending.orchestration_id, pending.confirmation_key or "")
        except ValueError:
            result = self._orchestration.get_orchestration_status(actor, pending.orchestration_id)
            if result.status is OrchestrationStatus.EXECUTING:
                return self._respond(actor, session_id, text,
                    "该操作仍在执行中；本次确认没有启动第二次写入，请稍后查询状态。", result)
            if result.status is OrchestrationStatus.UNCERTAIN:
                return self._reconcile(actor, session_id, text, result)
            else:
                return self._respond(actor, session_id, text, "该提案已被处理或状态发生变化；为避免重复写入，请查看会话名称。", result)
        if result.status is OrchestrationStatus.SUCCEEDED:
            message = _completed_plan_message(result)
        elif result.status is OrchestrationStatus.PARTIAL:
            message = _partial_plan_message(result)
        elif result.status in {OrchestrationStatus.UNCERTAIN, OrchestrationStatus.EXECUTING}:
            message = "计划结果暂时无法确认。我不会重复执行写入步骤；请稍后核查业务状态。"
        else:
            message = "会话重命名失败，没有确认业务状态已更新。请稍后查看会话名称。"
        return self._respond(actor, session_id, text, message, result)

    def _reconcile(self, actor, session_id, text, operation):
        result = self._orchestration.resume_uncertain(actor, operation.orchestration_id)
        if result.status is OrchestrationStatus.SUCCEEDED:
            message = "中断计划已通过业务 Query 核对并安全恢复完成。" + _completed_plan_message(result)
        elif result.status is OrchestrationStatus.PARTIAL:
            message = _partial_plan_message(result)
        else:
            message = "计划结果仍无法安全核实；没有重放任何写入步骤，请人工检查业务状态。"
        return self._respond(actor, session_id, text, message, result)

    def _respond(self, actor, session_id, text, answer, operation):
        user_message = self._commands.append_user_message(actor, session_id, text, preserve_session_title=True)
        assistant = self._commands.append_assistant_message(actor, session_id, answer)
        return SendMessageResult(user_message, assistant,
            orchestration=_public_operation(operation) if operation else None)


def _parse_rename(text: str) -> tuple[bool, str | None | str]:
    if not _RENAME_INTENT.search(text):
        return False, None
    if len(_RENAME_INTENT.findall(text)) > 1:
        return True, "ambiguous"
    captured = _NAME_CAPTURE.search(text)
    if captured is None:
        return True, None
    return True, _clean_name(captured.group(1)) or "ambiguous"


def normalized_control(text: str) -> bool:
    return text.casefold().strip(" .。!！") in _CONFIRM | _CANCEL


def _clean_name(value: str) -> str:
    value = value.strip().strip(" \t\r\n\"'“”‘’《》:：,，。.!！")
    if not value or len(value) > 100 or _UNSAFE_NAME_MARKERS.search(value):
        return ""
    return value


def _simple_name(text: str) -> str | None:
    if _RENAME_INTENT.search(text) or _UNSAFE_NAME_MARKERS.search(text):
        return None
    return _clean_name(text)


def _proposal(session_id: str, title: str) -> str:
    return json.dumps({"action_type": "rename_session", "session_id": session_id,
                       "new_name": title}, ensure_ascii=False, sort_keys=True)


def _multi_proposal(session_id: str, title: str) -> str:
    return json.dumps({"steps": [
        {"step_id": "rename-session", "action_type": "rename_session", "owner_module": "Conversation",
         "command_or_query": "Command", "parameters": {"new_name": title}, "depends_on": []},
        {"step_id": "list-sessions", "action_type": "list_sessions", "owner_module": "Conversation",
         "command_or_query": "Query", "parameters": {}, "depends_on": ["rename-session"]},
    ]}, ensure_ascii=False, sort_keys=True)


def _confirmation_prompt(title: str, *, include_list: bool = False) -> str:
    suffix = "，随后列出你的会话" if include_list else ""
    return f"我准备将当前会话改名为「{title}」{suffix}。请回复“确认”执行，或回复“改成……”修改计划。"


def _parse_rename_then_list(text: str, session_id: str) -> dict | None:
    match = _RENAME_THEN_LIST.fullmatch(text.strip())
    if match is None:
        return None
    title = _clean_name(match.group(1))
    return {"title": title or None, "session_id": session_id}


def _has_unsupported_multi_intent(text: str) -> bool:
    return bool(_RENAME_INTENT.search(text) and re.search(r"然后|再|接着|并且|同时", text))


def _completed_plan_message(operation: Orchestration) -> str:
    pieces = []
    for step in operation.steps:
        if step.action_type == "rename_session" and step.status.value == "SUCCEEDED":
            params = json.loads(step.parameters_json)
            pieces.append(f"会话已重命名为「{params.get('new_name', '目标名称')}」，并通过 Conversation Query 核验。")
        elif step.action_type == "list_sessions" and step.status.value == "SUCCEEDED":
            sessions = json.loads(step.result_reference or "[]")
            names = [item.get("title", "") for item in sessions if isinstance(item, dict)]
            pieces.append("当前会话列表：" + ("、".join(names) if names else "（暂无会话）"))
    return "计划执行完成。" + " ".join(pieces)


def _partial_plan_message(operation: Orchestration) -> str:
    completed = [step.action_type for step in operation.steps if step.status.value == "SUCCEEDED"]
    failed = [step.action_type for step in operation.steps if step.status.value in {"FAILED", "BLOCKED"}]
    return (f"计划部分完成。已完成：{', '.join(completed) if completed else '无'}；"
            f"失败或因依赖停止：{', '.join(failed) if failed else '待核查'}。没有将未完成步骤报告为成功。")


def _public_operation(operation: Orchestration) -> dict:
    payload = asdict(operation)
    payload.pop("confirmation_key", None)
    payload.pop("actor_user_id", None)
    return payload

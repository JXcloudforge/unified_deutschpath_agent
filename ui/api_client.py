"""Thin Streamlit-to-FastAPI contract adapter; no business logic lives here."""

from __future__ import annotations

from collections.abc import Mapping
import os
from typing import Any

import requests


class ApiContractError(ValueError):
    """A successful HTTP response did not match the UI contract."""


def resolve_api_base_url() -> str:
    """Return the single configured API origin used by all UI requests."""
    return os.getenv("DEUTSCHPATH_API_BASE_URL", "http://127.0.0.1:8765").rstrip("/")


def request_error_detail(error: Exception) -> str:
    """Return a safe backend error detail for Streamlit while callers log the exception."""
    if isinstance(error, requests.Timeout):
        return "请求超时，请稍后重试。"
    if isinstance(error, requests.ConnectionError):
        return "后端服务暂时不可用，请检查连接。"
    response = getattr(error, "response", None)
    if response is not None:
        try:
            payload = response.json()
            if isinstance(payload, Mapping) and isinstance(payload.get("detail"), str):
                return payload["detail"]
        except (ValueError, TypeError):
            pass
    return "后端请求失败，请稍后重试。"


def normalize_messages(payload: object) -> list[dict[str, str]]:
    """Accept the current list schema and a future {messages: [...]} wrapper."""
    raw = payload.get("messages") if isinstance(payload, Mapping) else payload
    if not isinstance(raw, list):
        raise ApiContractError("messages must be a list or an object with a messages list")
    messages: list[dict[str, str]] = []
    for index, item in enumerate(raw):
        if not isinstance(item, Mapping):
            raise ApiContractError(f"message {index} must be an object")
        role, content = item.get("role"), item.get("content")
        if role not in {"user", "assistant"} or not isinstance(content, str):
            raise ApiContractError(f"message {index} has an invalid role or content")
        messages.append({"role": role, "content": content})
    return messages


def normalize_session(payload: object) -> dict[str, Any]:
    raw = payload.get("session") if isinstance(payload, Mapping) and "session" in payload else payload
    if not isinstance(raw, Mapping) or not isinstance(raw.get("id"), str) or not raw["id"].strip():
        raise ApiContractError("session response must contain a non-empty id")
    return dict(raw)


def normalize_send_result(payload: object) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ApiContractError("send-message response must be an object")
    user = normalize_messages([payload.get("user_message")])
    assistant = normalize_messages([payload.get("assistant_message")])
    if user[0]["role"] != "user" or assistant[0]["role"] != "assistant":
        raise ApiContractError("send-message response roles are invalid")
    normalized: dict[str, Any] = {"user_message": user[0], "assistant_message": assistant[0]}
    if "tool_operation" in payload:
        operation = payload.get("tool_operation")
        if not isinstance(operation, Mapping):
            raise ApiContractError("tool_operation must be an object")
        normalized["tool_operation"] = dict(operation)
    return normalized


def normalize_attachment(payload: object) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ApiContractError("attachment response must be an object")
    if not isinstance(payload.get("filename"), str) or not isinstance(payload.get("file_type"), str):
        raise ApiContractError("attachment response must contain filename and file_type")
    return dict(payload)


def normalize_user_state(payload: object, user_id: str) -> dict[str, Any]:
    if not isinstance(payload, Mapping) or payload.get("user_id") != user_id:
        raise ApiContractError("user-state response must belong to the requested user")
    fields = ("current_level", "target_level", "learning_goal", "learning_preferences")
    if any(field not in payload or (payload[field] is not None and not isinstance(payload[field], str)) for field in fields):
        raise ApiContractError("user-state fields must be strings or null")
    return dict(payload)


def normalize_learning_events(payload: object, user_id: str) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        raise ApiContractError("learning events must be a list")
    for event in payload:
        if not isinstance(event, Mapping) or event.get("user_id") != user_id:
            raise ApiContractError("learning events must belong to the requested user")
        if not isinstance(event.get("id"), int) or any(not isinstance(event.get(field), str) for field in ("event_type", "item", "created_at")):
            raise ApiContractError("learning event fields are invalid")
        if event.get("result") is not None and not isinstance(event["result"], str):
            raise ApiContractError("learning event result must be a string or null")
    return [dict(event) for event in payload]


class Stage2ApiClient:
    def __init__(self, base_url: str, *, timeout: float = 120.0) -> None:
        self.base_url, self.timeout = base_url.rstrip("/"), timeout

    def _headers(self, user_id: str) -> dict[str, str]:
        return {"X-User-ID": user_id}

    def get_health(self) -> dict[str, Any]:
        response = requests.get(f"{self.base_url}/health", timeout=min(self.timeout, 10))
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, Mapping) or payload.get("status") != "ok":
            raise ApiContractError("health response must be an ok object")
        return dict(payload)

    def create_session(self, user_id: str) -> dict[str, Any]:
        response = requests.post(f"{self.base_url}/sessions", headers=self._headers(user_id), timeout=self.timeout)
        response.raise_for_status()
        return normalize_session(response.json())

    def list_sessions(self, user_id: str) -> list[dict[str, Any]]:
        response = requests.get(f"{self.base_url}/sessions", headers=self._headers(user_id), timeout=min(self.timeout, 10.0))
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list):
            raise ApiContractError("sessions must be a list")
        sessions = [normalize_session(item) for item in payload]
        if any(session.get("user_id") != user_id for session in sessions):
            raise ApiContractError("sessions must belong to the requested user")
        return sessions

    def rename_session(self, user_id: str, session_id: str, title: str) -> dict[str, Any]:
        response = requests.patch(
            f"{self.base_url}/sessions/{session_id}",
            headers=self._headers(user_id), json={"title": title}, timeout=min(self.timeout, 10.0),
        )
        response.raise_for_status()
        session = normalize_session(response.json())
        if session.get("user_id") != user_id or session.get("id") != session_id:
            raise ApiContractError("renamed session must belong to the requested user")
        return session

    def get_user_state(self, user_id: str) -> dict[str, Any]:
        response = requests.get(f"{self.base_url}/users/me/state", headers=self._headers(user_id), timeout=min(self.timeout, 10.0))
        response.raise_for_status()
        return normalize_user_state(response.json(), user_id)

    def update_user_state(self, user_id: str, changes: dict[str, Any]) -> dict[str, Any]:
        response = requests.patch(f"{self.base_url}/users/me/state", headers=self._headers(user_id), json=changes, timeout=min(self.timeout, 10.0))
        response.raise_for_status()
        return normalize_user_state(response.json(), user_id)

    def list_learning_events(self, user_id: str, *, limit: int = 10) -> list[dict[str, Any]]:
        response = requests.get(f"{self.base_url}/users/me/events", headers=self._headers(user_id), params={"limit": limit}, timeout=min(self.timeout, 10.0))
        response.raise_for_status()
        return normalize_learning_events(response.json(), user_id)

    def get_messages(self, user_id: str, session_id: str) -> list[dict[str, str]]:
        response = requests.get(f"{self.base_url}/sessions/{session_id}/messages", headers=self._headers(user_id), timeout=self.timeout)
        response.raise_for_status()
        return normalize_messages(response.json())

    def send_message(self, user_id: str, session_id: str, content: str) -> dict[str, dict[str, str]]:
        response = requests.post(f"{self.base_url}/sessions/{session_id}/messages", headers=self._headers(user_id), json={"content": content}, timeout=self.timeout)
        response.raise_for_status()
        return normalize_send_result(response.json())

    def upload_attachment(self, user_id: str, session_id: str, filename: str, content: bytes, content_type: str) -> dict[str, Any]:
        response = requests.post(f"{self.base_url}/sessions/{session_id}/attachments", headers=self._headers(user_id), files={"file": (filename, content, content_type)}, timeout=self.timeout)
        response.raise_for_status()
        return normalize_attachment(response.json())

    def upload_ocr_image(self, user_id: str, session_id: str, filename: str, content: bytes, content_type: str) -> dict[str, Any]:
        response = requests.post(f"{self.base_url}/sessions/{session_id}/ocr/images", headers=self._headers(user_id), files={"file": (filename, content, content_type)}, timeout=self.timeout)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, Mapping) or not isinstance(payload.get("image_id"), str):
            raise ApiContractError("OCR upload response must contain image_id")
        return dict(payload)

    def preview_ocr(self, user_id: str, session_id: str, image_id: str, language: str) -> dict[str, Any]:
        response = requests.post(f"{self.base_url}/sessions/{session_id}/ocr/preview", headers=self._headers(user_id), json={"image_id": image_id, "language": language}, timeout=self.timeout)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, Mapping):
            raise ApiContractError("OCR preview response must be an object")
        return dict(payload)

    def confirm_ocr(self, user_id: str, session_id: str, operation_id: str, rows: list[dict[str, str]]) -> dict[str, Any]:
        response = requests.post(f"{self.base_url}/sessions/{session_id}/ocr/confirm", headers=self._headers(user_id), json={"operation_id": operation_id, "rows": rows, "confirmed": True}, timeout=self.timeout)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, Mapping) or payload.get("status") != "verified":
            raise ApiContractError("OCR database confirmation was not verified")
        return dict(payload)

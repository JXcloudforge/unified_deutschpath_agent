"""Local-only API credential settings for the Streamlit engineering beta."""

from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path
from typing import Any

from dotenv import dotenv_values

from app.config import ENV_FILE, PROCESS_ENV_AT_LOAD, PROJECT_ROOT
from app.llm.client import DeepSeekLLM
from app.web import TavilySearchProvider

ALLOWED_KEYS = frozenset({"DEEPSEEK_API_KEY", "TAVILY_API_KEY"})
ENV_TEMPLATE = PROJECT_ROOT / ".env.example"


def _dotenv_value(name: str, env_file: Path | None = None) -> str:
    env_file = env_file or ENV_FILE
    value = dotenv_values(env_file).get(name)
    return value.strip() if isinstance(value, str) else ""


def effective_value(name: str, env_file: Path | None = None) -> str:
    if name not in ALLOWED_KEYS:
        raise ValueError("unsupported credential name")
    if name in PROCESS_ENV_AT_LOAD:
        return os.environ.get(name, "").strip()
    return _dotenv_value(name, env_file)


def credential_status(name: str, env_file: Path | None = None) -> dict[str, Any]:
    if name not in ALLOWED_KEYS:
        raise ValueError("unsupported credential name")
    process_override = name in PROCESS_ENV_AT_LOAD
    value = effective_value(name, env_file)
    source = "process environment" if process_override else (".env" if value else "not configured")
    return {"configured": bool(value), "source": source, "process_override": process_override}


def _validate_key(value: str) -> str:
    normalized = value.strip()
    if not re.fullmatch(r"[A-Za-z0-9._-]{8,512}", normalized):
        raise ValueError("API Key 格式无效；请确认后输入 8 至 512 位字母、数字或 . _ -。")
    return normalized


def save_credential(name: str, value: str, *, env_file: Path | None = None, template_file: Path | None = None) -> None:
    """Atomically replace only an allowlisted key in the ignored project .env."""
    if name not in ALLOWED_KEYS:
        raise ValueError("unsupported credential name")
    secret = _validate_key(value)
    env_file = env_file or ENV_FILE
    template_file = template_file or ENV_TEMPLATE
    if env_file.exists():
        original = env_file.read_text(encoding="utf-8")
    elif template_file.exists():
        original = template_file.read_text(encoding="utf-8")
    else:
        original = ""

    lines = original.splitlines()
    replacement = f'{name}="{secret}"'
    key_line = re.compile(rf"^\s*(?:export\s+)?{re.escape(name)}\s*=")
    first_index: int | None = None
    updated: list[str] = []
    for line in lines:
        if key_line.match(line):
            if first_index is None:
                first_index = len(updated)
                updated.append(replacement)
            continue
        updated.append(line)
    if first_index is None:
        if updated and updated[-1].strip():
            updated.append("")
        updated.append(replacement)
    content = "\n".join(updated) + ("\n" if original.endswith(("\n", "\r")) or updated else "")

    env_file.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="\n", dir=env_file.parent,
                                         prefix=f".{env_file.name}.", suffix=".tmp", delete=False) as temp:
            temp_path = Path(temp.name)
            temp.write(content)
            temp.flush()
            os.fsync(temp.fileno())
        os.replace(temp_path, env_file)
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()


def test_deepseek_connection(*, env_file: Path | None = None) -> dict[str, str]:
    key = effective_value("DEEPSEEK_API_KEY", env_file)
    if not key:
        return {"status": "NOT TESTED", "message": "未配置 DeepSeek API Key。"}
    base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    model = os.getenv("DEEPSEEK_MODEL") or _dotenv_value("DEEPSEEK_MODEL", env_file) or "deepseek-chat"
    provider = DeepSeekLLM(key, base_url=base_url, model=model, timeout=15.0)
    try:
        provider.answer("Reply with OK.")
    except Exception as exc:  # Do not surface provider exception text; it may include request details.
        import httpx

        if isinstance(exc, httpx.TimeoutException):
            message = "请求超时。"
        elif isinstance(exc, httpx.HTTPStatusError):
            status = exc.response.status_code
            message = "认证失败，请检查 Key。" if status in (401, 403) else ("配额或速率限制。" if status == 429 else f"服务返回 HTTP {status}。")
        elif isinstance(exc, httpx.RequestError):
            message = "网络连接失败。"
        else:
            message = "响应无效或调用失败。"
        return {"status": "FAIL", "message": message}
    finally:
        provider.client.close()
    return {"status": "PASS", "message": "DeepSeek 返回了有效文本。"}


def test_tavily_connection(*, env_file: Path | None = None) -> dict[str, Any]:
    key = effective_value("TAVILY_API_KEY", env_file)
    if not key:
        return {"status": "NOT TESTED", "message": "未配置 Tavily API Key。", "result_count": 0}
    provider = TavilySearchProvider(api_key=key, timeout=12.0)
    try:
        result = provider.search("Germany Ausbildung visa official information", max_results=3)
    except Exception as exc:
        from app.web.provider import (
            WebSearchAuthenticationError, WebSearchNetworkError, WebSearchRateLimitError,
            WebSearchServiceError,
            WebSearchTimeoutError,
        )

        if isinstance(exc, WebSearchAuthenticationError):
            message = "认证失败或请求参数无效。"
        elif isinstance(exc, WebSearchRateLimitError):
            message = "配额不足或请求受限。"
        elif isinstance(exc, WebSearchTimeoutError):
            message = "请求超时。"
        elif isinstance(exc, WebSearchNetworkError):
            message = "网络连接失败。"
        elif isinstance(exc, WebSearchServiceError):
            message = "搜索服务暂时不可用。"
        else:
            message = "搜索服务调用失败。"
        return {"status": "FAIL", "message": message, "result_count": 0}
    finally:
        provider.client.close()
    count = len(result.results)
    return {"status": "PASS" if count else "FAIL", "message": "收到有效搜索结果。" if count else "请求成功，但没有返回搜索结果。", "result_count": count}

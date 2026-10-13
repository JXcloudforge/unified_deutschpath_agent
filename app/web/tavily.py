from __future__ import annotations

import os
from collections.abc import Iterable

import httpx
import app.config  # noqa: F401 - load the project-local .env without overriding host variables.

from .models import WebSearchResponse, WebSearchResult, WebSearchTopic
from .query_guard import SearchQueryBuilder
from .provider import (
    WebSearchAuthenticationError,
    WebSearchConfigurationError,
    WebSearchFormatError,
    WebSearchNetworkError,
    WebSearchProvider,
    WebSearchRateLimitError,
    WebSearchServiceError,
    WebSearchTimeoutError,
)


class TavilySearchProvider(WebSearchProvider):
    """Minimal synchronous Tavily adapter; all remote behaviour stays behind this boundary."""

    endpoint = "https://api.tavily.com/search"

    def __init__(
        self,
        api_key: str | None = None,
        *,
        client: httpx.Client | None = None,
        timeout: float = 12.0,
        query_builder: SearchQueryBuilder | None = None,
    ) -> None:
        self.api_key = (api_key if api_key is not None else os.getenv("TAVILY_API_KEY", "")).strip()
        self.client = client or httpx.Client(timeout=timeout)
        self.timeout = timeout
        self.query_builder = query_builder or SearchQueryBuilder()

    def search(
        self, query: str, *, topic: WebSearchTopic = WebSearchTopic.GENERAL, max_results: int = 5
    ) -> WebSearchResponse:
        if not self.api_key:
            raise WebSearchConfigurationError("TAVILY_API_KEY is not configured.")
        if not query or not query.strip():
            raise ValueError("query must be non-empty")
        if not 1 <= max_results <= 10:
            raise ValueError("max_results must be between 1 and 10")
        safe_query = self.query_builder.build(query)
        try:
            response = self.client.post(
                self.endpoint,
                json={
                    "api_key": self.api_key,
                    "query": safe_query,
                    "search_depth": "basic",
                    "max_results": max_results,
                    "topic": topic.value,
                    "include_answer": False,
                },
                timeout=self.timeout,
            )
        except httpx.TimeoutException as exc:
            raise WebSearchTimeoutError("网页搜索请求超时。") from exc
        except httpx.RequestError as exc:
            raise WebSearchNetworkError("无法连接网页搜索服务。") from exc

        if response.status_code in {400, 401}:
            raise WebSearchAuthenticationError("网页搜索认证或请求参数无效。")
        if response.status_code == 429:
            raise WebSearchRateLimitError("网页搜索服务当前限流或配额不足。")
        if response.status_code >= 500:
            raise WebSearchServiceError("网页搜索服务暂时不可用。")
        if response.is_error:
            raise WebSearchServiceError(f"网页搜索服务返回 HTTP {response.status_code}。")
        try:
            payload = response.json()
        except ValueError as exc:
            raise WebSearchFormatError("网页搜索服务返回了无效 JSON。") from exc
        return WebSearchResponse(query=safe_query, results=tuple(self._parse_results(payload)))

    @staticmethod
    def _parse_results(payload: object) -> Iterable[WebSearchResult]:
        if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
            raise WebSearchFormatError("网页搜索响应缺少 results 列表。")
        for item in payload["results"]:
            if not isinstance(item, dict):
                raise WebSearchFormatError("网页搜索响应包含无效结果项。")
            title, url, snippet = item.get("title"), item.get("url"), item.get("content")
            if not all(isinstance(value, str) and value.strip() for value in (title, url, snippet)):
                raise WebSearchFormatError("网页搜索结果缺少 title、url 或 content。")
            if not url.startswith(("https://", "http://")):
                raise WebSearchFormatError("网页搜索结果 URL 无效。")
            published_date = item.get("published_date")
            if published_date is not None and not isinstance(published_date, str):
                raise WebSearchFormatError("网页搜索结果 published_date 无效。")
            yield WebSearchResult(title=title.strip(), url=url.strip(), snippet=snippet.strip(), published_date=published_date)


class FakeWebSearchProvider(WebSearchProvider):
    """Offline test double that records actual provider invocations."""

    def __init__(self, response: WebSearchResponse | None = None, *, error: Exception | None = None) -> None:
        self.response = response or WebSearchResponse("", ())
        self.error = error
        self.calls: list[tuple[str, WebSearchTopic, int]] = []

    def search(
        self, query: str, *, topic: WebSearchTopic = WebSearchTopic.GENERAL, max_results: int = 5
    ) -> WebSearchResponse:
        self.calls.append((query, topic, max_results))
        if self.error:
            raise self.error
        return WebSearchResponse(query=query, results=self.response.results)

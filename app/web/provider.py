from __future__ import annotations

from typing import Protocol

from .models import WebSearchResponse, WebSearchTopic


class WebSearchError(RuntimeError):
    """A controlled provider failure; callers must not treat it as search success."""


class WebSearchConfigurationError(WebSearchError):
    pass


class WebSearchAuthenticationError(WebSearchError):
    pass


class WebSearchRateLimitError(WebSearchError):
    pass


class WebSearchServiceError(WebSearchError):
    pass


class WebSearchNetworkError(WebSearchError):
    pass


class WebSearchTimeoutError(WebSearchError):
    pass


class WebSearchFormatError(WebSearchError):
    pass


class WebSearchSafetyError(WebSearchError):
    """The requested external search query is not safe to disclose."""


class WebSearchProvider(Protocol):
    def search(
        self, query: str, *, topic: WebSearchTopic = WebSearchTopic.GENERAL, max_results: int = 5
    ) -> WebSearchResponse: ...


class UnavailableWebSearchProvider:
    """Offline-safe default for direct orchestrator construction and missing configuration."""

    def search(
        self, query: str, *, topic: WebSearchTopic = WebSearchTopic.GENERAL, max_results: int = 5
    ) -> WebSearchResponse:
        raise WebSearchConfigurationError("实时网页搜索尚未配置。")

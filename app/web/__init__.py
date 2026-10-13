"""Web-search provider boundary for Stage 3 P2."""

from .models import WebSearchResponse, WebSearchResult, WebSearchTopic
from .provider import (
    UnavailableWebSearchProvider,
    WebSearchAuthenticationError,
    WebSearchConfigurationError,
    WebSearchError,
    WebSearchFormatError,
    WebSearchNetworkError,
    WebSearchProvider,
    WebSearchRateLimitError,
    WebSearchSafetyError,
    WebSearchServiceError,
    WebSearchTimeoutError,
)
from .query_guard import SearchQueryBuilder
from .tavily import FakeWebSearchProvider, TavilySearchProvider

__all__ = [
    "FakeWebSearchProvider", "TavilySearchProvider", "UnavailableWebSearchProvider", "WebSearchAuthenticationError",
    "SearchQueryBuilder", "WebSearchConfigurationError", "WebSearchError", "WebSearchFormatError", "WebSearchNetworkError", "WebSearchProvider",
    "WebSearchRateLimitError", "WebSearchResponse", "WebSearchResult", "WebSearchSafetyError", "WebSearchServiceError", "WebSearchTimeoutError", "WebSearchTopic",
]

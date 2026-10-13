import json

import httpx
import pytest

from app.web import (
    FakeWebSearchProvider,
    TavilySearchProvider,
    WebSearchAuthenticationError,
    WebSearchConfigurationError,
    WebSearchFormatError,
    WebSearchNetworkError,
    WebSearchRateLimitError,
    WebSearchResponse,
    WebSearchResult,
    WebSearchSafetyError,
    WebSearchServiceError,
    WebSearchTimeoutError,
    WebSearchTopic,
)


def test_fake_provider_returns_structured_response_and_records_call():
    provider = FakeWebSearchProvider(WebSearchResponse("seed", (WebSearchResult("Title", "https://example.test", "Snippet"),)))
    response = provider.search("Berlin weather", topic=WebSearchTopic.NEWS)
    assert response.query == "Berlin weather"
    assert response.results[0].url == "https://example.test"
    assert provider.calls == [("Berlin weather", WebSearchTopic.NEWS, 5)]


def test_tavily_requires_an_api_key(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    with pytest.raises(WebSearchConfigurationError):
        TavilySearchProvider().search("test")


def test_tavily_parses_payload_and_uses_documented_request_defaults():
    recorded = {}

    def handler(request):
        recorded.update(json.loads(request.content))
        return httpx.Response(200, json={"results": [{"title": "Berlin", "url": "https://example.test/berlin", "content": "Today is sunny.", "published_date": "2026-10-10"}]})

    provider = TavilySearchProvider("test-key", client=httpx.Client(transport=httpx.MockTransport(handler)))
    response = provider.search("Berlin weather", topic=WebSearchTopic.NEWS)
    assert recorded == {"api_key": "test-key", "query": "Berlin weather", "search_depth": "basic", "max_results": 5, "topic": "news", "include_answer": False}
    assert response.results == (WebSearchResult("Berlin", "https://example.test/berlin", "Today is sunny.", "2026-10-10"),)


def test_tavily_stops_sensitive_query_before_creating_an_http_request():
    called = False

    def handler(request):
        nonlocal called
        called = True
        return httpx.Response(200, json={"results": []})

    provider = TavilySearchProvider("test-key", client=httpx.Client(transport=httpx.MockTransport(handler)))
    with pytest.raises(WebSearchSafetyError):
        provider.search("search alice@example.com visa status")
    assert not called


@pytest.mark.parametrize(
    ("handler", "error"),
    [
        (lambda request: httpx.Response(401), WebSearchAuthenticationError),
        (lambda request: httpx.Response(429), WebSearchRateLimitError),
        (lambda request: httpx.Response(503), WebSearchServiceError),
        (lambda request: httpx.Response(200, json={"results": [{"title": "bad"}]}), WebSearchFormatError),
    ],
)
def test_tavily_provider_reports_controlled_http_and_payload_failures(handler, error):
    provider = TavilySearchProvider("test-key", client=httpx.Client(transport=httpx.MockTransport(handler)))
    with pytest.raises(error):
        provider.search("test")


def test_tavily_provider_reports_network_and_timeout_failures():
    def timeout(request):
        raise httpx.ReadTimeout("timed out", request=request)

    def unavailable(request):
        raise httpx.ConnectError("offline", request=request)

    with pytest.raises(WebSearchTimeoutError):
        TavilySearchProvider("test-key", client=httpx.Client(transport=httpx.MockTransport(timeout))).search("test")
    with pytest.raises(WebSearchNetworkError):
        TavilySearchProvider("test-key", client=httpx.Client(transport=httpx.MockTransport(unavailable))).search("test")

# M05 — Stage 3 routing and web evidence

## Purpose

Select a retrieval strategy while preserving the existing three-class Router contract and the separate mixed-evidence flag.

## Scope and implementation

- `app/routing/` contains rule, LLM, and hybrid routers plus `RouteDecision` and `RoutingContext`.
- The only intent classes are `rag`, `web_search`, and `no_tool`; `mixed_sources` is additional evidence metadata.
- `app/web/query_guard.py` and `SearchQueryBuilder` constrain outbound search queries.
- `app/web/tavily.py` adapts the optional Tavily service; the provider protocol and offline unavailable implementation are in `app/web/provider.py`.
- `app/agent/evidence.py` aggregates local and public evidence for the answer prompt.

## Request chain

`UnifiedOrchestrator → intent router → RAG, guarded Web Search, or direct context → EvidenceAggregator when needed → LLM`.

## Validation and limits

Offline router, guard, mixed-source, and provider behavior is covered by `tests/unit/test_intent_router.py`, `tests/unit/test_hybrid_router.py`, `tests/integration/test_mixed_sources.py`, and web-search integration tests. Engineering candidate scores are not independent human-labeled results. The formal 98% target remains NOT VERIFIED. Live DeepSeek/Tavily status is turn-specific and not implied by this record.

## Evidence locations

- Source: `app/routing/`, `app/web/`, `app/agent/evidence.py`
- Tests: `tests/unit/test_intent_router.py`, `tests/unit/test_search_query_guard.py`, `tests/integration/test_mixed_sources.py`, `tests/integration/test_web_search_orchestration.py`

## Reuse and implementation notes

- **Previous capability/problem:** M04 supplied local evidence but no path selection for public current facts or direct no-tool responses.
- **New functions:** three intents; Rules, LLM, Hybrid implementations; distinct `mixed_sources`; guarded query building; optional Tavily search; evidence aggregation/citations and controlled fallback.
- **Technology roles:** rule router handles clear policy cases; semantic router handles selected ambiguity; Hybrid protects explicit/high-confidence rules; QueryGuard limits outbound text; provider adapter handles remote search; aggregator labels local/public evidence.
- **Core interfaces:** `Intent`, `RouteDecision`, `RoutingContext`, router `route` methods, `SearchQueryBuilder.build`, `WebSearchProvider.search`, `EvidenceAggregator`.
- **Implementation/call chain:** `UnifiedOrchestrator → router → RAG/Web/direct branch → EvidenceAggregator/ContextBuilder → LLM`; MCP planner is not part of this intent protocol.
- **Decoupling/reuse:** decision, provider, and evidence contracts are separate; alternate search providers can implement the existing protocol.
- **Acceptance:** offline tests cover classification, guards, mixed paths, and failures. Real external checks must be separately dated and run.
- **Known limits:** 300 engineering cases are not a blind human-labeled set; independent 98% remains NOT VERIFIED.

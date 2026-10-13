# M01 — Agent foundation

## Purpose

Establish one model boundary and one application orchestration path for answering German-learning requests. This milestone describes the current unified implementation; it does not claim that every historical prototype tool loop was migrated.

## Scope and implementation

- `app/llm/client.py` defines the LLM boundary, offline `FakeLLM`, and configured DeepSeek client construction.
- `app/agent/orchestrator.py` owns answer planning across the existing routing/RAG/web paths and constructs bounded prompt context.
- `app/agent/evidence.py` models and aggregates evidence supplied by enabled tools.
- `app/schemas.py` defines shared request and parsed-document structures.
- Tool execution requiring external side effects is handled by the separate MCP Host (M06), not an unrestricted model-driven executor.

## Request chain

`ChatService → UnifiedOrchestrator → selected evidence/context path → LLMClient → persisted assistant message`.

## Validation and limits

Offline behavior is exercised by unit and integration tests using `FakeLLM`; real DeepSeek success is a separate external-service check and must be reported only when actually run. Current source does not expose a general-purpose legacy Tool Registry/Checkpoint loop as a single migrated feature.

## Evidence locations

- Source: `app/llm/client.py`, `app/agent/orchestrator.py`, `app/agent/evidence.py`
- Tests: `tests/integration/test_stage2_flow.py`, `tests/integration/test_orchestrator_routing.py`, `tests/unit/test_evidence.py`

## Reuse and implementation notes

- **Previous stage/problem:** this is the foundational milestone; early A3 experiments had provider calls and tool ideas but lacked one testable application boundary.
- **New functions and implementation:** provider selection is through `build_llm`; `FakeLLM` provides deterministic offline behavior; `UnifiedOrchestrator.answer` selects answer paths and delegates final generation.
- **Technology roles:** Python hosts the application; Pydantic structures requests/documents; DeepSeek-compatible HTTP is encapsulated in `DeepSeekLLM`; `ContextBuilder` prepares prompt material.
- **Core interfaces:** `LLMClient`, `FakeLLM`, `DeepSeekLLM`, `ParsedDocument`, `RouteDecision`, `UnifiedOrchestrator`.
- **Decoupling/reuse:** service code depends on the LLM interface. A new project can reuse the interface and inject a provider and its own orchestrator. Current source does not provide a migrated generic Tool Registry, Checkpoint store, or native model Function Calling loop.
- **Acceptance:** the cited tests validate the fake/offline path. No result here alone proves an external DeepSeek call.
- **Known limits:** side-effecting actions are isolated in M06 Host workflow.

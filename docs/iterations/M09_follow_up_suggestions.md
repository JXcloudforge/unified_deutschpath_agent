# M09 — Optional follow-up suggestions

## Problem

Learners may want a guided next question after an answer, while retaining control over whether another request is sent.

## Module boundary and contract

`FollowUpSuggestionService` exposes a read-only Query over a bounded Conversation context and, when applicable, read-only orchestration status. It returns zero to three immutable suggestion DTOs. The Chat API includes suggestions only when `include_suggestions=true`.

## Implementation and reuse

M09 reuses Conversation snapshots and the existing Streamlit ChatWorkspace. Its deterministic strategy is opt-in and defaults off. A clicked suggestion only prefills the chat input; the user must submit it. No database schema or external model dependency was added.

## Validation

See [M09 acceptance](../PHASE4_M09_ACCEPTANCE.md) and [M10 acceptance](../PHASE4_M10_ACCEPTANCE.md). The evidence covers HTTP compatibility, AppTest prefill, bounded result count, owner isolation, and no side effects.

## Limits

The deterministic strategy covers a limited set of German-learning topics. It is not a general or generative recommendation engine.

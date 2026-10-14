# M07 — Conversation history and bounded context

## Problem

The API and chat UI needed to access persistent sessions, messages, attachments, and bounded history without depending on the Conversation Repository implementation.

## Module boundary and contract

`app.chat` owns session and message state. `ConversationCommands` performs allowed mutations; `ConversationQueries` provides owner-scoped reads and immutable DTOs. Context snapshots carry at most the latest 20 messages and 12,000 characters. This is a character bound, not a token budget.

## Implementation and reuse

M07 keeps the existing ChatService and SQLite data model; it introduces the Conversation Command/Query boundary and moves API access away from direct Repository calls. The Streamlit UI continues to call the FastAPI API Client. No business database schema migration was made.

## Validation

The release-copy evidence is recorded in [M08 acceptance](../PHASE4_M08_ACCEPTANCE.md), [M08-C acceptance](../PHASE4_M08C_ACCEPTANCE.md), and [M10 acceptance](../PHASE4_M10_ACCEPTANCE.md). Coverage includes owner checks, history recovery, context limits, HTTP compatibility and persistent state in isolated tests.

## Limits

The current local development identity is not production authentication. There is no persistent conversation summarization, and the character limit is not an exact model-token limit. Production OIDC and two-account resource isolation remain unverified.

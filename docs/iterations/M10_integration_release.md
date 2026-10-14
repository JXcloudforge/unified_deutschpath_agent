# M10 — Integration quality and release boundary

## Problem

As more modules joined the application, the project needed cross-module regression evidence and a clear boundary between local engineering acceptance and a public production release.

## Module boundary and contract

M10 consolidates existing Conversation, UserState, Agent, Router, RAG, Web, MCP, Orchestration, Suggestions and Auth contracts. The Auth service verifies configured API Access Tokens and maps provider subject identity to an internal Actor; owning business modules still enforce resource ownership. Auth does not own Conversation or CRM data.

## Implementation and reuse

M10 reuses the existing module Commands/Queries, test suite and loopback acceptance scripts. Auth token/Actor code and Streamlit OIDC wiring are present; Compose and Caddy files are deployment drafts. No product module is combined into a shared Repository or global transaction.

## Validation

See [M10 acceptance](../PHASE4_M10_ACCEPTANCE.md), [Auth API evidence](../PHASE4_M10_AUTH_ACCEPTANCE.md), and [Auth UI evidence](../PHASE4_M10_AUTH_UI_ACCEPTANCE.md). The publish-copy snapshot records local pytest, API Smoke, M08/M09/MCP loopback acceptance and compile checks. The tests use isolated local identities/data and fake OIDC/JWKS where applicable.

## Limits

Real OIDC login, two real accounts over HTTPS, browser session/CSRF/logout behavior, independent frozen Router evaluation, production container deployment and recovery drills are not verified. Local tests are not production acceptance.

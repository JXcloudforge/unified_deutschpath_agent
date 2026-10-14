# M08 — Bounded multi-step orchestration

## Problem

An action spanning multiple conversation operations needs durable proposal state, explicit user confirmation, ordered execution, and verification through the owning module's Query.

## Module boundary and contract

`app.orchestration` owns proposals and step state in its SQLite database. It calls only allowlisted Conversation interfaces. The verified example is `rename_session → list_sessions`: after user confirmation, the rename Command is read back with `get_session`; only then does the workflow call the read-only list Query.

## Implementation and reuse

M08 reuses the existing three-class Router and Conversation Commands/Queries. It adds orchestration DTOs, Commands/Queries, a bounded Chat adapter, confirmation keys, and restart reconciliation. There is no unrestricted model Planner, general Tool Registry, global transaction, or automatic replay of uncertain writes.

## Validation

See [M08-B acceptance](../PHASE4_M08_ACCEPTANCE.md), [M08-C acceptance](../PHASE4_M08C_ACCEPTANCE.md), and [M10 acceptance](../PHASE4_M10_ACCEPTANCE.md). Records include loopback Uvicorn HTTP, restart confirmation, duplicate confirmation, cross-user denial, and real business-state read-back.

## Limits

Only the fixed conversation rename/list flow is implemented. CRM writes, arbitrary task decomposition, and public production execution are not supported. Separate module databases do not provide exactly-once cross-module transactions.

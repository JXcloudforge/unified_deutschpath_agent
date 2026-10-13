# P1-2 archive and restore migration proposal

## Current finding

The active repository initializes only `chat_sessions`, `chat_messages`, and
`attachments`. `chat_sessions` already stores persistent `title` and activity
timestamps, but there is no archive column or metadata table. Messages and
attachments reference the session; RAG, staged OCR, and MCP workflow state live
outside this SQLite cascade. Permanent deletion is therefore unsafe.

This batch does not change the formal database schema. Archive and restore stay
disabled until this migration is reviewed and approved.

## Proposed additive migration

Add nullable `archived_at TEXT` to `chat_sessions` and an index on
`(user_id, archived_at, updated_at DESC)`. `NULL` means active. Archive and
restore endpoints must update only a row matching both `session_id` and
`user_id`; normal lists include only active rows, while an explicit archived
view returns only archived rows. Search remains user scoped. No records in
messages, attachments, Chroma, OCR staging, or MCP workflow storage are deleted.

Use a versioned, idempotent migration that checks `PRAGMA table_info` before
adding the column. Execute it transactionally and verify `PRAGMA integrity_check`
and row counts before enabling the UI controls.

## Backup and rollback

1. Stop FastAPI and confirm no process holds the configured chat database.
2. Create a consistent SQLite backup with SQLite's backup API to a new,
   timestamped file; do not overwrite or relocate the source database.
3. Verify the backup with `PRAGMA integrity_check`, record session/message/
   attachment row counts, and retain the backup outside Git.
4. Apply the migration to the target database and repeat the checks.
5. If validation fails before users resume writing, restore the verified backup
   while FastAPI remains stopped. If writes occurred after migration, do not
   restore the older backup blindly; stop and reconcile the post-migration
   changes before rollback.

Permanent deletion remains out of scope. It requires a separate cross-storage
cleanup design and recovery procedure for attachments, session RAG, OCR images,
and MCP workflow state.

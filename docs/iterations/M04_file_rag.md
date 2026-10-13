# M04 — Files and RAG

## Purpose

Accept learning documents and provide both direct attachment context and session-isolated retrieval, while keeping file parsing separate from prompt construction.

## Scope and implementation

- `app/files/service.py` and `app/files/parsers/` parse the supported document formats.
- `app/rag/embeddings.py` supports configured embeddings, including deterministic offline test embeddings.
- `app/rag/vector_store.py` wraps Chroma collections; `app/rag/service.py` indexes and searches namespaces.
- `app/rag/context_builder.py` assembles bounded context for the LLM.
- Session retrieval uses a `session:<id>` namespace; knowledge retrieval uses a separate knowledge namespace.

## Request chain

`Upload → FileService/parser → ChatService attachment/session storage → direct context or RAGService(namespace) → ContextBuilder → LLM`.

## Validation and limits

File types and limits are enforced by the existing parser/service code. Unit and integration evidence is in `tests/unit/test_files.py`, `tests/integration/test_stage2_flow.py`, and `tests/integration/test_chroma_lifecycle.py`. Automated runs use isolated SQLite/Chroma paths; production local data remains outside those tests.

## Evidence locations

- Source: `app/files/`, `app/rag/`
- Tests: `tests/unit/test_files.py`, `tests/unit/test_vector_store_lifecycle.py`, `tests/integration/test_chroma_lifecycle.py`

## Reuse and implementation notes

- **Previous capability/problem:** M03 supported chat attachments but needed normalized parsing and retrieval of session material and long-lived knowledge.
- **New functions:** TXT/MD/PDF/DOCX parsing, cleaned/chunked documents, embeddings, Chroma upsert/search, session namespace retrieval, and bounded context construction.
- **Technology roles:** `FileService` validates/dispatches; parser classes extract text; embedder maps chunks; `ChromaVectorStore` owns vector I/O; `RAGService` controls namespace operations; `ContextBuilder` formats context.
- **Core interfaces:** `ParsedDocument`, parser registry, `FileService`, `RAGService.index_documents/search/context_for_session`, `ChromaVectorStore`.
- **Implementation/call chain:** `Upload → parse → ParsedDocument → split/embed/upsert → namespace-filtered search → ContextBuilder → LLM`; small attachment text may use bounded direct context.
- **Decoupling/reuse:** parsers and RAG service are callable independently of FastAPI; namespaces distinguish Session from knowledge; another app can supply a different store/embedding configuration.
- **Acceptance:** parser, flow, isolation, and lifecycle tests cited above run with isolated storage.
- **Known limits:** text extraction is not OCR for scanned PDFs; changing embedding models may require reindexing; do not use production data paths in tests.

from __future__ import annotations

from app.schemas import ParsedDocument, SearchResult
from .cleaner import clean_text
from .context_builder import ContextBuilder
from .splitter import split_document
from .vector_store import ChromaVectorStore


class RAGService:
    """The sole Stage 2 RAG engine for long-lived knowledge and session attachments."""
    def __init__(self, store: ChromaVectorStore, *, context_builder: ContextBuilder | None = None) -> None:
        self.store = store
        self.context_builder = context_builder or ContextBuilder()

    def index_documents(self, namespace: str, documents: list[ParsedDocument]) -> int:
        chunks = []
        for document in documents:
            cleaned = ParsedDocument(document.filename, document.file_type, clean_text(document.text), document.metadata)
            chunks.extend(split_document(cleaned, namespace))
        self.store.upsert(namespace, chunks)
        return len(chunks)

    def search(self, namespace: str, query: str, top_k: int = 4) -> list[SearchResult]:
        if not namespace.strip() or not query.strip() or not 1 <= top_k <= 20:
            raise ValueError("namespace/query must be non-empty and top_k must be 1..20")
        return self.store.search(namespace, query, top_k)

    def context_for_session(self, session_id: str, query: str, top_k: int = 4) -> str:
        return self.context_builder.from_results(self.search(f"session:{session_id}", query, top_k), "Session attachment")

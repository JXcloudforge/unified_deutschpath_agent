from __future__ import annotations

from pathlib import Path

import chromadb

from app.schemas import Chunk, SearchResult
from .embeddings import EmbeddingProvider


def _collection_name(namespace: str) -> str:
    return "stage2_" + "".join(char if char.isalnum() else "_" for char in namespace)[:80]


class ChromaVectorStore:
    """One persistent Chroma collection per namespace, as in 01/03 but unified."""
    def __init__(self, persist_path: str | Path, embedding: EmbeddingProvider) -> None:
        self.client = chromadb.PersistentClient(path=str(persist_path))
        self.embedding = embedding
        self._closed = False

    def upsert(self, namespace: str, chunks: list[Chunk]) -> None:
        if not chunks:
            return
        collection = self.client.get_or_create_collection(_collection_name(namespace), metadata={"namespace": namespace, "dimension": self.embedding.dimension})
        collection.upsert(ids=[chunk.id for chunk in chunks], documents=[chunk.text for chunk in chunks],
                          metadatas=[chunk.metadata for chunk in chunks], embeddings=self.embedding.embed_documents([chunk.text for chunk in chunks]))

    def search(self, namespace: str, query: str, top_k: int) -> list[SearchResult]:
        try:
            collection = self.client.get_collection(_collection_name(namespace))
        except Exception:
            return []
        result = collection.query(query_embeddings=[self.embedding.embed_query(query)], n_results=top_k, include=["documents", "metadatas", "distances"])
        ids = result.get("ids", [[]])[0]
        documents = result.get("documents", [[]])[0]
        metadata = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]
        return [SearchResult(identifier, document, float(distance), item or {}) for identifier, document, item, distance in zip(ids, documents, metadata, distances)]

    def close(self) -> None:
        """Release Chroma's SQLite handles during controlled application/test shutdown."""
        if not getattr(self, "_closed", False):
            self.client.close()
            self._closed = True

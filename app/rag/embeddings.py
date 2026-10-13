from __future__ import annotations

import hashlib
import math
import os
from typing import Protocol

import app.config  # noqa: F401 - importing the configuration module loads project .env once.


class EmbeddingProvider(Protocol):
    dimension: int
    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...
    def embed_query(self, text: str) -> list[float]: ...


class DeterministicEmbedding:
    """Dependency-free hash embedding used by demos and offline tests."""
    dimension = 64

    def _embed(self, text: str) -> list[float]:
        values = [0.0] * self.dimension
        for word in text.casefold().split():
            values[int(hashlib.sha256(word.encode()).hexdigest(), 16) % self.dimension] += 1.0
        norm = math.sqrt(sum(value * value for value in values)) or 1.0
        return [value / norm for value in values]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)


class MultilingualE5Embedding:
    """Adapted from 01_agent: E5 prefixes plus normalized multilingual vectors."""
    def __init__(self, model_name: str = "intfloat/multilingual-e5-small") -> None:
        from sentence_transformers import SentenceTransformer
        self._model = SentenceTransformer(model_name)
        self.dimension = self._model.get_sentence_embedding_dimension()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._model.encode([f"passage: {text}" for text in texts], normalize_embeddings=True).tolist()

    def embed_query(self, text: str) -> list[float]:
        return self._model.encode([f"query: {text}"], normalize_embeddings=True)[0].tolist()


def build_embedding() -> EmbeddingProvider:
    """Use the validated E5 provider when explicitly configured; preserve offline mode by default."""
    return MultilingualE5Embedding() if os.getenv("STAGE2_EMBEDDING_PROVIDER", "deterministic").casefold() == "e5" else DeterministicEmbedding()

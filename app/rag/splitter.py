from __future__ import annotations

import hashlib

from app.schemas import Chunk, ParsedDocument


def split_document(document: ParsedDocument, namespace: str, *, chunk_size: int = 800, overlap: int = 100) -> list[Chunk]:
    if chunk_size < 1 or overlap < 0 or overlap >= chunk_size:
        raise ValueError("chunk_size must be positive and overlap smaller than it")
    text = document.text.strip()
    chunks: list[Chunk] = []
    start = 0
    index = 0
    while start < len(text):
        content = text[start:start + chunk_size].strip()
        if content:
            digest = hashlib.sha256(f"{namespace}:{document.filename}:{index}:{content}".encode()).hexdigest()
            metadata = {**document.metadata, "filename": document.filename, "file_type": document.file_type,
                        "namespace": namespace, "chunk_index": index}
            chunks.append(Chunk(digest, content, metadata))
            index += 1
        start += chunk_size - overlap
    return chunks

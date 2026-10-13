"""Offline-inspectable Stage 2 RAG acceptance demo."""
import os
import shutil
import sys
from pathlib import Path

# Make this explicit demo runnable as `python scripts\\demo_rag.py` before editable install.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

from app.rag import DeterministicEmbedding, MultilingualE5Embedding, RAGService
from app.rag.vector_store import ChromaVectorStore
from app.schemas import ParsedDocument

root = Path(__file__).resolve().parents[1]
demo_path = root / "data" / "demo_chroma"
shutil.rmtree(demo_path, ignore_errors=True)
embedding = MultilingualE5Embedding() if os.getenv("STAGE2_EMBEDDING_PROVIDER") == "e5" else DeterministicEmbedding()
rag = RAGService(ChromaVectorStore(demo_path, embedding))
documents = [
    ParsedDocument("ausbildung.md", "markdown", "Ausbildung 是德国职业教育制度，通常结合企业实践和职业学校学习。", {"source": "demo"}),
    ParsedDocument("dativ.txt", "txt", "Dativ 常回答 wem。介词 mit 后面通常使用 Dativ。", {"source": "demo"}),
    ParsedDocument("interview.md", "markdown", "面试自我介绍可以说明姓名、经验和学习目标。", {"source": "demo"}),
]
chunks = rag.index_documents("knowledge:germany", documents)
query = "德国 Ausbildung 是什么？"
results = rag.search("knowledge:germany", query, top_k=3)
print("=== Stage 2 RAG Demo ===")
print(f"Documents loaded: {len(documents)}")
print(f"Chunks created: {chunks}")
print("Namespace / collection: knowledge:germany / stage2_knowledge_germany")
print(f"Query: {query}")
print("Top-3:")
for index, item in enumerate(results, 1):
    print(f"\n[{index}]\nscore(distance): {item.score:.4f}\nsource: {item.metadata.get('filename')}\ncontent: {item.text[:160]}")

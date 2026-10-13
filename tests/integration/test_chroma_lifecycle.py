import shutil

from app.rag import DeterministicEmbedding
from app.rag.vector_store import ChromaVectorStore
from app.schemas import Chunk


def test_closing_one_client_keeps_second_client_usable_and_releases_temp_files(tmp_path):
    path = tmp_path / "chroma-lifecycle"
    embedding = DeterministicEmbedding()
    first = ChromaVectorStore(path, embedding)
    second = ChromaVectorStore(path, embedding)
    try:
        first.close()
        second.upsert("session:alpha", [Chunk("alpha-1", "alpha private evidence", {"filename": "alpha.txt"})])
        second.upsert("session:beta", [Chunk("beta-1", "beta private evidence", {"filename": "beta.txt"})])
        assert [item.text for item in second.search("session:alpha", "alpha", 4)] == ["alpha private evidence"]
        assert all(item.text != "alpha private evidence" for item in second.search("session:beta", "alpha", 4))
    finally:
        first.close()
        second.close()
    shutil.rmtree(path)
    assert not path.exists()

from app.rag.vector_store import ChromaVectorStore


def test_vector_store_closes_its_chroma_client():
    class Client:
        closed = False

        def close(self):
            self.closed = True

    store = object.__new__(ChromaVectorStore)
    store.client = Client()
    store.close()
    assert store.client.closed is True

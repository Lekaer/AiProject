from AiLearning.rag import embedder, vector_store


def retrieve(query: str, collection_name: str, top_k: int = 5) -> list[str]:
    """Retrieve the top_k most relevant document contents for a query."""
    query_vecs = embedder.embed_texts([query])
    return vector_store.search(query_vecs[0], collection_name, top_k=top_k)

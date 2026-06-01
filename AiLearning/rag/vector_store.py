import os
import uuid

import chromadb
from chromadb.api import ClientAPI
from chromadb.config import Settings

DB_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "chroma_db")

_client: ClientAPI | None = None


def _get_client() -> chromadb.PersistentClient:
    global _client
    if _client is None:
        os.makedirs(DB_DIR, exist_ok=True)
        _client = chromadb.PersistentClient(
            path=DB_DIR,
            settings=Settings(anonymized_telemetry=False),
        )
    return _client


def save_documents(docs, embeddings, collection_name):
    """Store documents and their embeddings into a Chroma collection."""
    client = _get_client()
    collection = client.get_or_create_collection(name=collection_name)

    ids = [str(uuid.uuid4()) for _ in docs]
    texts = [getattr(doc, "page_content", str(doc)) for doc in docs]

    collection.add(ids=ids, documents=texts, embeddings=embeddings)


def search(query_embedding, collection_name, top_k=3):
    """Search for the top_k most similar documents by embedding vector."""
    client = _get_client()
    collection = client.get_or_create_collection(name=collection_name)

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
    )
    return results["documents"][0] if results["documents"] else []

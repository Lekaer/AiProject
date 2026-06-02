import os
import uuid

import chromadb
from chromadb.api import ClientAPI
from chromadb.config import Settings

# ChromaDB 持久化存储目录（项目根目录下的 chroma_db/）
DB_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "chroma_db")

# ChromaDB 客户端单例
_client: ClientAPI | None = None


def _get_client() -> chromadb.PersistentClient:
    """获取或初始化 ChromaDB 持久化客户端（懒加载单例）。"""
    global _client
    if _client is None:
        os.makedirs(DB_DIR, exist_ok=True)
        _client = chromadb.PersistentClient(
            path=DB_DIR,
            settings=Settings(anonymized_telemetry=False),  # 关闭匿名遥测
        )
    return _client


def save_documents(docs, embeddings, collection_name):
    """将文档及其 embedding 向量存入 Chroma 集合。

    每个文档生成唯一 UUID 作为主键，集合名由上传文件名决定。
    """
    client = _get_client()
    collection = client.get_or_create_collection(name=collection_name)

    ids = [str(uuid.uuid4()) for _ in docs]
    texts = [getattr(doc, "page_content", str(doc)) for doc in docs]

    collection.add(ids=ids, documents=texts, embeddings=embeddings)


def get_all_documents(collection_name: str) -> list[str]:
    """返回集合中所有文档的文本列表。"""
    client = _get_client()
    collection = client.get_or_create_collection(name=collection_name)
    result = collection.get()
    return result["documents"] if result["documents"] else []


def search(query_embedding, collection_name, top_k=3):
    """按 embedding 向量搜索 top_k 个最相似的文档。

    返回文档文本列表，若结果为空则返回空列表。
    """
    client = _get_client()
    collection = client.get_or_create_collection(name=collection_name)

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
    )
    return results["documents"][0] if results["documents"] else []

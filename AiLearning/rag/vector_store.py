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
            settings=Settings(anonymized_telemetry=False),
        )
    return _client


def save_documents(docs, embeddings, collection_name, file_hash=None, filename=None):
    """将文档及其 embedding 向量存入 Chroma 集合。

    每个文档生成唯一 UUID 作为主键。
    metadata 中保存 file_hash（内容去重）和 filename（用户可见的文件名）。
    """
    client = _get_client()
    collection = client.get_or_create_collection(name=collection_name)

    ids = [str(uuid.uuid4()) for _ in docs]
    texts = [getattr(doc, "page_content", str(doc)) for doc in docs]

    metadata = {}
    if file_hash:
        metadata["file_hash"] = file_hash
    if filename:
        metadata["filename"] = filename

    metadatas = [metadata for _ in docs] if metadata else None
    collection.add(ids=ids, documents=texts, embeddings=embeddings, metadatas=metadatas)


def get_all_documents(collection_name: str) -> list[str]:
    """返回集合中所有文档的文本列表。"""
    client = _get_client()
    collection = client.get_or_create_collection(name=collection_name)
    result = collection.get()
    return result["documents"] if result["documents"] else []


def search(query_embedding, collection_name, top_k=3):
    """按 embedding 向量搜索 top_k 个最相似的文档。"""
    client = _get_client()
    collection = client.get_or_create_collection(name=collection_name)

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
    )
    return results["documents"][0] if results["documents"] else []


def ensure_collection(collection_name: str, metadata: dict | None = None):
    """确保集合存在（不存在则创建空集合，可附带 metadata）。"""
    _get_client().get_or_create_collection(name=collection_name, metadata=metadata)


def collection_exists(collection_name: str) -> bool:
    """检查指定名称的集合是否存在。"""
    client = _get_client()
    try:
        client.get_collection(name=collection_name)
        return True
    except Exception:
        return False


def delete_collection(collection_name: str):
    """删除指定集合及其全部数据，不存在则静默跳过。"""
    client = _get_client()
    try:
        client.delete_collection(name=collection_name)
    except Exception:
        pass


def delete_by_filename(collection_name: str, filename: str) -> int:
    """删除集合中指定 filename 的所有 chunks，返回删除数量。

    集合不存在或没有匹配项时返回 0。
    """
    client = _get_client()
    try:
        collection = client.get_collection(name=collection_name)
        # 先查有多少条匹配，再删除
        result = collection.get(where={"filename": filename})
        count = len(result["ids"]) if result["ids"] else 0
        if count > 0:
            collection.delete(where={"filename": filename})
        return count
    except Exception:
        return 0


def get_by_filename(collection_name: str, filename: str) -> list[str]:
    """获取指定文件名的所有 chunk 文本。

    集合不存在或没有匹配项时返回空列表。
    """
    client = _get_client()
    try:
        collection = client.get_collection(name=collection_name)
        result = collection.get(where={"filename": filename})
        return result["documents"] if result["documents"] else []
    except Exception:
        return []


def list_filenames(collection_name: str) -> list[str]:
    """返回集合中所有不重复的文件名。"""
    client = _get_client()
    try:
        collection = client.get_collection(name=collection_name)
        result = collection.get()
        if not result["metadatas"]:
            return []
        filenames = {m.get("filename", "") for m in result["metadatas"] if m}
        filenames.discard("")
        return sorted(filenames)
    except Exception:
        return []


def list_collections_by_prefix(prefix: str) -> list[dict]:
    """列出所有以 prefix 开头的集合，返回 [{name, kb_name}, ...]。

    kb_name 从 collection metadata 中读取，若不存在则回退到 collection name。
    """
    client = _get_client()
    try:
        collections = client.list_collections()
        result = []
        for c in collections:
            if c.name.startswith(prefix):
                meta = c.metadata or {}
                result.append({
                    "name": c.name,
                    "kb_name": meta.get("kb_name", c.name),
                })
        return result
    except Exception:
        return []

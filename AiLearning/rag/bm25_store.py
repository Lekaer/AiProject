import os
import pickle

import jieba
from rank_bm25 import BM25Okapi

# BM25 索引持久化目录
INDEX_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "bm25_indices")


def _index_path(collection_name: str) -> str:
    os.makedirs(INDEX_DIR, exist_ok=True)
    return os.path.join(INDEX_DIR, f"{collection_name}.pkl")


def _tokenize(text: str) -> list[str]:
    return list(jieba.cut(text))


def build_index(collection_name: str, documents: list[str]):
    """对文档构建 BM25 索引并持久化到磁盘。"""
    tokenized = [_tokenize(doc) for doc in documents]
    index = BM25Okapi(tokenized)
    data = {"docs": documents, "index": index}
    with open(_index_path(collection_name), "wb") as f:
        pickle.dump(data, f)


def load_index(collection_name: str) -> dict | None:
    """从磁盘加载 BM25 索引数据，不存在则返回 None。"""
    path = _index_path(collection_name)
    if not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        return pickle.load(f)


def search(query: str, collection_name: str, top_k: int = 5) -> list[str]:
    """BM25 检索，返回文档文本列表（不含分数）。"""
    data = load_index(collection_name)
    if data is None:
        return []
    index = data["index"]
    docs = data["docs"]
    tokenized_query = _tokenize(query)
    scores = index.get_scores(tokenized_query)
    top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
    return [docs[i] for i in top_indices]


def delete_index(collection_name: str):
    """删除指定集合的 BM25 索引文件，不存在则静默跳过。"""
    path = _index_path(collection_name)
    if os.path.exists(path):
        os.unlink(path)

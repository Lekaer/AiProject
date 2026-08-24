import logging
import time

from AiLearning.rag import embedder, vector_store, bm25_store

logger = logging.getLogger(__name__)


def _rrf_fusion(
    vector_results: list[str],
    bm25_results: list[str],
    k: int = 60,
) -> list[str]:
    """使用 RRF (Reciprocal Rank Fusion) 融合两路检索结果。

    对双路召回去重后按 RRF 分数降序排列，k=60 为常用常数。
    """
    score: dict[str, float] = {}

    for rank, doc in enumerate(vector_results):
        if doc not in score:
            score[doc] = 0.0
        score[doc] += 1.0 / (k + rank + 1)

    for rank, doc in enumerate(bm25_results):
        if doc not in score:
            score[doc] = 0.0
        score[doc] += 1.0 / (k + rank + 1)

    sorted_docs = sorted(score.keys(), key=lambda d: score[d], reverse=True)
    return sorted_docs


def retrieve_from_multiple_collections(
    query: str,
    collection_names: list[str],
    top_k: int = 5,
) -> list[str]:
    """跨多个知识库混合检索，RRF 融合后返回 top_k 个文档。"""
    t0 = time.perf_counter()
    recall_k = top_k * 2
    query_vecs = embedder.embed_queries([query])
    query_vec = query_vecs[0]
    score: dict[str, float] = {}

    for collection_name in collection_names:
        vector_results = vector_store.search(query_vec, collection_name, top_k=recall_k)
        bm25_results = bm25_store.search(query, collection_name, top_k=recall_k)

        for rank, doc in enumerate(vector_results):
            score[doc] = score.get(doc, 0.0) + 1.0 / (60 + rank + 1)

        for rank, doc in enumerate(bm25_results):
            score[doc] = score.get(doc, 0.0) + 1.0 / (60 + rank + 1)

    result = sorted(score.keys(), key=lambda d: score[d], reverse=True)[:top_k]
    elapsed = round((time.perf_counter() - t0) * 1000)
    logger.info("多库检索完成 collections=%d docs=%d elapsed=%dms", len(collection_names), len(result), elapsed)
    return result


def retrieve(query: str, collection_name: str, top_k: int = 5) -> list[str]:
    """混合检索：向量 + BM25，RRF 融合后返回 top_k 个文档。"""
    t0 = time.perf_counter()
    recall_k = top_k * 2

    # 向量检索（使用 BGE 查询前缀）
    query_vecs = embedder.embed_queries([query])
    vector_results = vector_store.search(query_vecs[0], collection_name, top_k=recall_k)

    # BM25 关键词检索
    bm25_results = bm25_store.search(query, collection_name, top_k=recall_k)

    # RRF 融合
    fused = _rrf_fusion(vector_results, bm25_results)

    result = fused[:top_k]
    elapsed = round((time.perf_counter() - t0) * 1000)
    logger.info("混合检索完成 collection=%s docs=%d elapsed=%dms query=%.80s", collection_name, len(result), elapsed, query)
    return result

from AiLearning.rag import embedder, vector_store, bm25_store


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

    return sorted(score.keys(), key=lambda d: score[d], reverse=True)[:top_k]


def retrieve(query: str, collection_name: str, top_k: int = 5) -> list[str]:
    """混合检索：向量 + BM25，RRF 融合后返回 top_k 个文档。"""
    # 每路召回 top_k * 2 个结果，给融合留冗余
    recall_k = top_k * 2

    # 向量检索（使用 BGE 查询前缀）
    query_vecs = embedder.embed_queries([query])
    vector_results = vector_store.search(query_vecs[0], collection_name, top_k=recall_k)

    # BM25 关键词检索
    bm25_results = bm25_store.search(query, collection_name, top_k=recall_k)

    # RRF 融合
    fused = _rrf_fusion(vector_results, bm25_results)

    return fused[:top_k]

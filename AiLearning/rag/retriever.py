from AiLearning.rag import embedder, vector_store


def retrieve(query: str, collection_name: str, top_k: int = 5) -> list[str]:
    """根据查询语句检索 top_k 个最相关的文档内容。

    流程：将查询文本 embedding → 向量搜索 → 返回文档内容列表。
    """
    # 将查询文本转为 embedding 向量
    query_vecs = embedder.embed_texts([query])
    # 在 ChromaDB 中按向量相似度搜索
    return vector_store.search(query_vecs[0], collection_name, top_k=top_k)

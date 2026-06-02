from sentence_transformers import SentenceTransformer

# 本地 embedding 模型名称，支持中英文多语言
MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"

# 模型单例，避免重复加载
_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    """获取或初始化 embedding 模型（懒加载单例）。"""
    global _model
    if _model is None:
        _model = SentenceTransformer(MODEL_NAME)
    return _model


def embed_texts(texts: list[str]) -> list[list[float]]:
    """将文本列表转换为 embedding 向量列表。"""
    model = _get_model()
    # normalize_embeddings=True 使向量归一化，提升相似度计算的准确性
    embeddings = model.encode(texts, normalize_embeddings=True)
    return embeddings.tolist()

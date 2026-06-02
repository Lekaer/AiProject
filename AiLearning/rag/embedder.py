from sentence_transformers import SentenceTransformer

# BGE 中文检索模型，1024 维，相比 MiniLM 对中文语义区分能力更强
# 优先从 ModelScope 本地缓存加载（国内更快），回退到 HuggingFace
import os
_LOCAL_PATH = os.path.expanduser("~/.cache/modelscope/BAAI/bge-large-zh-v1.5")
MODEL_NAME = _LOCAL_PATH if os.path.isdir(_LOCAL_PATH) else "BAAI/bge-large-zh-v1.5"

# BGE 模型要求查询文本加此前缀以区分查询/文档编码
QUERY_PREFIX = "为这个句子生成表示以用于检索相关文章："

# 模型单例，避免重复加载
_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    """获取或初始化 embedding 模型（懒加载单例）。"""
    global _model
    if _model is None:
        _model = SentenceTransformer(MODEL_NAME)
    return _model


def embed_texts(texts: list[str]) -> list[list[float]]:
    """将文档文本列表转换为 embedding 向量列表（不加前缀）。"""
    model = _get_model()
    embeddings = model.encode(texts, normalize_embeddings=True)
    return embeddings.tolist()


def embed_queries(queries: list[str]) -> list[list[float]]:
    """将查询文本列表转换为 embedding 向量列表（加 BGE 查询前缀）。"""
    model = _get_model()
    prefixed = [QUERY_PREFIX + q for q in queries]
    embeddings = model.encode(prefixed, normalize_embeddings=True)
    return embeddings.tolist()

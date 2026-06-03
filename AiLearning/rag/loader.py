from pathlib import Path

from langchain_core.documents import Document
from langchain_community.document_loaders import PyPDFLoader, TextLoader

# 文件扩展名 → 对应加载器的映射
LOADER_MAP = {
    ".pdf": PyPDFLoader,
    ".txt": TextLoader,
}


def load_document(file_path: str) -> list[Document]:
    """加载文档并返回 langchain Document 对象列表。

    支持 PDF（通过 PyPDFLoader）和 TXT（通过 TextLoader），
    根据文件扩展名自动选择加载器。
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")

    suffix = path.suffix.lower()
    loader_cls = LOADER_MAP.get(suffix)
    if loader_cls is None:
        raise ValueError(
            f"不支持的文件类型: {suffix}。支持的类型: {list(LOADER_MAP)}"
        )

    loader = loader_cls(str(path))
    docs = loader.load()

    # 过滤空文档（TextLoader 对空文件也会生成一个 page_content="" 的 Document）
    docs = [d for d in docs if d.page_content.strip()]
    if not docs:
        raise ValueError(f"文件内容为空: {file_path}")

    return docs

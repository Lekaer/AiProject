from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter


def split_documents(
    documents: list[Document],
    chunk_size: int = 500,
    chunk_overlap: int = 50,
) -> list[Document]:
    """将文档列表切分为更小的文本块。

    使用递归字符分割器，按 chunk_size 切分，相邻块之间保留 chunk_overlap
    的重叠内容，避免语义在边界处断裂。
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    return splitter.split_documents(documents)

from pathlib import Path

from langchain_core.documents import Document
from langchain_community.document_loaders import PyPDFLoader, TextLoader


LOADER_MAP = {
    ".pdf": PyPDFLoader,
    ".txt": TextLoader,
}


def load_document(file_path: str) -> list[Document]:
    """Load a document and return a list of langchain Document objects.

    Supports PDF (via PyPDFLoader) and TXT (via TextLoader). The loader
    is selected based on the file extension.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    suffix = path.suffix.lower()
    loader_cls = LOADER_MAP.get(suffix)
    if loader_cls is None:
        raise ValueError(
            f"Unsupported file type: {suffix}. Supported: {list(LOADER_MAP)}"
        )

    loader = loader_cls(str(path))
    return loader.load()

import hashlib
import json
import os
import tempfile

from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from AiLearning.rag.bm25_store import build_index as build_bm25_index
from AiLearning.rag.embedder import embed_texts
from AiLearning.rag.generator import generate
from AiLearning.rag.loader import load_document
from AiLearning.rag.retriever import retrieve
from AiLearning.rag.splitter import split_documents
from AiLearning.rag.vector_store import save_documents


def _sanitize_collection_name(filename: str) -> str:
    """Convert a filename into a valid Chroma collection name."""
    import re

    base = os.path.splitext(filename)[0]
    sanitized = re.sub(r"[^a-zA-Z0-9._-]", "_", base)
    sanitized = sanitized.strip("_")
    if not sanitized or len(sanitized) < 3:
        sanitized = "col_" + hashlib.md5(base.encode()).hexdigest()[:16]
    return sanitized


def init(request):
    return HttpResponse("Hello Django AI Learning")


@csrf_exempt
def upload_doc(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    uploaded = request.FILES.get("file")
    if not uploaded:
        return JsonResponse({"error": "No file uploaded"}, status=400)

    suffix = os.path.splitext(uploaded.name)[1].lower()
    if suffix not in (".pdf", ".txt"):
        return JsonResponse({"error": f"Unsupported format: {suffix}"}, status=400)

    # Save uploaded file to a temp file so load_document can read it
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        for chunk in uploaded.chunks():
            tmp.write(chunk)
        tmp_path = tmp.name

    try:
        collection_name = _sanitize_collection_name(uploaded.name)
        docs = load_document(tmp_path)
        chunks = split_documents(docs)
        texts = [c.page_content for c in chunks]
        embeddings = embed_texts(texts)
        save_documents(chunks, embeddings, collection_name)
        build_bm25_index(collection_name, texts)

        return JsonResponse({
            "message": "Document indexed successfully",
            "collection": collection_name,
            "pages": len(docs),
            "chunks": len(chunks),
        })
    finally:
        os.unlink(tmp_path)


@csrf_exempt
def ask(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    question = body.get("question", "").strip()
    if not question:
        return JsonResponse({"error": "question is required"}, status=400)

    collection_name = body.get("collection", "merchant_credit")
    context_docs = retrieve(question, collection_name)
    answer = generate(question, context_docs)

    return JsonResponse({"answer": answer})

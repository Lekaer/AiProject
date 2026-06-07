import hashlib
import json
import os
import tempfile

from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from AiLearning.rag.bm25_store import build_index as build_bm25_index
from AiLearning.rag.bm25_store import delete_index as delete_bm25_index
from AiLearning.rag.embedder import embed_texts
from AiLearning.rag.generator import generate
from AiLearning.rag.loader import load_document
from AiLearning.rag.retriever import retrieve
from AiLearning.rag.splitter import split_documents
from AiLearning.rag.vector_store import (
    collection_exists,
    delete_by_filename,
    delete_collection,
    ensure_collection,
    get_all_documents,
    list_collections_by_prefix,
    list_filenames,
    save_documents,
)


# ── helpers ────────────────────────────────────────────────────────────


def _sanitize_name(name: str) -> str:
    """将用户输入的名称转为 ChromaDB 允许的字符集 [a-zA-Z0-9._-] 。"""
    import re

    sanitized = re.sub(r"[^a-zA-Z0-9._-]+", "_", name).strip("._-")
    if not sanitized or len(sanitized) < 2:
        sanitized = "unnamed"
    return sanitized


def _get_project_id(request) -> str:
    """从 header (X-Project-Id) 或 query param 获取 project_id。"""
    pid = (request.headers.get("X-Project-Id", "") or
           request.GET.get("project_id", "") or
           request.POST.get("project_id", "")).strip()
    return pid


def _kb_key(project_id: str, kb_name: str) -> str:
    """拼接 project_id + kb_name 哈希，生成 ChromaDB 合法的集合名。

    格式: {safe_pid}__{md5[:10]}
    原始 kb_name 存入 collection metadata，列表时从 metadata 读取。
    """
    safe_pid = _sanitize_name(project_id)
    hash_suffix = hashlib.md5(kb_name.encode()).hexdigest()[:10]
    return f"{safe_pid}__{hash_suffix}"


def _require_project(request) -> str:
    """获取 project_id，缺失时抛 400。"""
    pid = _get_project_id(request)
    if not pid:
        raise ValueError("project_id is required (header X-Project-Id)")
    return pid


def _parse_body(request) -> dict:
    """解析 JSON body，解析失败返回空 dict。"""
    try:
        return json.loads(request.body)
    except (json.JSONDecodeError, AttributeError):
        return {}


# ── health ─────────────────────────────────────────────────────────────

def init(request):
    return HttpResponse("Hello Django AI Learning")


# ── knowledge base CRUD ────────────────────────────────────────────────

@csrf_exempt
def kb_view(request):
    """POST /api/kb → 创建知识库
    GET  /api/kb → 列出知识库
    """
    try:
        project_id = _require_project(request)
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=400)

    if request.method == "POST":
        body = _parse_body(request)
        kb_name = body.get("name", "").strip()
        if not kb_name:
            return JsonResponse({"error": "name is required"}, status=400)

        collection_name = _kb_key(project_id, kb_name)
        if collection_exists(collection_name):
            return JsonResponse({"error": f"知识库 '{kb_name}' 已存在"}, status=409)

        ensure_collection(collection_name, metadata={"kb_name": kb_name})
        return JsonResponse({"message": "知识库创建成功", "name": kb_name})

    if request.method == "GET":
        safe_pid = _sanitize_name(project_id)
        prefix = f"{safe_pid}__"
        items = list_collections_by_prefix(prefix)
        kb_names = [item["kb_name"] for item in items]
        return JsonResponse({"kbs": kb_names})

    return JsonResponse({"error": "method not allowed"}, status=405)


@csrf_exempt
def kb_delete(request, kb_name):
    """DELETE /api/kb/{name} → 删除整个知识库"""
    if request.method != "DELETE":
        return JsonResponse({"error": "DELETE required"}, status=405)

    try:
        project_id = _require_project(request)
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=400)

    collection_name = _kb_key(project_id, kb_name)
    existed = collection_exists(collection_name)
    delete_collection(collection_name)
    delete_bm25_index(collection_name)

    return JsonResponse({
        "message": "已删除" if existed else "知识库不存在，已清理残留",
        "name": kb_name,
    })


# ── document CRUD ──────────────────────────────────────────────────────

@csrf_exempt
def docs_view(request, kb_name):
    """POST   /api/kb/{name}/docs → 上传文档
    GET    /api/kb/{name}/docs → 列出文档
    DELETE /api/kb/{name}/docs → 删除文档
    """
    try:
        project_id = _require_project(request)
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=400)

    collection_name = _kb_key(project_id, kb_name)

    if request.method == "POST":
        return _upload_doc(request, project_id, kb_name, collection_name)

    if request.method == "GET":
        filenames = list_filenames(collection_name)
        return JsonResponse({"docs": filenames})

    if request.method == "DELETE":
        return _delete_doc(request, collection_name)

    return JsonResponse({"error": "method not allowed"}, status=405)


def _upload_doc(request, project_id, kb_name, collection_name):
    uploaded = request.FILES.get("file")
    if not uploaded:
        return JsonResponse({"error": "No file uploaded"}, status=400)

    filename = uploaded.name
    suffix = os.path.splitext(filename)[1].lower()
    if suffix not in (".pdf", ".txt"):
        return JsonResponse({"error": f"不支持的文件类型: {suffix}"}, status=400)

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        for chunk in uploaded.chunks():
            tmp.write(chunk)
        tmp_path = tmp.name

    try:
        with open(tmp_path, "rb") as f:
            file_hash = hashlib.md5(f.read()).hexdigest()

        # 如果同名文件已在集合中，删掉旧版本再追加
        delete_by_filename(collection_name, filename)

        # 保留旧文档文本（用于重建 BM25）
        old_texts = get_all_documents(collection_name)

        docs = load_document(tmp_path)
        chunks = split_documents(docs)
        texts = [c.page_content for c in chunks]
        embeddings = embed_texts(texts)
        save_documents(chunks, embeddings, collection_name,
                       file_hash=file_hash, filename=filename)

        # BM25 索引整体重建
        all_texts = old_texts + texts
        build_bm25_index(collection_name, all_texts)

        return JsonResponse({
            "message": "上传成功",
            "kb": kb_name,
            "filename": filename,
            "pages": len(docs),
            "chunks": len(chunks),
        })
    finally:
        os.unlink(tmp_path)


def _delete_doc(request, collection_name):
    body = _parse_body(request)
    filename = body.get("filename", "").strip()

    if filename:
        count = delete_by_filename(collection_name, filename)
        # 重建 BM25 索引
        remaining = get_all_documents(collection_name)
        if remaining:
            build_bm25_index(collection_name, remaining)
        else:
            delete_bm25_index(collection_name)

        return JsonResponse({
            "message": f"已删除 {count} 条记录",
            "filename": filename,
        })
    else:
        return JsonResponse({"error": "filename is required"}, status=400)


# ── ask ────────────────────────────────────────────────────────────────

@csrf_exempt
def ask(request, kb_name):
    """POST /api/kb/{name}/ask → 在知识库中提问"""
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    try:
        project_id = _require_project(request)
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=400)

    body = _parse_body(request)
    question = body.get("question", "").strip()
    if not question:
        return JsonResponse({"error": "question is required"}, status=400)

    collection_name = _kb_key(project_id, kb_name)
    context_docs = retrieve(question, collection_name)
    answer = generate(question, context_docs)

    return JsonResponse({"answer": answer})

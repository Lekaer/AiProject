import hashlib
import json
import logging
import os
import re
import tempfile
import threading

from fastapi import FastAPI, File, Header, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from AiLearning.rag.bm25_store import build_index as build_bm25_index
from AiLearning.rag.bm25_store import delete_index as delete_bm25_index
from AiLearning.rag.embedder import embed_texts
from AiLearning.rag.generator import generate
from AiLearning.rag.loader import load_document
from AiLearning.rag.retriever import retrieve
from AiLearning.router.agent_router import dispatch, dispatch_stream
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

app = FastAPI(title="RAG API", version="1.0.0")


# ── helpers ────────────────────────────────────────────────────────

def _sanitize_name(name: str) -> str:
    sanitized = re.sub(r"[^a-zA-Z0-9._-]+", "_", name).strip("._-")
    return sanitized if len(sanitized) >= 2 else "unnamed"


def _kb_key(project_id: str, kb_name: str) -> str:
    safe_pid = _sanitize_name(project_id)
    # 已经是内部集合名格式（如 testcase__c9f01d8ca7），直接返回
    if re.fullmatch(rf"{re.escape(safe_pid)}__[a-f0-9]+", kb_name):
        return kb_name
    hash_suffix = hashlib.md5(kb_name.encode()).hexdigest()[:10]
    return f"{safe_pid}__{hash_suffix}"


def _require_project_id(project_id: str | None) -> str:
    if not project_id:
        raise HTTPException(status_code=400, detail="project_id is required (header X-Project-Id)")
    return project_id


async def _save_upload_file(uploaded: UploadFile) -> tuple[str, str]:
    """将上传文件写入临时文件，返回 (file_path, suffix)。"""
    suffix = os.path.splitext(uploaded.filename or "")[1].lower()
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await uploaded.read()
        tmp.write(content)
        return tmp.name, suffix


def _resolve_collection_names(project_id: str, kb_names: list[str] | None,
                               default_kb_name: str | None = None) -> list[str]:
    """根据 kb_names 解析为 ChromaDB collection_name 列表。

    - kb_names 为 None：使用项目下全部 KB
    - kb_names 为空列表 []：不检索任何 KB，返回空列表
    - kb_names 有值：使用指定的 KB
    - 若指定 KB 不存在则忽略（不报错）
    """
    if kb_names is not None:
        return [_kb_key(project_id, n) for n in kb_names]
    if default_kb_name:
        return [_kb_key(project_id, default_kb_name)]
    safe_pid = _sanitize_name(project_id)
    items = list_collections_by_prefix(f"{safe_pid}__")
    return [item["name"] for item in items]


# ── request/response models ─────────────────────────────────────────

class CreateKBRequest(BaseModel):
    name: str


class DeleteDocRequest(BaseModel):
    filename: str


class AskRequest(BaseModel):
    question: str
    app: str | None = None
    requirement_doc: str | None = None
    reference_cases: str | None = None  # 参考用例文本（风格范例，仅 Phase 2 使用）
    kb_names: list[str] | None = None   # 指定 KB 名称列表，空列表=不检索，None=全部 KB


# ── health ──────────────────────────────────────────────────────────

@app.get("/")
def health():
    return {"message": "RAG API running"}


# ── knowledge base CRUD ─────────────────────────────────────────────

@app.post("/api/kb")
def create_kb(body: CreateKBRequest, project_id: str = Header(None, alias="X-Project-Id")):
    pid = _require_project_id(project_id)
    collection_name = _kb_key(pid, body.name)

    if collection_exists(collection_name):
        raise HTTPException(status_code=409, detail=f"知识库 '{body.name}' 已存在")

    ensure_collection(collection_name, metadata={"kb_name": body.name})
    return {"message": "知识库创建成功", "name": body.name}


@app.get("/api/kb")
def list_kb(project_id: str = Header(None, alias="X-Project-Id")):
    pid = _require_project_id(project_id)
    safe_pid = _sanitize_name(pid)
    items = list_collections_by_prefix(f"{safe_pid}__")
    return {"kbs": [item["kb_name"] for item in items]}


@app.delete("/api/kb/{kb_name}")
def delete_kb(kb_name: str, project_id: str = Header(None, alias="X-Project-Id")):
    pid = _require_project_id(project_id)
    collection_name = _kb_key(pid, kb_name)
    existed = collection_exists(collection_name)
    delete_collection(collection_name)
    delete_bm25_index(collection_name)
    return {
        "message": "已删除" if existed else "知识库不存在，已清理残留",
        "name": kb_name,
    }


# ── document CRUD ───────────────────────────────────────────────────

@app.post("/api/kb/{kb_name}/docs")
async def upload_doc(
    kb_name: str,
    file: UploadFile = File(...),
    project_id: str = Header(None, alias="X-Project-Id"),
):
    pid = _require_project_id(project_id)
    collection_name = _kb_key(pid, kb_name)

    filename = file.filename or "unknown"
    suffix = os.path.splitext(filename)[1].lower()
    if suffix not in (".pdf", ".txt", ".md"):
        raise HTTPException(status_code=400, detail=f"不支持的文件类型: {suffix}")

    tmp_path, _ = await _save_upload_file(file)
    try:
        with open(tmp_path, "rb") as f:
            file_hash = hashlib.md5(f.read()).hexdigest()

        # 同名文件替换：删旧版本
        delete_by_filename(collection_name, filename)
        old_texts = get_all_documents(collection_name)

        docs = load_document(tmp_path)
        chunks = split_documents(docs)
        texts = [c.page_content for c in chunks]
        embeddings = embed_texts(texts)
        save_documents(chunks, embeddings, collection_name,
                       file_hash=file_hash, filename=filename)

        all_texts = old_texts + texts
        build_bm25_index(collection_name, all_texts)

        return {
            "message": "上传成功",
            "kb": kb_name,
            "filename": filename,
            "pages": len(docs),
            "chunks": len(chunks),
        }
    finally:
        os.unlink(tmp_path)


@app.get("/api/kb/{kb_name}/docs")
def list_docs(kb_name: str, project_id: str = Header(None, alias="X-Project-Id")):
    pid = _require_project_id(project_id)
    collection_name = _kb_key(pid, kb_name)
    return {"docs": list_filenames(collection_name)}


@app.delete("/api/kb/{kb_name}/docs")
def delete_doc(
    kb_name: str,
    body: DeleteDocRequest,
    project_id: str = Header(None, alias="X-Project-Id"),
):
    pid = _require_project_id(project_id)
    collection_name = _kb_key(pid, kb_name)
    count = delete_by_filename(collection_name, body.filename)

    remaining = get_all_documents(collection_name)
    if remaining:
        build_bm25_index(collection_name, remaining)
    else:
        delete_bm25_index(collection_name)

    return {"message": f"已删除 {count} 条记录", "filename": body.filename}


# ── ask ─────────────────────────────────────────────────────────────

@app.post("/api/kb/{kb_name}/ask")
def ask(
    kb_name: str,
    body: AskRequest,
    project_id: str = Header(None, alias="X-Project-Id"),
):
    pid = _require_project_id(project_id)
    collection_names = _resolve_collection_names(pid, body.kb_names, kb_name)
    try:
        response = dispatch(
            body.question,
            app=body.app,
            collection_names=collection_names,
            requirement_doc=body.requirement_doc,
            reference_cases=body.reference_cases,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {
        "answer": response.answer,
        "agent": response.agent_name,
        "selected_skills": response.metadata.get("selected_skills", []),
    }


@app.post("/api/kb/{kb_name}/ask/stream")
async def ask_stream(
    kb_name: str,
    body: AskRequest,
    project_id: str = Header(None, alias="X-Project-Id"),
):
    """SSE streaming 版 ask：实时推送用例生成进度。

    返回 text/event-stream，每 yield 一条进度事件。
    客户端断开连接时 cancelled Event 被 set，生成器在检查点退出。
    """
    pid = _require_project_id(project_id)
    collection_names = _resolve_collection_names(pid, body.kb_names, kb_name)
    cancelled = threading.Event()

    def generate():
        try:
            for event in dispatch_stream(
                body.question,
                app=body.app,
                cancelled=cancelled,
                collection_names=collection_names,
                requirement_doc=body.requirement_doc,
            reference_cases=body.reference_cases,
            ):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except GeneratorExit:
            cancelled.set()
        except Exception:
            logging.getLogger(__name__).exception("SSE stream error")
            yield f"data: {json.dumps({'event': 'error', 'data': {'message': '服务内部错误'}}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/ask")
def ask_project(
    body: AskRequest,
    project_id: str = Header(None, alias="X-Project-Id"),
):
    """项目级问答：kb_names 指定 KB 列表，不传则使用全部 KB。"""
    pid = _require_project_id(project_id)
    collection_names = _resolve_collection_names(pid, body.kb_names)
    if not collection_names:
        raise HTTPException(status_code=404, detail="该项目下没有知识库")
    try:
        response = dispatch(
            body.question,
            app=body.app,
            collection_names=collection_names,
            requirement_doc=body.requirement_doc,
            reference_cases=body.reference_cases,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {
        "answer": response.answer,
        "agent": response.agent_name,
        "selected_skills": response.metadata.get("selected_skills", []),
    }


@app.post("/api/ask/stream")
async def ask_project_stream(
    body: AskRequest,
    project_id: str = Header(None, alias="X-Project-Id"),
):
    """项目级 SSE streaming 问答。"""
    pid = _require_project_id(project_id)
    collection_names = _resolve_collection_names(pid, body.kb_names)
    if not collection_names:
        raise HTTPException(status_code=404, detail="该项目下没有知识库")

    cancelled = threading.Event()

    def generate():
        try:
            for event in dispatch_stream(
                body.question,
                app=body.app,
                cancelled=cancelled,
                collection_names=collection_names,
                requirement_doc=body.requirement_doc,
            reference_cases=body.reference_cases,
            ):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except GeneratorExit:
            cancelled.set()
        except Exception:
            logging.getLogger(__name__).exception("SSE stream error")
            yield f"data: {json.dumps({'event': 'error', 'data': {'message': '服务内部错误'}}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ── document parsing ──────────────────────────────────────────────────

@app.post("/api/parse-doc")
async def parse_doc(file: UploadFile = File(...)):
    """解析上传的需求文档（PDF/TXT），返回纯文本。不存入知识库。"""
    suffix = os.path.splitext(file.filename or "")[1].lower()
    if suffix not in (".pdf", ".txt", ".md"):
        raise HTTPException(status_code=400, detail=f"不支持的文件类型: {suffix}")
    tmp_path, _ = await _save_upload_file(file)
    try:
        docs = load_document(tmp_path)
        text = "\n\n".join(d.page_content for d in docs)
        return {"text": text, "filename": file.filename}
    finally:
        os.unlink(tmp_path)


# ── static files ─────────────────────────────────────────────────────

import os as _os

_static_dir = _os.path.join(_os.path.dirname(__file__), "static")
if _os.path.isdir(_static_dir):
    app.mount("/static", StaticFiles(directory=_static_dir), name="static")

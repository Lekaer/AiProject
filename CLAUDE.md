# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run Django dev server
python manage.py runserver

# Run standalone scripts (any .py file under AiLearning/)
python AiLearning/rag/test.py

# Django shell with app context
python manage.py shell

# Run RAG pipeline tests
python -m pytest AiLearning/rag/tests/ -v

# Run LLM judge evaluation (reads generation_result.json, scores with AI)
python test_llm_judge.py
```

## Architecture

Single Django app (`AiLearning`) for AI/RAG experimentation. No database models — the app is a shell for calling LLMs and serving a RAG pipeline.

### AI Client (`rag/generator.py`)

The core abstraction. `AIClient` wraps the OpenAI-compatible SDK, targeting DeepSeek by default. All OpenAI SDK errors are unified under `AIError`.

- `get_client()` — module-level singleton. In Django context reads `settings.DEEPSEEK_*`; outside Django falls back to env vars with hardcoded defaults.
- `AIClient.chat()` — non-streaming chat, returns `str`
- `AIClient.chat_stream()` — streaming chat, yields `str` chunks
- `AIClient.embed()` / `embed_batch()` — API-based embedding (not used by the RAG pipeline; see below)
- `generate(question, context_docs)` — convenience function that formats `PROMPT_TEMPLATE` with a question and retrieved context, then calls `chat()`. This is what `views.ask` uses.

**Import path for other modules:**

```python
from AiLearning.service import get_client, AIError, AIClient
```

`service/__init__.py` re-exports from `rag.generator.py` — use this path, not the `rag` import directly.

### RAG Pipeline (`rag/`)

The ingestion and retrieval flow:

```
upload_doc view                     ask view
    │                                  │
    ▼                                  │
loader.py (PDF/TXT → Documents)        │
    │                                  │
splitter.py (RecursiveTextSplitter, chunk_size=500, chunk_overlap=100)
    │                                  │
embedder.py (SentenceTransformer: bge-large-zh-v1.5, 1024-dim, normalize_embeddings=True)
    │                                  │
vector_store.py (ChromaDB PersistentClient at ../chroma_db/)
    │                                  │
bm25_store.py (BM25Okapi with jieba tokenizer, persisted to ../bm25_indices/)
    │                                  │
    └──────────────────────────────────┤
                                       ▼
                              retriever.py (hybrid: vector + BM25, RRF fusion → top-k docs)
                                       │
                                       ▼
                              generator.generate() (prompt + LLM → answer)
```

**Two separate embedding paths exist:**
- `embedder.py` — local `bge-large-zh-v1.5` model (from BAAI). Prefers ModelScope local cache at `~/.cache/modelscope/BAAI/bge-large-zh-v1.5`, falls back to HuggingFace. Two functions: `embed_texts()` for documents (no prefix), `embed_queries()` for queries (prefixed with BGE instruction).
- `AIClient.embed()` / `embed_batch()` — calls the DeepSeek API for embeddings. Available but not wired into the RAG flow.

**Hybrid retrieval (retriever.py):**
- Queries both vector search (ChromaDB) and BM25 keyword search in parallel, each retrieving `top_k * 2` candidates.
- Uses RRF (Reciprocal Rank Fusion, k=60) to merge and deduplicate results into a final top_k ranking.
- `bm25_store.py` tokenizes Chinese text with jieba, builds `BM25Okapi` indices, and pickles them to `bm25_indices/<collection_name>.pkl`.

Key details:
- `vector_store.py` persists ChromaDB data to `chroma_db/` at the project root. Collections are named by sanitizing the uploaded filename.
- Two PDF test documents live in `AiLearning/docs/`.

### Web Layer (`views.py`)

Three endpoints (CSRF-exempt on upload/ask):

- `GET /` — health check, returns "Hello Django AI Learning"
- `POST /upload` — multipart form upload (field: `file`). Accepts `.pdf`/`.txt`. Runs the full ingestion pipeline (load → split → embed → save to ChromaDB → build BM25 index). Returns `{message, collection, pages, chunks}`.
- `POST /ask` — JSON body with `question` (required) and optional `collection` (default: `"merchant_credit"`). Runs hybrid retrieval then LLM generation. Returns `{answer}`.

### Testing & Evaluation

Tests in `AiLearning/rag/tests/`:
- `test_retrieval.py` — verifies retrieval hits expected docs for known queries
- `test_generation.py` — runs questions through the full RAG pipeline, saves results to `generation_result.json`
- `test_edge_cases.py` — empty queries, nonexistent collections, etc.

Root-level `test_llm_judge.py` evaluates generation quality by calling an LLM to score each answer on faithfulness/relevance/completeness (1-5). Reads `generation_result.json`, outputs `judge_result.json`.

### Configuration

DeepSeek credentials in `AiProject/settings.py` with env var overrides:

- `DEEPSEEK_API_KEY` (default: hardcoded key)
- `DEEPSEEK_BASE_URL` (default: `https://api.deepseek.com`)
- `DEEPSEEK_MODEL` (default: `deepseek-v4-pro`)
- `DEEPSEEK_TIMEOUT` (default: `60`)

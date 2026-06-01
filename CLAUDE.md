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
```

No test suite, linter, or build step is configured yet.

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

Fully implemented retrieval-augmented generation pipeline. The flow is:

```
upload_doc view                     ask view
    │                                  │
    ▼                                  │
loader.py (PDF/TXT → Documents)        │
    │                                  │
splitter.py (chunk with RecursiveTextSplitter, 500/50)
    │                                  │
embedder.py (SentenceTransformer: paraphrase-multilingual-MiniLM-L12-v2)
    │                                  │
vector_store.py (ChromaDB PersistentClient at ../chroma_db/)
    │                                  │
    └──────────────────────────────────┤
                                       ▼
                              retriever.py (embed query → vector search → top-k docs)
                                       │
                                       ▼
                              generator.generate() (prompt + LLM → answer)
```

**Two separate embedding paths exist:**
- `embedder.py` — local `SentenceTransformer` model, used by the RAG pipeline for both document indexing and query embedding.
- `AIClient.embed()` / `embed_batch()` — calls the DeepSeek API for embeddings. Available but not wired into the RAG flow.

Key details:
- `vector_store.py` persists ChromaDB data to `chroma_db/` at the project root. Collections are named by sanitizing the uploaded filename.
- `retriever.py` embeds the query with the local model, then runs vector search against ChromaDB.
- Two PDF test documents live in `AiLearning/docs/`.

### Web Layer (`views.py`)

Two CSRF-exempt POST endpoints:

- `POST /upload` — multipart form upload (field: `file`). Accepts `.pdf`/`.txt`. Runs the full ingestion pipeline and returns `{message, collection, pages, chunks}`.
- `POST /ask` — JSON body with `question` (required) and optional `collection` (default: `"merchant_credit"`). Returns `{answer}`.

### Configuration

DeepSeek credentials in `DjangoProject/settings.py` with env var overrides:

- `DEEPSEEK_API_KEY` (default: hardcoded key)
- `DEEPSEEK_BASE_URL` (default: `https://api.deepseek.com`)
- `DEEPSEEK_MODEL` (default: `deepseek-v4-pro`)
- `DEEPSEEK_TIMEOUT` (default: `60`)

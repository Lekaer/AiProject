# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run dev server (auto-reload on code changes)
uvicorn main:app --reload

# Run standalone scripts (always use -m from project root)
python -m AiLearning.agents.test
python -m AiLearning.router.agent_router

# Run RAG pipeline tests
python -m pytest AiLearning/rag/tests/ -v

# Run LLM judge evaluation
python test_llm_judge.py
```

API docs available at `http://127.0.0.1:8000/docs` (Swagger UI) and `/redoc` while the server is running.

## Architecture

FastAPI app (`main.py`) serving a RAG pipeline with agent-based routing. No database — the app calls LLMs and manages a local vector index.

### Agent Layer (`AiLearning/agents/`, `AiLearning/router/`, `AiLearning/prompts/`)

Three agents, all subclassing `BaseAgent` (ABC with `name` and `execute(question, **kwargs) -> AgentResponse`):

| Agent | Name | Purpose | Temperature |
|-------|------|---------|-------------|
| `RAGAgent` | `rag` | General knowledge base Q&A | 0.0 |
| `LearningAgent` | `learning` | Learning tutor style | 0.7 |
| `TestCaseAgent` | `testcase` | Structured test case generation | (default) |

`AgentResponse` is a dataclass: `answer: str`, `agent_name: str`, `metadata: dict`.

**Router** (`agent_router.py`): `dispatch(question, app=None, **kwargs)` resolves intent in three tiers:

1. **Explicit `app`** — if provided, route directly to that agent. Raises `ValueError` for unknown agent names.
2. **Keyword match** — scan question for keywords mapped to agents (e.g., "测试"/"用例"/"test" → testcase, "学习"/"理解"/"计划" → learning).
3. **LLM intent detection** — classify via DeepSeek with `INTENT_DETECTION_PROMPT` (labels: `rag`/`testcase`/`learning`). Falls back to `rag` on failure.

All extra kwargs (e.g., `collection_name`) pass through to the agent.

Prompt templates in `AiLearning/prompts/` each contain `system` and `template` fields with a `format(context, question)` method.

### AI Client (`rag/generator.py`)

`AIClient` wraps the OpenAI-compatible SDK, targeting DeepSeek by default. All errors unified under `AIError`.

- `get_client()` — module-level singleton. Reads config from `config.py` + env vars.
- `AIClient.chat()` — non-streaming chat, returns `str`
- `AIClient.chat_stream()` — streaming chat, yields `str` chunks
- `AIClient.embed()` / `embed_batch()` — API-based embedding (not wired into RAG flow)

**Import path for other modules:**

```python
from AiLearning.service import get_client, AIError, AIClient
```

`service/__init__.py` re-exports from `rag.generator.py`.

### RAG Pipeline (`rag/`)

```
upload                           ask
  │                                │
  ▼                                │
loader.py (PDF/TXT → Documents)    │
  │                                │
splitter.py (chunk_size=500, chunk_overlap=100)
  │                                │
embedder.py (bge-large-zh-v1.5, 1024-dim)
  │                                │
vector_store.py (ChromaDB at ../chroma_db/)
  │                                │
bm25_store.py (BM25Okapi + jieba, persisted to ../bm25_indices/)
  │                                │
  └────────────────────────────────┤
                                   ▼
                          retriever.py (vector + BM25, RRF fusion → top-k)
                                   │
                                   ▼
                          router.dispatch() → agent.execute()
```

**Two separate embedding paths:**
- `embedder.py` — local BGE model. Prefers ModelScope cache (`~/.cache/modelscope/BAAI/bge-large-zh-v1.5`), falls back to HuggingFace. `embed_texts()` for documents (no prefix), `embed_queries()` for queries (with BGE instruction prefix).
- `AIClient.embed()` / `embed_batch()` — DeepSeek API embeddings. Not wired into RAG flow.

**Hybrid retrieval (retriever.py):**
- Queries vector search and BM25 in parallel, each retrieving `top_k * 2` candidates.
- RRF (k=60) merges and deduplicates results into final top_k.
- `bm25_store.py` tokenizes Chinese text with jieba, pickles indices to `bm25_indices/<collection>.pkl`.

### API (`main.py`)

All endpoints require `X-Project-Id` header for multi-tenant isolation. Knowledge base names are internally mapped to ChromaDB-safe collection names via `{safe_pid}__{md5[:10]}`; the original name is stored in collection metadata.

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Health check |
| `POST` | `/api/kb` | Create knowledge base `{name}` |
| `GET` | `/api/kb` | List knowledge bases for project |
| `DELETE` | `/api/kb/{name}` | Delete entire KB |
| `POST` | `/api/kb/{name}/docs` | Upload doc (multipart `file`) |
| `GET` | `/api/kb/{name}/docs` | List docs in KB |
| `DELETE` | `/api/kb/{name}/docs` | Delete doc `{filename}` |
| `POST` | `/api/kb/{name}/ask` | Ask question `{question}`, optional `{app}` |

Uploading a file with the same filename auto-replaces the old version. Different filenames append to the KB.

### Testing & Evaluation

Tests in `AiLearning/rag/tests/`:
- `test_retrieval.py` — verifies retrieval hits expected docs
- `test_generation.py` — full pipeline, outputs `generation_result.json`
- `test_edge_cases.py` — empty queries, missing collections, etc.

Root-level `test_llm_judge.py` scores generation quality via LLM (faithfulness/relevance/completeness 1-5). Reads `generation_result.json` → `judge_result.json`.

### Configuration

`config.py` with env var overrides:

- `DEEPSEEK_API_KEY` (default: hardcoded key)
- `DEEPSEEK_BASE_URL` (default: `https://api.deepseek.com`)
- `DEEPSEEK_MODEL` (default: `deepseek-v4-pro`)
- `DEEPSEEK_TIMEOUT` (default: `60`)

### Data directories

- `chroma_db/` — ChromaDB persistent storage
- `bm25_indices/` — pickled BM25 indices

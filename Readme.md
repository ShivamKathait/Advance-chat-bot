# RAG Chatbot API

> A production-style Retrieval-Augmented Generation backend: hybrid search (dense + BM25), reciprocal rank fusion, Cohere reranking, Gemini generation, SSE streaming, guardrails, async ingestion, and a built-in eval harness.

[![Python](https://img.shields.io/badge/Python-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Qdrant](https://img.shields.io/badge/Qdrant-DC244C?logoColor=white)](https://qdrant.tech/)
[![Redis](https://img.shields.io/badge/Redis-DC382D?logo=redis&logoColor=white)](https://redis.io/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?logo=postgresql&logoColor=white)](https://www.postgresql.org/)

---

## What This Is

This is currently a **backend-only API service** — there is no UI yet (see [Known Gaps](#known-gaps)). It's a FastAPI app that implements a full RAG pipeline:

- Document ingestion (PDF/DOCX/TXT/MD/CSV/XLSX, with OCR fallback for scanned PDFs) processed asynchronously by an ARQ worker
- Hybrid retrieval: Qdrant dense vector search + Redis-backed BM25 sparse search, combined with reciprocal rank fusion
- Cohere reranking on top of the fused candidates
- Query rewriting and answer generation via Google Gemini
- Streaming responses over Server-Sent Events, with source citations
- Guardrails for prompt-injection and harmful-content detection on both input and output
- Prometheus metrics, structured JSON logging, and a small eval harness against a golden query set

## Architecture

```
┌──────────────────────────┐
│   HTTP Client            │
│  (curl / Postman / your  │
│   own frontend, later)   │
└──────────────────────────┘
            │ HTTP / SSE
            ▼
┌──────────────────────────┐
│      FastAPI Backend     │
│   apps/backend/app/      │
│                          │
│  • Chat (query/stream)   │
│  • Documents (upload)    │
│  • Health / Debug        │
└──────────────────────────┘
            │
   ┌────────┼─────────┬───────────┐
   ▼        ▼         ▼           ▼
┌──────┐ ┌───────┐ ┌────────┐ ┌───────┐
│Qdrant│ │ Redis │ │Postgres│ │ MinIO │
│vector│ │BM25 + │ │chats / │ │ file  │
│store │ │queue  │ │docs DB │ │storage│
└──────┘ └───────┘ └────────┘ └───────┘
            ▲
            │ ARQ job queue
┌──────────────────────────┐
│   Ingestion Worker        │
│ app/workers/ingestion_    │
│ worker.py (separate       │
│ process)                  │
└──────────────────────────┘
```

## Project Structure

```
advance-chat-bot/
│
├── apps/
│   ├── backend/                       # FastAPI service — everything currently lives here
│   │   ├── app/
│   │   │   ├── main.py                # Entry point: middleware, lifespan, routers, /metrics
│   │   │   │
│   │   │   ├── api/                   # Route handlers
│   │   │   │   ├── chat.py            # /api/v1/chat: query, stream, feedback
│   │   │   │   ├── documents.py       # /api/v1/documents: upload, status, list, delete, reingest
│   │   │   │   ├── health.py          # /health: Qdrant/Redis/Postgres dependency checks
│   │   │   │   ├── debug.py           # /api/v1/debug: pipeline status, rag-stats
│   │   │   │   └── auth.py            # Stub — empty, no auth implemented yet
│   │   │   │
│   │   │   ├── services/              # Business logic
│   │   │   │   ├── vector_service.py      # Qdrant + BM25 hybrid retrieval, RRF, rerank orchestration
│   │   │   │   ├── llm_service.py         # Gemini generation + query rewriting
│   │   │   │   ├── chat_service.py        # Chat orchestration: guardrails, history, persistence
│   │   │   │   ├── Ingestion_service.py   # Parsing, chunking, embedding generation
│   │   │   │   ├── document_service.py    # Upload lifecycle, dedup, enqueues ingestion job
│   │   │   │   ├── rerank_service.py       # Cohere reranking
│   │   │   │   ├── minio_service.py        # S3-compatible object storage
│   │   │   │   └── auth_service.py         # Stub — empty
│   │   │   │
│   │   │   ├── core/                  # Config & cross-cutting concerns
│   │   │   │   ├── config.py          # Settings (env-driven)
│   │   │   │   ├── guardrails.py      # Prompt-injection / harmful-content checks
│   │   │   │   ├── security.py        # Input sanitization, token utilities
│   │   │   │   ├── logging.py         # Structured JSON logging w/ request IDs
│   │   │   │   └── metrics.py         # Prometheus counters/histograms
│   │   │   │
│   │   │   ├── db/                    # SQLAlchemy engine/session setup
│   │   │   ├── models/                # User, Document, Conversation+Message, Feedback
│   │   │   ├── repositories/          # ChatRepository, DocumentRepository
│   │   │   ├── schemas/               # Pydantic request/response models
│   │   │   ├── dependencies/          # FastAPI DI wiring for services/repos
│   │   │   ├── workers/               # ingestion_worker.py — ARQ background job
│   │   │   ├── utils/                 # Shared enums/helpers
│   │   │   └── eval/                  # evaluator.py + golden_set.json + result snapshots
│   │   │
│   │   ├── requirements.txt
│   │   └── .env.example
│   │
│   └── web/                           # Empty placeholder — no frontend exists yet
│
├── docker-compose.yml                 # Empty placeholder — not wired up yet
├── package.json                       # Empty placeholder — not wired up yet
├── pnpm-workspace.yaml                # Empty placeholder — not wired up yet
└── Readme.md
```

## Quick Start

### Prerequisites
- Python 3.10+
- PostgreSQL, Redis, Qdrant, MinIO running somewhere reachable (locally or via individual `docker run` commands — `docker-compose.yml` in this repo is currently an empty placeholder, not a working stack)
- A [Google Gemini API key](https://ai.google.dev/) — required, since generation and embeddings both go through Gemini
- A Cohere API key — optional, only needed if `USE_RERANKER=true`

### Installation

```bash
# 1. Clone and enter the backend
git clone <this-repo>
cd advance-chat-bot/apps/backend

# 2. Create venv and install dependencies
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 3. Set up environment
cp .env.example .env
# Edit .env: fill in SECRET_KEY, DATABASE_URL, REDIS_URL, QDRANT_URL, MINIO_*
# IMPORTANT: also add GEMINI_API_KEY=... manually — it's required by
# llm_service.py / Ingestion_service.py but is NOT in .env.example yet.

# 4. Start dependencies (example — adjust to your setup)
docker run -d -p 5432:5432 -e POSTGRES_USER=rag_user -e POSTGRES_PASSWORD=rag_password -e POSTGRES_DB=rag_db postgres:16
docker run -d -p 6379:6379 redis:7
docker run -d -p 6333:6333 qdrant/qdrant
docker run -d -p 9000:9000 -p 9001:9001 -e MINIO_ROOT_USER=minioadmin -e MINIO_ROOT_PASSWORD=minioadmin minio/minio server /data --console-address ":9001"

# 5. Run the API (creates DB tables + Qdrant collection on startup)
uvicorn app.main:app --reload --port 8003

# 6. In a second terminal, run the ingestion worker (required for uploads to complete)
arq app.workers.ingestion_worker.WorkerSettings
```

**Access**:
- API: http://localhost:8003
- Swagger docs: http://localhost:8003/docs
- ReDoc: http://localhost:8003/redoc
- Prometheus metrics: http://localhost:8003/metrics
- Health check: http://localhost:8003/health

## Configuration

All settings are defined in [`app/core/config.py`](apps/backend/app/core/config.py) and read from `.env`. Key groups:

| Group | Variables | Notes |
|---|---|---|
| Security | `SECRET_KEY` (required, no default) | Generate with `python -c "import secrets; print(secrets.token_urlsafe(32))"` |
| Database | `DATABASE_URL` | Defaults to local Postgres |
| Redis | `REDIS_URL`, `REDIS_TTL` | Used for caching, BM25 corpus storage, and the ARQ queue |
| Qdrant | `QDRANT_URL`, `QDRANT_API_KEY`, `QDRANT_COLLECTION`, `QDRANT_VECTOR_SIZE` | Vector size defaults to 3072 (Gemini embedding dimension) |
| LLM | `GEMINI_API_KEY` **(required, missing from `.env.example` — add manually)**, `GEMINI_MODEL`, `GEMINI_EMBEDDING_MODEL` | The only provider actually wired into `llm_service.py` / `Ingestion_service.py` |
| LLM (configured, unused) | `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` | Defined in settings but no service currently calls these providers |
| Reranking | `COHERE_API_KEY`, `COHERE_RERANK_MODEL`, `USE_RERANKER` | Reranking is skipped if no Cohere key is set |
| File storage | `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `MINIO_BUCKET`, `MINIO_SECURE` | |
| RAG tuning | `CHUNK_SIZE`, `CHUNK_OVERLAP`, `TOP_K_RETRIEVAL`, `TOP_K_RERANK`, `MAX_RERANK_CANDIDATES`, `SIMILARITY_THRESHOLD`, `DENSE_WEIGHT`, `SPARSE_WEIGHT`, `BM25_ENABLED`, `QUERY_REWRITE_ENABLED`, `CONTEXTUAL_ENRICHMENT_ENABLED` | |
| Defined but not wired up | `SEMANTIC_CACHE_ENABLED`, `SEMANTIC_CACHE_THRESHOLD`, `SEMANTIC_CACHE_TTL` | Present in settings only — no code references them outside `config.py` |

## API Reference

### Chat — `/api/v1/chat`
| Method & Path | Description |
|---|---|
| `POST /query` | Non-streaming chat query. Runs full RAG pipeline, returns answer + sources. |
| `POST /stream` | SSE streaming query. Emits `{"type":"token","content":...}`, then `{"type":"sources",...}`, then `{"type":"done","conversation_id":...}`, terminated by `data: [DONE]`. |
| `POST /{conversation_id}/feedback` | Records a 1–5 rating (+ optional comment) on a previous answer. |

### Documents — `/api/v1/documents`
| Method & Path | Description |
|---|---|
| `POST /upload` | Uploads a file, stores it in MinIO, enqueues background ingestion. Returns `202` with `status: pending`. |
| `GET /{document_id}/status` | Poll ingestion progress: `pending → queued → processing → completed/failed`. |
| `GET /list` | List recent documents (limit 20). |
| `DELETE /{document_id}` | Deletes the document and its vectors/BM25 entries. |
| `POST /{document_id}/reingest` | Re-runs ingestion with current settings (e.g. after toggling `CONTEXTUAL_ENRICHMENT_ENABLED`). |

### Health & Debug
| Method & Path | Description |
|---|---|
| `GET /health` | Checks Qdrant, Redis, and Postgres connectivity. `200` if healthy, `503` if degraded. |
| `GET /api/v1/debug/status` | Snapshot of Qdrant point count, ARQ pending job count, and the 10 most recent documents. |
| `GET /api/v1/debug/rag-stats` | Aggregate latency/quality stats over the last 100 pipeline runs. |

### Auth — `/api/v1/auth`
Routes file exists (`app/api/auth.py`) but is currently empty — no authentication is implemented. `user_id` fields on `Document`/`Conversation` are nullable and unused in practice.

## RAG Pipeline

**Ingestion** (triggered by upload, runs in `app/workers/ingestion_worker.py`):
```
Upload → MinIO storage → ARQ job enqueued
  → Parse (PyMuPDF / python-docx / openpyxl / OCR fallback for scanned PDFs)
  → Chunk (recursive splitter, configurable size + overlap)
  → Embed each chunk (Gemini embedding model)
  → Upsert vectors into Qdrant + store raw text in Redis for BM25
  → Update document status in Postgres
```

**Query** (`vector_service.py` + `chat_service.py` + `llm_service.py`):
```
User message → guardrail checks (prompt injection / harmful content)
  → load recent conversation history (last 10 messages)
  → Gemini query rewrite (expands abbreviations, decomposes multi-part questions)
  → hybrid retrieval: Qdrant dense search + Redis BM25 sparse search
  → reciprocal rank fusion of both result sets
  → Cohere rerank top candidates (if enabled)
  → Gemini generates the answer from the fused context
  → guardrail-validate the output
  → stream tokens + sources over SSE, persist messages to Postgres
```

## Tech Stack

- **Framework**: FastAPI 0.135, Uvicorn, Pydantic v2
- **Database**: PostgreSQL via SQLAlchemy 2.0 + Alembic
- **Vector store**: Qdrant (qdrant-client 1.18)
- **Cache / queue**: Redis 5.3, ARQ 0.28 for async ingestion jobs
- **Sparse search**: rank-bm25
- **LLM / embeddings**: Google Gemini (`google-genai`) — actively used; `openai`, `anthropic`, `litellm` are installed dependencies but not called by any service
- **Reranking**: Cohere (`rerank-english-v3.0`)
- **Document parsing**: PyMuPDF, pdfplumber, python-docx, openpyxl, pytesseract (OCR fallback)
- **File storage**: MinIO via boto3 (S3-compatible)
- **Observability**: prometheus-client, structured JSON logging with request-ID propagation

## Observability & Eval

- `GET /metrics` — Prometheus metrics (RAG latency histograms, chunks retrieved, feedback counts)
- Structured JSON logs with request IDs (`app/core/logging.py`)
- `GET /health` and `GET /api/v1/debug/*` for live pipeline inspection
- `app/eval/` — `evaluator.py` runs retrieval/answer quality checks against `golden_set.json`, with results snapshotted in `eval_results.json` / `retrieval_eval_results.json`

## Known Gaps

These are real, verified gaps — not a roadmap, just the current state:

- **No authentication** — `app/api/auth.py` and `app/services/auth_service.py` are empty stub files.
- **No automated tests** — there is no `tests/` directory anywhere in the repo.
- **No Dockerfile / working docker-compose** — `docker-compose.yml` at the repo root is a 0-byte placeholder; there's no containerized way to run the stack yet.
- **No frontend** — `apps/web/` is an empty directory; the root `package.json` and `pnpm-workspace.yaml` are also empty placeholders.
- **`.env.example` is incomplete** — it doesn't include `GEMINI_API_KEY`, which is required for the app to actually generate responses or embeddings.
- **Unused config/dependencies** — `SEMANTIC_CACHE_*` settings exist but aren't referenced anywhere in the code; `langgraph`/`langchain-core`/`langsmith` are installed but unused by any current service.

## Contributing

1. Fork the repo
2. Create a feature branch
3. Make your changes
4. Open a PR describing what changed and why

## License

No `LICENSE` file is currently committed to this repo.

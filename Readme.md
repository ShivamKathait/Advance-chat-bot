# 🚀 RAG Chatbot - Simple & Powerful

> Production-grade RAG system with advanced retrieval. **Clean monorepo - just Web + Backend.**

[![TypeScript](https://img.shields.io/badge/TypeScript-007ACC?logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![Python](https://img.shields.io/badge/Python-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/Next.js-000000?logo=next.js&logoColor=white)](https://nextjs.org/)

---

## ✨ What This Is

A **FAANG-level RAG chatbot** that showcases:
- ✅ Advanced retrieval (hybrid search + reranking)
- ✅ Streaming responses with citations
- ✅ Production infrastructure
- ✅ Clean, maintainable code

**Philosophy**: Start simple, scale when needed.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────┐
│         Next.js Frontend            │
│   (Streaming Chat Interface)        │
└─────────────────────────────────────┘
                ↓ HTTP/SSE
┌─────────────────────────────────────┐
│        FastAPI Backend              │
│   (Complete RAG Pipeline)           │
│                                     │
│  • Document ingestion               │
│  • Hybrid retrieval                 │
│  • Reranking                        │
│  • LLM generation                   │
│  • Caching                          │
└─────────────────────────────────────┘
                ↓
    ┌──────┬─────────┬────────┐
    ↓      ↓         ↓        ↓
┌────────┐ ┌────────┐ ┌──────┐
│Postgres│ │Qdrant  │ │Redis │
│        │ │Vector  │ │Cache │
└────────┘ └────────┘ └──────┘
```

---

## 📁 Project Structure

```
rag-chatbot/
│
├── apps/
│   ├── backend/              # FastAPI - ALL backend logic here
│   │   ├── app/
│   │   │   ├── main.py      # API entry point
│   │   │   │
│   │   │   ├── api/         # API routes
│   │   │   │   ├── chat.py
│   │   │   │   ├── documents.py
│   │   │   │   └── health.py
│   │   │   │
│   │   │   ├── services/    # Business logic
│   │   │   │   ├── rag.py           # Core RAG pipeline
│   │   │   │   ├── retrieval.py     # Hybrid search
│   │   │   │   ├── embedding.py     # Embeddings
│   │   │   │   ├── reranking.py     # Reranker
│   │   │   │   ├── llm.py           # LLM calls
│   │   │   │   ├── cache.py         # Redis caching
│   │   │   │   └── ingestion.py     # Document processing
│   │   │   │
│   │   │   ├── core/        # Config & utilities
│   │   │   │   ├── config.py
│   │   │   │   ├── logging.py
│   │   │   │   └── security.py
│   │   │   │
│   │   │   └── models/      # Database models
│   │   │       ├── document.py
│   │   │       └── conversation.py
│   │   │
│   │   ├── tests/           # Backend tests
│   │   └── requirements.txt
│   │
│   └── web/                 # Next.js - Frontend
│       ├── app/             # App router
│       │   ├── page.tsx     # Main chat page
│       │   └── layout.tsx
│       │
│       ├── components/      # React components
│       │   ├── chat/
│       │   │   ├── ChatMessage.tsx
│       │   │   ├── ChatInput.tsx
│       │   │   └── SourceCard.tsx
│       │   └── ui/          # Reusable UI
│       │
│       ├── lib/             # Utilities
│       │   ├── api.ts       # API client
│       │   └── utils.ts
│       │
│       ├── hooks/           # Custom hooks
│       │   └── useChat.ts
│       │
│       └── package.json
│
├── docker-compose.yml       # Infrastructure (3 services)
├── package.json             # Monorepo scripts
├── pnpm-workspace.yaml      # Workspace config
├── .gitignore
└── README.md
```

**Key principle**: Everything in `apps/backend/app/services/` - no separate microservices.

---

## 🚀 Quick Start

### Prerequisites
- Node.js 18+
- Python 3.11+
- Docker Desktop
- pnpm 8+

### Installation

```bash
# 1. Clone repository
git clone <your-repo>
cd rag-chatbot

# 2. Install frontend dependencies
pnpm install

# 3. Install backend dependencies
cd apps/backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cd ../..

# 4. Set up environment
cp apps/backend/.env.example apps/backend/.env
# Edit apps/backend/.env with your OPENAI_API_KEY

# 5. Start infrastructure
pnpm docker:up

# 6. Start development servers
pnpm dev
```

**Access**:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

---

## 🔧 Configuration

### Backend Environment (`apps/backend/.env`)

```env
# Required
OPENAI_API_KEY=sk-...

# Optional but recommended
COHERE_API_KEY=...          # For reranking

# Database URLs (defaults work with docker-compose)
DATABASE_URL=postgresql://rag_user:rag_password@localhost:5432/rag_db
REDIS_URL=redis://localhost:6379
QDRANT_URL=http://localhost:6333

# RAG Settings
TOP_K_RETRIEVAL=10
CHUNK_SIZE=1000
CHUNK_OVERLAP=200
```

### Frontend Environment (`apps/web/.env.local`)

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## 💻 Development

### Daily Workflow

```bash
# Start infrastructure
pnpm docker:up

# Start dev servers (both frontend & backend)
pnpm dev

# Or run separately:
pnpm dev:web     # Frontend only
pnpm dev:api     # Backend only

# View logs
pnpm docker:logs

# Stop everything
pnpm docker:down
```

### Adding Features

**Backend changes** (`apps/backend/app/`):
```python
# Add new service in services/
# Add new route in api/
# Changes hot-reload automatically
```

**Frontend changes** (`apps/web/`):
```typescript
// Add components in components/
// Add pages in app/
// Changes hot-reload automatically
```

---

## 🧪 Testing

```bash
# Backend tests
cd apps/backend
pytest tests/ -v --cov

# Frontend tests
cd apps/web
pnpm test

# Lint
pnpm lint
```

---

## 📚 Tech Stack

### Frontend
- **Framework**: Next.js 14 (App Router)
- **Language**: TypeScript
- **Styling**: Tailwind CSS
- **State**: Zustand
- **HTTP**: Fetch API with SSE

### Backend
- **Framework**: FastAPI
- **Language**: Python 3.11+
- **Async**: asyncio + uvicorn
- **Validation**: Pydantic v2
- **ORM**: SQLAlchemy

### AI/ML
- **LLM**: OpenAI GPT-4 / Claude
- **Embeddings**: text-embedding-3-large
- **Vector DB**: Qdrant
- **Cache**: Redis
- **Reranking**: Cohere (optional)

### Infrastructure
- **Containers**: Docker + Docker Compose
- **Database**: PostgreSQL + pgvector
- **Cache**: Redis
- **Vector Store**: Qdrant

---

## 🎯 Core Features

### RAG Pipeline

```python
# apps/backend/app/services/rag.py

1. Document Upload
   → Parse (PDF, DOCX, TXT)
   → Chunk (recursive + semantic)
   → Embed (OpenAI)
   → Store (Qdrant)

2. Query Processing
   → Preprocess query
   → Hybrid retrieval (vector + keyword)
   → Rerank top results
   → Generate with LLM
   → Stream response

3. Response
   → Streaming tokens
   → Source citations
   → Conversation memory
```

### Advanced Retrieval

```python
# Hybrid Search
dense_results = await vector_search(query)  # Semantic
sparse_results = await keyword_search(query) # BM25
fused = reciprocal_rank_fusion([dense, sparse])

# Reranking
reranked = await reranker.rerank(query, fused, top_k=5)
```

### Streaming Chat

```typescript
// apps/web/lib/api.ts

// Server-Sent Events (SSE)
const stream = await fetch('/api/chat/stream', {
  method: 'POST',
  body: JSON.stringify({ message })
});

// Parse SSE and update UI token-by-token
for await (const chunk of stream) {
  updateMessage(chunk);
}
```

---

## 🗺️ Roadmap

### ✅ Week 1-2: MVP (CURRENT)
- [x] Monorepo setup
- [x] Docker infrastructure
- [x] Basic RAG pipeline
- [ ] Document upload
- [ ] Vector storage
- [ ] Simple chat interface

### 🔄 Week 3-4: Advanced Retrieval
- [ ] Hybrid search (dense + sparse)
- [ ] Reranking with Cohere
- [ ] Semantic caching
- [ ] Query enhancement
- [ ] Citation generation

### 📋 Week 5-6: Polish
- [ ] Streaming UI
- [ ] Conversation history
- [ ] Source panel
- [ ] Error handling
- [ ] Performance optimization

### 🚀 Week 7+: Advanced Features
- [ ] Agentic RAG
- [ ] Query decomposition
- [ ] GraphRAG
- [ ] Evaluation framework
- [ ] Monitoring

---

## 🎓 Learning Path

### Start Here
1. `apps/backend/app/main.py` - Entry point
2. `apps/backend/app/services/rag.py` - Core logic
3. `apps/web/app/page.tsx` - Chat UI
4. `apps/web/lib/api.ts` - API client

### Key Concepts
- **Embeddings**: Convert text to vectors
- **Semantic Search**: Find similar vectors
- **Chunking**: Split documents intelligently
- **Reranking**: Improve retrieval precision
- **Streaming**: Real-time response delivery

### Resources
- [RAG Paper](https://arxiv.org/abs/2005.11401)
- [FastAPI Docs](https://fastapi.tiangolo.com/)
- [Next.js Docs](https://nextjs.org/docs)
- [Qdrant Docs](https://qdrant.tech/documentation/)

---

## 🐛 Troubleshooting

### Docker containers won't start
```bash
# Check ports
lsof -i :5432 :6333 :6379

# Restart
pnpm docker:down
docker system prune -f
pnpm docker:up
```

### Backend won't connect to databases
```bash
# Verify services
docker-compose ps

# Check logs
docker-compose logs postgres
docker-compose logs qdrant
docker-compose logs redis
```

### Frontend shows CORS error
```bash
# Check CORS_ORIGINS in apps/backend/app/core/config.py
# Should include: http://localhost:3000
```

---

## 📊 Performance Targets

| Metric | Target |
|--------|--------|
| Query Latency (p95) | <2s |
| Cache Hit Rate | >60% |
| Retrieval Recall@5 | >85% |
| Cost per Query | <$0.05 |

---

## 🤝 Contributing

1. Fork the repo
2. Create feature branch
3. Make changes
4. Add tests
5. Submit PR

---

## 📄 License

MIT License - see LICENSE file

---

## 🙏 Acknowledgments

Built with:
- [FastAPI](https://fastapi.tiangolo.com/)
- [Next.js](https://nextjs.org/)
- [Qdrant](https://qdrant.tech/)
- [OpenAI](https://openai.com/)

---

## 📧 Contact

**Your Name** - [your.email@example.com]

Portfolio: https://yourportfolio.com
GitHub: https://github.com/yourusername
LinkedIn: https://linkedin.com/in/yourprofile

---

**⭐ Star this repo if it helps you!**

Built with 💜 for learning advanced RAG systems
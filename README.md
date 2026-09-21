# ScribeQL

Natural-language-to-SQL platform with **RAG**, **PostgreSQL + pgvector**, a safety-first SQL pipeline, and measurable evaluation.

## Architecture & Specifications

Documentation is located in `docs/`:
- [`docs/architecture.md`](docs/architecture.md) — System design, components, pipeline, security boundaries.
- [`docs/api.md`](docs/api.md) — API contract, endpoints, error shapes, rate limits.
- [`docs/ui.md`](docs/ui.md) — Screen map, state behaviors, client rendering rules.
- [`docs/plan.md`](docs/plan.md) — Phased implementation roadmap.

---

## Local Development Setup

### 1. Prerequisites

- Python 3.12+ (or 3.14)
- Node.js 20+ & npm
- PostgreSQL with `pgvector` extension

### 2. Backend Setup

```bash
cd backend
python -m pip install -e .
# Or run with uvicorn directly
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 3. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

The frontend will run on `http://localhost:5173` and communicate with the backend on `http://localhost:8000`.

### 4. Gemini (SQL generation + embeddings)

Copy `.env.example` and set a Google AI Studio Gemini API key. Defaults:

- `LLM_PROVIDER=gemini`
- `LLM_MODEL=gemini-2.5-flash`
- `EMBEDDING_MODEL=gemini-embedding-001`
- `EMBEDDING_DIMENSION=1536` (must match `app.rag_documents.embedding vector(1536)`)

Do not commit real keys. Index the RAG corpus after embeddings are configured:

```bash
python scripts/build_rag_index.py
```

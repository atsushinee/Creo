# Creo

> A modern workspace for AI agents.
>
> *Creo* comes from Latin **creō** — to create, to bring forth, to make something come into being.

English | [中文文档](README_zh.md)

Creo is in its **MVP stage**: the goal is not feature count, but a stable, clear and extensible agent foundation. Future capabilities (Knowledge / RAG / MCP / Multi-Agent / Workflow) evolve on top of this base.

## Core Flow

```text
User
  ↓
React Agent UI
  ↓
SSE / HTTP
  ↓
FastAPI
  ↓
DeepAgents
  ↓
LLM
  ↓
Tools
  ↓
Result
```

## Features

- Streaming chat with a DeepAgents-backed agent (SSE, token-level streaming)
- Session management, tool call visualization (running / success / error)
- Markdown rendering with code blocks, light / dark theme
- **Knowledge base (v1)**: create categorized knowledge bases, upload PDFs, and let the agent retrieve them with **hybrid search — dense vectors (bge-m3) + sparse BM25** served by Milvus / Zilliz Cloud

## Tech Stack

| Layer | Technology |
| --- | --- |
| Frontend | React 19 · TypeScript (strict) · Vite · React Router · Tailwind CSS · shadcn-style components · lucide-react · pnpm |
| Backend | Python 3.12+ · FastAPI · DeepAgents · Pydantic · SSE · uv |
| Knowledge base | Unstructured (self-hosted parsing API) · Milvus / Zilliz Cloud (server-side BM25 + dense vectors, `pymilvus`) · OpenAI-compatible embeddings |
| Protocol | Creo Agent Event Protocol (custom event protocol; the frontend never touches DeepAgents internals) |

## Directory Structure

```text
creo/
├── README.md            # This file
├── README_zh.md         # Chinese documentation
├── AGENTS.md            # Development rules (required reading for humans & AI agents)
├── DESIGN.md            # UI design system
├── CONTRIBUTING.md      # Development process & commit rules
├── docs/
│   ├── architecture.md  # Architecture guide
│   ├── decisions/       # ADRs (architecture decision records)
│   ├── development/     # CHANGELOG / TECHNICAL-NOTES / PITFALLS
│   └── milestones/      # MVP acceptance criteria & status
├── frontend/            # React agent UI
└── backend/             # FastAPI + DeepAgents runtime
```

## Quick Start

### Prerequisites

- Node.js ≥ 20.19 (22 recommended) + **pnpm 12** (`corepack enable` or `npm i -g pnpm`)
- Python ≥ 3.12 and [uv](https://docs.astral.sh/uv/)
- One LLM API key (any provider; OpenAI-compatible endpoints are supported via a custom base_url)
- For the knowledge base (optional): a [Zilliz Cloud](https://zilliz.com/cloud) cluster or self-hosted Milvus ≥ 2.5, a self-hosted [Unstructured](https://github.com/Unstructured-IO/unstructured-api) API, and an embedding API key (e.g. `BAAI/bge-m3` on SiliconFlow)

### 1. Backend

```bash
cd backend
cp .env.example .env          # fill in your model / API keys (see below)
uv sync
uv run uvicorn app.main:app --reload --port 8000
```

Health check: <http://localhost:8000/api/health> (the `model` field shows the active config); API docs: <http://localhost:8000/docs>

### 2. Configure the LLM

Everything lives in `backend/.env`. Provider / model / base_url / api_key are all customizable — any OpenAI-compatible service works (DeepSeek, Qwen, Moonshot, Ollama, vLLM…):

```ini
CREO_MODEL_PROVIDER=openai
CREO_MODEL_NAME=gpt-4o-mini
OPENAI_API_KEY=sk-...

# Example: DeepSeek — OpenAI-compatible services only need NAME / BASE_URL / API_KEY
# CREO_MODEL_NAME=deepseek-chat
# CREO_MODEL_BASE_URL=https://api.deepseek.com/v1
# CREO_MODEL_API_KEY=sk-...
```

### 3. Frontend

```bash
cd frontend
pnpm install
pnpm run dev
```

Open <http://localhost:5173> (in dev mode `/api` is proxied by Vite to the backend on port 8000).

### Docker (optional)

```bash
# Prepare .env at the repo root (model / key config is injected into the backend by compose)
docker compose up --build
```

Open <http://localhost:5173>.

## Knowledge Base Setup (Optional)

The knowledge base ships **disabled**. Set `CREO_KB_ENABLED=true` and fill in the three endpoints below; if anything is missing — or Milvus cannot be reached at startup — the KB stays disabled (endpoints return `503`, the retrieval tool is not registered) and the chat flow is unaffected.

### 1. Milvus / Zilliz Cloud (vectors + full-text)

```ini
CREO_MILVUS_URI=https://in03-xxxx.api-us-west-1.zillizcloud.com   # cluster endpoint
CREO_MILVUS_TOKEN=                                                # Zilliz Cloud API key
# Self-hosted Milvus instead: CREO_MILVUS_URI=http://localhost:19530
```

- Zilliz Cloud: create a Dedicated cluster, copy the endpoint from the cluster page and an API key from the API Keys page. Server-side BM25 requires Milvus ≥ 2.5 (all current Zilliz Cloud clusters qualify).
- Each knowledge base gets its own collection (`kb_{slug}_{id}`); collections are created lazily on first ingest.

### 2. Unstructured (PDF parsing, self-hosted)

```ini
CREO_UNSTRUCTURED_API_URL=http://localhost:8000
# CREO_UNSTRUCTURED_API_KEY=       # only if the service sets UNSTRUCTURED_API_KEY
```

Run the service locally (the full image includes the `hi_res` layout model + OCR):

```bash
docker run -p 8000:8000 -d --rm quay.io/unstructuredio/unstructured-api:latest
```

Defaults used by Creo: `strategy=hi_res` (handles scanned PDFs), `chunking_strategy=by_title`, `max_characters=1500`, OCR languages `chi_sim,eng`. Tune via `CREO_UNSTRUCTURED_STRATEGY` / `CREO_UNSTRUCTURED_LANGUAGES`.

### 3. Embeddings (dense channel)

```ini
CREO_KB_EMBEDDING_BASE_URL=https://api.siliconflow.cn/v1   # any OpenAI-compatible /embeddings
CREO_KB_EMBEDDING_API_KEY=
CREO_KB_EMBEDDING_MODEL=BAAI/bge-m3
CREO_KB_EMBEDDING_DIM=1024
```

### 4. Use It

1. Open the **Knowledge** page (top navigation) → create a knowledge base (this is the "category"; each KB = a local folder + one Milvus collection).
2. Upload PDFs — parsing, chunking and indexing run in the background; rows poll from `pending → processing → ready / failed`, failed documents can be re-ingested with one click.
3. In **Chat**, ask about your documents — the agent calls `search_knowledge_base` (hybrid BM25 + dense retrieval, RRF fusion) and cites `[1] filename (page N)` sources. Retrieval calls show up as regular tool cards in the UI.

### Knowledge Base Notes

- The embedding model, dimension and the Chinese analyzer (`CREO_KB_ANALYZER=chinese`, jieba-based) are **fixed when a collection is created**. Changing them means dropping the KB and re-ingesting.
- Uploaded files and the SQLite registry live under `backend/data/kb/` (git-ignored).
- If the backend restarts mid-ingestion, documents may stay in `processing` — use the retry button to re-ingest (idempotent: old vectors are deleted first).

## Configuration Reference

All variables use the `CREO_` prefix and are set in `backend/.env` (see `.env.example` for the annotated list).

| Variable | Default | Description |
| --- | --- | --- |
| `CREO_MODEL_PROVIDER` | `openai` | Any provider known to `init_chat_model` |
| `CREO_MODEL_NAME` | `gpt-4o-mini` | Model name |
| `CREO_MODEL_API_KEY` | — | Optional; falls back to provider-native env keys |
| `CREO_MODEL_BASE_URL` | — | Optional; for OpenAI-compatible endpoints |
| `CREO_AGENT_INSTRUCTIONS` | built-in | Agent system prompt |
| `CREO_CORS_ORIGINS` | localhost:5173 | Comma-separated allowed origins |
| `CREO_LOG_LEVEL` | `INFO` | stdlib logging level |
| `CREO_KB_ENABLED` | `false` | Master switch for the knowledge base |
| `CREO_MILVUS_URI` | — | Zilliz Cloud endpoint or `http://host:19530` |
| `CREO_MILVUS_TOKEN` | — | Zilliz Cloud API key (empty for unauthenticated self-hosting) |
| `CREO_UNSTRUCTURED_API_URL` | — | Self-hosted Unstructured base URL |
| `CREO_UNSTRUCTURED_API_KEY` | — | Only if the service requires one |
| `CREO_UNSTRUCTURED_STRATEGY` | `hi_res` | `auto` \| `fast` \| `hi_res` \| `ocr_only` |
| `CREO_UNSTRUCTURED_LANGUAGES` | `chi_sim,eng` | OCR languages (Tesseract codes) |
| `CREO_UNSTRUCTURED_TIMEOUT` | `600` | Seconds; hi_res is slow on large PDFs |
| `CREO_KB_EMBEDDING_BASE_URL` | — | OpenAI-compatible `/embeddings` base URL |
| `CREO_KB_EMBEDDING_API_KEY` | — | Bearer token |
| `CREO_KB_EMBEDDING_MODEL` | `BAAI/bge-m3` | Embedding model |
| `CREO_KB_EMBEDDING_DIM` | `1024` | Vector dimension (must match the model) |
| `CREO_KB_ANALYZER` | `chinese` | BM25 analyzer; `chinese`/`english`/`standard` or a JSON analyzer_params |
| `CREO_KB_CHUNK_MAX_CHARACTERS` | `1500` | Max characters per chunk (by_title) |
| `CREO_KB_DATA_DIR` | `backend/data/kb` | Uploads + SQLite registry |
| `CREO_KB_UPLOAD_MAX_MB` | `50` | Per-file upload limit |
| `CREO_KB_SEARCH_TOP_K` | `5` | Default top_k for the retrieval tool |

## Documentation Index

| Document | Content |
| --- | --- |
| [AGENTS.md](AGENTS.md) | Development rules: architecture boundaries, forbidden patterns, commit discipline |
| [DESIGN.md](DESIGN.md) | Creo design language: color, typography, components |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Development process, Conventional Commits, pre-commit checklist |
| [docs/architecture.md](docs/architecture.md) | System architecture & module responsibilities |
| [docs/decisions/](docs/decisions/) | ADRs: project architecture, Agent Event Protocol, SSE streaming, knowledge base |
| [docs/development/CHANGELOG.md](docs/development/CHANGELOG.md) | User-perceivable changes |
| [docs/development/TECHNICAL-NOTES.md](docs/development/TECHNICAL-NOTES.md) | Technical implementation details & rationale |
| [docs/development/PITFALLS.md](docs/development/PITFALLS.md) | Pitfall records |
| [docs/milestones/MVP.md](docs/milestones/MVP.md) | MVP acceptance criteria |

## Current Status

Implemented: React agent UI, DeepAgents backend, SSE streaming, agent sessions, tool call visualization, Markdown / code blocks, light / dark theme, basic error handling, logging, tests, complete governance docs — and **knowledge base v1** (PDF upload → Unstructured parsing → BM25 + dense hybrid indexing in Milvus/Zilliz → agent retrieval tool).

Not implemented (boundary reserved): deep-RAG (multi-format parsing, rerank, GraphRAG), MCP, Multi-Agent, Workflow, long-term memory, authentication.

## License

TBD; all rights reserved during the MVP stage.

<div align="center">

# Semantic Video Search Engine

**Ask natural-language questions about your video library. Get timestamped, cited answers.**

[![CI](https://github.com/singhrobin123/semantic-video-search/actions/workflows/ci.yml/badge.svg)](https://github.com/singhrobin123/semantic-video-search/actions)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-36%20passing-brightgreen.svg)](#testing)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

</div>

<br/>

<div align="center">

| Ingest a YouTube video | Ask a question | Get timestamped citations |
|:---:|:---:|:---:|
| Paste URL → auto-extract transcript → chunk → embed → store | LangGraph agent autonomously searches your library | Answer + exact quotes with seek-to-moment timestamps |

</div>

<br/>

> **How is this different from a basic RAG demo?**
> The LLM agent controls its own execution flow. It decides which tools to call, in what order, and when to stop — using a cyclic state machine, not a linear chain. It can examine multiple clips, skip irrelevant ones, and backtrack when needed.

---

## Table of Contents

- [System Architecture](#system-architecture)
- [How It Works](#how-it-works)
  - [Agentic Search](#1-agentic-search)
  - [Ingestion Pipeline](#2-ingestion-pipeline)
  - [Request Lifecycle](#3-request-lifecycle)
- [Data Model](#data-model)
- [Error Handling](#error-handling)
- [Quick Start](#quick-start)
- [API Reference](#api-reference)
- [Project Structure](#project-structure)
- [Testing](#testing)
- [Configuration](#configuration)
- [Technical Decisions](#technical-decisions)

---

## System Architecture

```mermaid
graph TB
    subgraph Frontend["Streamlit Frontend :8501"]
        FE_Chat["Chat UI<br/><small>conversation history</small>"]
        FE_Ingest["YouTube Ingestion<br/><small>sidebar</small>"]
        FE_Lib["Library Manager<br/><small>sidebar</small>"]
        FE_Player["Video Player<br/><small>embedded YT with seek</small>"]
    end

    subgraph Backend["FastAPI Backend :8000"]
        subgraph Middleware["Middleware"]
            MW_CORS["CORS"]
            MW_Trace["Request Tracing<br/><small>X-Request-ID + latency</small>"]
        end

        subgraph Routes["API Routes"]
            R_Search["POST /search"]
            R_Ingest["POST /ingest/youtube"]
            R_Manual["POST /ingest/manual"]
            R_Lib["GET /library"]
            R_Del["DELETE /library/:id"]
            R_Health["GET /health"]
        end

        subgraph Agent["LangGraph Agent"]
            AG_Reason["agent_reason<br/><small>LLM decides next action</small>"]
            AG_Route{"should_continue?"}
            AG_Tools["tool_execute<br/><small>run selected tool</small>"]
            AG_Respond["respond<br/><small>parse final JSON</small>"]

            AG_Reason --> AG_Route
            AG_Route -->|"tool calls"| AG_Tools
            AG_Route -->|"no tool calls"| AG_Respond
            AG_Tools -->|"loop back"| AG_Reason
        end

        subgraph Ingestion["Ingestion Pipeline"]
            I_Trans["Transcriber<br/><small>youtube-transcript-api</small>"]
            I_Chunk["Chunker<br/><small>sentence-aware sliding window</small>"]
            I_Embed["Embedder<br/><small>OpenAI batch embedding</small>"]
        end

        subgraph Tools["Agent Tools"]
            T1["get_initial_candidates<br/><small>broad KNN sweep</small>"]
            T2["examine_clip_deeper<br/><small>scoped clip search</small>"]
            T3["get_clip_quotes<br/><small>timestamped citations</small>"]
        end

        subgraph Data["Repository Layer"]
            Repo["repository.py<br/><small>only module that speaks SQL</small>"]
        end

        subgraph LLM["LLM Provider"]
            Provider["provider.py<br/><small>OpenAI / Anthropic<br/>switchable via env var</small>"]
        end
    end

    subgraph DB["PostgreSQL + pgvector :5432"]
        Clips["video_clips"]
        Chunks["transcript_chunks<br/><small>+ HNSW vector index</small>"]
        Clips -->|"1:N"| Chunks
    end

    Frontend -->|"HTTP / JSON<br/>APIEnvelope"| Routes
    R_Search --> Agent
    R_Ingest --> Ingestion
    Agent --> Tools
    Tools --> Repo
    Tools --> Provider
    Ingestion --> Repo
    Ingestion --> Provider
    Repo --> DB

    style Frontend fill:#e8f4fd,stroke:#4a90d9
    style Backend fill:#f5f5f5,stroke:#999
    style Agent fill:#fff3e0,stroke:#ff9800
    style Ingestion fill:#e8f5e9,stroke:#4caf50
    style DB fill:#fce4ec,stroke:#e91e63
    style Tools fill:#fff8e1,stroke:#ffc107
    style LLM fill:#f3e5f5,stroke:#9c27b0
```

---

## How It Works

### 1. Agentic Search

When you ask a question, the LangGraph agent runs a **cyclic loop** — reason → call tool → observe → repeat until done.

```mermaid
sequenceDiagram
    participant U as User
    participant FE as Streamlit
    participant API as FastAPI
    participant AG as LangGraph Agent
    participant LLM as GPT-4o-mini
    participant DB as pgvector
    participant EMB as Embeddings API

    U->>FE: "How did they handle database scaling?"
    FE->>API: POST /api/v1/search

    rect rgb(239, 246, 255)
        Note over AG,LLM: Step 1 — Broad search
        AG->>LLM: What tool should I use?
        LLM-->>AG: get_initial_candidates(question)
        AG->>EMB: Embed question → 1536-dim vector
        AG->>DB: KNN cosine search (top 20 across all clips)
        DB-->>AG: Candidate chunks grouped by clip
    end

    rect rgb(239, 255, 239)
        Note over AG,LLM: Step 2 — Deep dive into best clip
        AG->>LLM: Here are the candidates. What next?
        LLM-->>AG: examine_clip_deeper("demo-incident-review")
        AG->>DB: Scoped KNN within this clip (top 10)
        DB-->>AG: Most relevant moments
        Note over AG: Cache result in memory
    end

    rect rgb(255, 245, 235)
        Note over AG,LLM: Step 3 — Get citations
        AG->>LLM: I have context. What next?
        LLM-->>AG: get_clip_quotes("demo-incident-review")
        Note over AG: Read from cache — zero DB calls
        AG-->>AG: Chronological timestamped quotes
    end

    rect rgb(245, 240, 255)
        Note over AG,LLM: Step 4 — Formulate answer
        AG->>LLM: All evidence gathered. Produce final answer.
        LLM-->>AG: Structured JSON (answer + quotes + follow-ups)
        Note over AG: should_continue() → no tool calls → respond
        AG->>AG: Parse into SearchResponse schema
    end

    AG-->>API: {results: [{clip_id, answer, quotes, related_questions}]}
    API-->>FE: APIEnvelope {success: true, data: ...}
    FE-->>U: Answer + cited quotes + video player + follow-up buttons
```

**What makes this different from basic RAG:**

- The agent **chose** to examine only one clip. With multiple relevant clips, it would loop back and examine each one.
- The **clip cache** between steps 2 and 3 eliminates a redundant DB round-trip.
- A **hard cap of 8 iterations** prevents runaway loops and unbounded LLM cost.
- If the LLM returns **malformed JSON**, the respond node wraps raw text in the expected schema instead of crashing.

---

### 2. Ingestion Pipeline

Four independent stages, each testable in isolation:

```mermaid
flowchart LR
    URL["YouTube URL"] --> Extract
    
    subgraph Extract["1. Transcriber"]
        YT["youtube-transcript-api<br/><small>no API key needed</small>"]
        Meta["yt-dlp metadata<br/><small>optional, graceful fallback</small>"]
    end
    
    subgraph Chunk["2. Chunker"]
        SW["Sentence-aware<br/>sliding window<br/><small>max 1500 chars<br/>200 char overlap</small>"]
    end
    
    subgraph Embed["3. Embedder"]
        OAI["OpenAI API<br/><small>text-embedding-3-small<br/>batches of 512</small>"]
    end
    
    subgraph Store["4. Repository"]
        PG["pgvector<br/><small>upsert clip + bulk insert chunks<br/>idempotent re-ingestion</small>"]
    end
    
    Extract --> Chunk --> Embed --> Store

    style Extract fill:#e3f2fd,stroke:#1976d2
    style Chunk fill:#e8f5e9,stroke:#388e3c
    style Embed fill:#fff3e0,stroke:#f57c00
    style Store fill:#fce4ec,stroke:#c62828
```

```mermaid
sequenceDiagram
    participant U as User
    participant FE as Streamlit
    participant API as FastAPI
    participant TR as Transcriber
    participant CH as Chunker
    participant EM as Embedder
    participant DB as pgvector

    U->>FE: Paste YouTube URL
    FE->>API: POST /ingest/youtube {url}
    
    API->>TR: fetch_youtube_transcript(url)
    TR->>TR: extract_youtube_id() via regex
    TR-->>API: segments[] + metadata
    
    API->>CH: chunk_transcript(segments)
    Note over CH: Sliding window preserves<br/>sentence boundaries + timestamps
    CH-->>API: TranscriptChunkDTO[]
    
    API->>EM: embed_chunks(chunks)
    loop Every 512 chunks
        EM->>EM: OpenAI embed_documents(batch)
    end
    EM-->>API: vectors[] (1:1 with chunks)
    
    API->>DB: upsert_clip + bulk_insert_chunks
    DB-->>API: Committed
    
    API-->>FE: {clip_id, title, chunks_stored: 47}
    FE-->>U: "Ingested 'Video Title' — 47 chunks stored"
```

**Design choices:**
- **Idempotent** — Same URL twice → updates metadata, replaces chunks, no duplicates
- **Graceful** — yt-dlp metadata is optional; pipeline continues with placeholder title if it fails
- **Batched** — Embeddings processed in groups of 512 to stay within rate limits

---

### 3. Request Lifecycle

Every request passes through the same middleware stack regardless of endpoint:

```mermaid
flowchart TD
    Req["Incoming HTTP Request"] --> CORS
    
    CORS["CORS Middleware<br/><small>validate origin</small>"] --> Trace
    
    Trace["Request Tracing Middleware<br/><small>generate X-Request-ID<br/>start timer<br/>bind to structlog context</small>"] --> Handler
    
    Handler["Route Handler"] --> Logic["Business Logic"]
    
    Logic --> Success{"Outcome?"}
    
    Success -->|"OK"| S200["200<br/>APIEnvelope(success=true, data=result)"]
    Success -->|"ValueError"| S400["400<br/>APIEnvelope(success=false, error=message)"]
    Success -->|"Exception"| Log["Log full traceback<br/><small>logger.exception()</small>"]
    Log --> S500["500<br/>APIEnvelope(success=false, error='safe message')"]
    
    S200 --> Finalize
    S400 --> Finalize
    S500 --> Finalize
    
    Finalize["Stop timer<br/>Log status + elapsed_ms<br/>Set X-Request-ID header<br/>Set X-Response-Time-Ms header"] --> Resp["Response to Client"]

    style Trace fill:#e8f5e9,stroke:#388e3c
    style Log fill:#ffebee,stroke:#c62828
    style S200 fill:#e8f5e9,stroke:#388e3c
    style S400 fill:#fff3e0,stroke:#f57c00
    style S500 fill:#ffebee,stroke:#c62828
```

Every log line within a request carries the same `request_id`. You can grep for it to trace an entire search — agent tool calls, DB queries, LLM invocations — in one shot.

---

## Data Model

```mermaid
erDiagram
    VIDEO_CLIPS ||--o{ TRANSCRIPT_CHUNKS : "has many (cascade delete)"
    VIDEO_CLIPS {
        string id PK "e.g. yt-dQw4w9WgXcQ"
        string title "max 512 chars"
        text description
        string source_url "YouTube URL"
        int duration_seconds
        string channel_name
        string language "default: en"
        datetime ingested_at "auto"
    }
    TRANSCRIPT_CHUNKS {
        int id PK "auto-increment"
        string clip_id FK "video_clips.id"
        text segment_text "transcript content"
        float start_time "seconds into video"
        float end_time
        int chunk_index "order within clip"
        vector_1536 embedding "HNSW indexed"
        datetime created_at "auto"
    }
```

### Vector Search

```mermaid
flowchart LR
    Q["User Question"] -->|embed| V["1536-dim vector"]
    V -->|cosine distance| H["HNSW Index ⚡"]
    H -->|top-K| R["Ranked Chunks"]
    R -->|group by clip| C["Candidate Clips"]

    style H fill:#f9f,stroke:#333,stroke-width:2px
```

| Parameter | Value | Notes |
|-----------|-------|-------|
| Embedding model | `text-embedding-3-small` | 1536 dimensions |
| Index type | HNSW | Hierarchical Navigable Small World graph |
| `m` | 16 | Connections per node |
| `ef_construction` | 64 | Build-time search depth |
| Distance | `vector_cosine_ops` | pgvector `<=>` operator |

HNSW gives sub-millisecond approximate nearest neighbor queries at millions of vectors, trading a small amount of recall for massive speed gains over exact search.

---

## Error Handling

Six layers, each with a specific strategy. No raw tracebacks ever reach the client.

```mermaid
flowchart TD
    subgraph L1["Layer 1 — Input Validation"]
        P["Pydantic schemas<br/><small>strip whitespace, min/max length<br/>→ auto 422 on bad input</small>"]
    end
    
    subgraph L2["Layer 2 — Route Handlers"]
        V["ValueError → 400<br/><small>client error, meaningful message</small>"]
        E["Exception → 500<br/><small>log traceback, return safe message</small>"]
    end
    
    subgraph L3["Layer 3 — Agent Tools"]
        T["Per-tool try/except<br/><small>failing tool returns error as ToolMessage<br/>LLM can recover and try another approach</small>"]
    end
    
    subgraph L4["Layer 4 — Response Parsing"]
        J["JSON parse failure → fallback<br/><small>wrap raw LLM text in expected schema<br/>graceful degradation, not a crash</small>"]
    end
    
    subgraph L5["Layer 5 — External Services"]
        YT["yt-dlp fails → placeholder metadata<br/><small>pipeline continues without title/channel</small>"]
    end
    
    subgraph L6["Layer 6 — Frontend"]
        FE["Centralized api_call()<br/><small>connection error → helpful message<br/>HTTP error → extract from envelope</small>"]
    end

    L1 --> L2 --> L3 --> L4 --> L5 --> L6

    style L1 fill:#e8eaf6,stroke:#3f51b5
    style L2 fill:#e3f2fd,stroke:#1976d2
    style L3 fill:#e0f7fa,stroke:#00838f
    style L4 fill:#e8f5e9,stroke:#2e7d32
    style L5 fill:#fff8e1,stroke:#f9a825
    style L6 fill:#fce4ec,stroke:#c62828
```

<details>
<summary><strong>Code examples for each layer</strong></summary>

**Layer 1 — Pydantic strips whitespace before checking min_length:**
```python
class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)

    @field_validator("query", mode="before")
    def strip_query(cls, v):
        return v.strip() if isinstance(v, str) else v
```

**Layer 2 — Route handler classifies errors:**
```python
try:
    result = await business_logic()
    return APIEnvelope(success=True, data=result)
except ValueError as exc:
    return JSONResponse(status_code=400,
        content=APIEnvelope(success=False, error=str(exc)).model_dump())
except Exception:
    logger.exception("operation_failed")
    return JSONResponse(status_code=500,
        content=APIEnvelope(success=False, error="Internal error").model_dump())
```

**Layer 3 — Each agent tool is individually wrapped:**
```python
try:
    result_str = await handler(**fn_args)
except Exception as exc:
    logger.exception("tool_execution_error", tool=fn_name)
    result_str = json.dumps({"error": str(exc)})
```

**Layer 4 — Bad LLM JSON gets wrapped in expected schema:**
```python
try:
    parsed = json.loads(content)
    response = SearchResponse(**parsed)
except (json.JSONDecodeError, Exception):
    result = {"results": [{"answer": content[:600], ...}]}
```

**Layer 5 — Metadata extraction is optional:**
```python
except ImportError:
    return {"title": f"YouTube Video {video_id}", ...}
```

**Layer 6 — Frontend handles disconnections:**
```python
except requests.exceptions.ConnectionError:
    st.error("Cannot reach backend. Is FastAPI running on port 8000?")
```

</details>

---

## Quick Start

### Prerequisites

- **Docker** — for PostgreSQL + pgvector
- **Python 3.12+**
- **OpenAI API Key** — [get one here](https://platform.openai.com/api-keys)

### Option A: Full Docker Stack

```bash
git clone git@github.com:singhrobin123/semantic-video-search.git
cd semantic-video-search
cp .env.example .env
# Set your OPENAI_API_KEY in .env

make up   # Builds and starts pgvector + backend + frontend
```

Open **http://localhost:8501**

### Option B: Local Development

```bash
git clone git@github.com:singhrobin123/semantic-video-search.git
cd semantic-video-search
cp .env.example .env
# Set your OPENAI_API_KEY in .env

# 1. Database
make db                         # Starts pgvector in Docker

# 2. Backend
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m app.db.seed           # Seeds 3 demo clips (28 chunks, ~$0.001)
uvicorn app.main:app --reload --port 8000

# 3. Frontend (new terminal)
cd frontend
pip install streamlit requests
streamlit run app.py --server.port 8501
```

### Verify

```bash
# Health
curl http://localhost:8000/health

# Library
curl -s http://localhost:8000/api/v1/library | python3 -m json.tool

# Search
curl -s -X POST http://localhost:8000/api/v1/search \
  -H "Content-Type: application/json" \
  -d '{"query": "How did they handle database scaling?"}' | python3 -m json.tool
```

---

## API Reference

Every endpoint returns a consistent **APIEnvelope**:

```json
{"success": true, "data": {...}, "error": null}
```

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/search` | Agentic semantic search |
| `POST` | `/api/v1/ingest/youtube` | Ingest a YouTube video |
| `POST` | `/api/v1/ingest/manual` | Ingest a manual transcript |
| `GET` | `/api/v1/library` | List all clips with chunk counts |
| `DELETE` | `/api/v1/library/{clip_id}` | Delete a clip (cascade) |
| `GET` | `/health` | Liveness probe |

### POST /api/v1/search

<details>
<summary>Request / Response</summary>

**Request:**
```json
{"query": "How did they handle database scaling?"}
```

**Response (200):**
```json
{
  "success": true,
  "data": {
    "results": [{
      "clip_id": "demo-incident-review",
      "question": "How did they handle database scaling?",
      "answer": "The fix was three-fold: increase pool size to 20, add connection timeouts, and implement read replicas.",
      "relevant_quotes": [
        {
          "quote": "The root cause was connection pool exhaustion.",
          "quote_description": "Root cause identification",
          "quote_timestamp": 30.0
        },
        {
          "quote": "The fix was three-fold: increase pool size to 20...",
          "quote_description": "Resolution steps",
          "quote_timestamp": 80.0
        }
      ],
      "related_questions": [
        "What monitoring was added after the incident?",
        "How do read replicas improve search performance?"
      ]
    }]
  },
  "error": null
}
```

**Errors:** `422` invalid input · `500` agent failure
</details>

### POST /api/v1/ingest/youtube

<details>
<summary>Request / Response</summary>

**Request:**
```json
{"url": "https://youtube.com/watch?v=aircAruvnKk", "languages": ["en"]}
```

**Response (200):**
```json
{
  "success": true,
  "data": {
    "clip_id": "yt-aircAruvnKk",
    "title": "But what is a neural network?",
    "chunks_stored": 47,
    "source_url": "https://www.youtube.com/watch?v=aircAruvnKk"
  }
}
```

**Errors:** `400` invalid URL / no transcript · `500` embedding failure
</details>

### POST /api/v1/ingest/manual

<details>
<summary>Request / Response</summary>

**Request:**
```json
{
  "clip_id": "meeting-2024-q4",
  "title": "Q4 Planning Meeting",
  "transcript": [
    {"text": "Welcome to Q4 planning.", "start": 0, "duration": 5},
    {"text": "Let's review our OKRs.", "start": 5, "duration": 3}
  ]
}
```
</details>

### GET /api/v1/library

<details>
<summary>Response</summary>

```json
{
  "success": true,
  "data": {
    "clips": [{
      "id": "yt-aircAruvnKk",
      "title": "But what is a neural network?",
      "source_url": "https://www.youtube.com/watch?v=aircAruvnKk",
      "duration_seconds": 1140,
      "channel_name": "3Blue1Brown",
      "language": "en",
      "chunk_count": 47
    }]
  }
}
```
</details>

### DELETE /api/v1/library/{clip_id}

```bash
curl -X DELETE http://localhost:8000/api/v1/library/yt-aircAruvnKk
# → {"success": true, "data": {"deleted": "yt-aircAruvnKk"}, "error": null}
```

**Errors:** `404` clip not found · `500` database error

---

## Project Structure

```
semantic-video-search/
│
├── backend/
│   ├── app/
│   │   ├── config.py              # Pydantic Settings — validated env vars
│   │   ├── main.py                # FastAPI app, lifespan, CORS, middleware
│   │   ├── agent/
│   │   │   ├── state.py           # TypedDict for graph state
│   │   │   ├── graph.py           # Cyclic agent graph
│   │   │   └── tools.py           # 3 retrieval tools + clip cache
│   │   ├── api/
│   │   │   ├── routes.py          # All endpoints
│   │   │   ├── schemas.py         # Pydantic models with validators
│   │   │   └── middleware.py      # X-Request-ID + latency tracking
│   │   ├── db/
│   │   │   ├── models.py          # VideoClip, TranscriptChunk ORM
│   │   │   ├── repository.py      # All SQL in one file
│   │   │   ├── session.py         # Async engine + connection pool
│   │   │   └── seed.py            # Demo data (3 clips, 28 chunks)
│   │   ├── ingestion/
│   │   │   ├── pipeline.py        # URL → transcript → chunks → vectors → DB
│   │   │   ├── transcriber.py     # YouTube transcript extraction
│   │   │   ├── chunker.py         # Sliding window with overlap
│   │   │   └── embedder.py        # Batch OpenAI embedding
│   │   ├── llm/
│   │   │   └── provider.py        # OpenAI + Anthropic switching
│   │   └── observability/
│   │       └── logging.py         # structlog config
│   ├── tests/
│   │   ├── unit/                  # 32 tests (no real APIs)
│   │   └── integration/           # 4 tests (full HTTP stack)
│   ├── Dockerfile
│   └── requirements.txt
│
├── frontend/
│   ├── app.py                     # Streamlit UI
│   └── Dockerfile
│
├── docs/adr/                      # Architecture Decision Records
├── docker-compose.yml             # pgvector + backend + frontend
├── Makefile                       # Developer commands
├── .github/workflows/ci.yml       # CI with pgvector service
└── .env.example                   # Config template
```

---

## Testing

```bash
make test              # All 36 tests
make test-unit         # 32 unit tests (no DB, no API keys)
make test-integration  # 4 integration tests
make test-cov          # Coverage report
```

| File | Tests | What It Covers |
|------|:-----:|----------------|
| `test_tools.py` | 6 | Tool dispatch, DB mocking, clip cache |
| `test_agent_graph.py` | 6 | Routing, respond node, iteration cap |
| `test_chunker.py` | 7 | Boundaries, overlap, timestamps, edge cases |
| `test_transcriber.py` | 6 | URL parsing (full, short, bare ID, invalid) |
| `test_api_schemas.py` | 7 | Validation, whitespace strip, envelope shape |
| `test_api_routes.py` | 4 | Full HTTP round-trip via httpx |

All external calls (OpenAI, DB) are mocked in unit tests — they run in under 1 second with zero cost. CI uses a real pgvector container via GitHub Actions services.

---

## Configuration

Copy `.env.example` to `.env`. All values are validated by Pydantic at startup.

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | *(required)* | OpenAI API key |
| `ANTHROPIC_API_KEY` | *(optional)* | For Anthropic provider |
| `LLM_PROVIDER` | `openai` | `openai` or `anthropic` |
| `LLM_MODEL` | `gpt-4o-mini` | Chat model name |
| `LLM_TEMPERATURE` | `0.1` | Low = factual |
| `EMBEDDING_MODEL` | `text-embedding-3-small` | Embedding model |
| `DATABASE_URL` | `postgresql+asyncpg://...` | Async PG connection |
| `DB_POOL_SIZE` | `10` | Connection pool |
| `VECTOR_SEARCH_TOP_K` | `20` | KNN candidates |
| `HNSW_M` | `16` | Index connectivity |
| `HNSW_EF_CONSTRUCTION` | `64` | Index build quality |
| `APP_ENV` | `development` | `development` / `production` |
| `APP_LOG_LEVEL` | `INFO` | Log verbosity |

---

## Technical Decisions

| Decision | Chose | Over | Why |
|----------|-------|------|-----|
| Agent framework | LangGraph cyclic graph | LangChain linear chain | Agent needs to loop, backtrack, skip tools |
| Vector store | pgvector + HNSW | ChromaDB / FAISS / Pinecone | ACID, HNSW indexing, metadata in same DB |
| LLM | Multi-provider (OpenAI + Anthropic) | Single provider | Vendor flexibility, cost optimization |
| Chunking | Sentence-aware sliding window | Fixed-size / recursive split | Preserves sentence boundaries + timestamps |
| Embedding | text-embedding-3-small | ada-002 | 5x cheaper, comparable quality |
| DB access | Repository pattern | Direct ORM in routes | Swap vector backend by editing one file |
| Logging | structlog (JSON / console) | stdlib logging | Request ID correlation across call stack |

Full rationale documented in ADRs:

| ADR | Decision |
|-----|----------|
| [001](docs/adr/001-langgraph-over-langchain.md) | LangGraph over LangChain |
| [002](docs/adr/002-pgvector-over-chromadb.md) | pgvector over ChromaDB |
| [003](docs/adr/003-multi-provider-llm.md) | Multi-provider LLM abstraction |

---

## Makefile

```bash
make help         make install       make dev
make db           make seed          make up
make down         make clean         make test
make test-unit    make test-cov      make lint
```

---

## Tech Stack

| | Technology |
|-|-----------|
| Agent | LangGraph StateGraph |
| LLM | GPT-4o-mini / Claude |
| Embeddings | text-embedding-3-small |
| Vector DB | PostgreSQL + pgvector |
| Backend | FastAPI (async) |
| ORM | SQLAlchemy 2.0 (async) |
| Frontend | Streamlit |
| Ingestion | youtube-transcript-api + yt-dlp |
| Logging | structlog |
| Testing | pytest-asyncio + httpx |
| CI | GitHub Actions |
| Deploy | Docker Compose |

---

## License

MIT

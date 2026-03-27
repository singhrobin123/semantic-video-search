<div align="center">

# Semantic Video Search Engine

**Production-grade agentic RAG system for semantic video transcript search**

[![CI](https://github.com/robin-singh/semantic-video-search/actions/workflows/ci.yml/badge.svg)](https://github.com/robin-singh/semantic-video-search/actions)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-36%20passing-brightgreen.svg)](#testing)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

*LangGraph · pgvector · OpenAI · FastAPI · Streamlit*

[Architecture](#system-architecture) · [Quick Start](#quick-start) · [API Reference](#api-reference) · [How It Works](#how-it-works)

</div>

---

## Table of Contents

- [What Is This?](#what-is-this)
- [System Architecture](#system-architecture)
- [How It Works](#how-it-works)
  - [Agentic Search Flow](#1-agentic-search-flow)
  - [YouTube Ingestion Pipeline](#2-youtube-ingestion-pipeline)
  - [Request Lifecycle](#3-request-lifecycle)
- [Data Model](#data-model)
- [Error Handling](#error-handling)
- [Quick Start](#quick-start)
- [API Reference](#api-reference)
- [Project Structure](#project-structure)
- [Testing](#testing)
- [Configuration](#configuration)
- [Technical Decisions](#technical-decisions)
- [Architecture Decision Records](#architecture-decision-records)

---

## What Is This?

A semantic search engine that lets you ask natural-language questions about a library of videos and get back precise, timestamped answers with cited evidence.

**The core loop:**

1. **Ingest** — Paste a YouTube URL. The system extracts the transcript, chunks it into sentence-aware overlapping windows, embeds each chunk via OpenAI, and stores the vectors in PostgreSQL with pgvector.
2. **Search** — Ask a question. A LangGraph agent autonomously decides which tools to call — broad KNN sweep, scoped clip examination, quote extraction — looping until it has enough evidence to answer.
3. **Answer** — Get a structured response: the answer, timestamped transcript citations you can click to seek to that moment in the video, and suggested follow-up questions.

This is **not** a basic embed-and-retrieve demo. The agent controls its own execution — it can examine multiple clips, skip irrelevant ones, and backtrack if its first approach doesn't yield results. The architecture is the same pattern used in production systems processing hundreds of millions of queries.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      Streamlit Frontend (:8501)                          │
│  ┌───────────┐  ┌──────────────┐  ┌─────────────┐  ┌───────────────┐  │
│  │ Chat UI   │  │ YouTube      │  │ Library     │  │ Video Player  │  │
│  │ (conv.    │  │ Ingestion    │  │ Management  │  │ (embedded YT  │  │
│  │  history) │  │ Sidebar      │  │ Sidebar     │  │  with seek)   │  │
│  └─────┬─────┘  └──────┬───────┘  └──────┬──────┘  └───────────────┘  │
└────────┼───────────────┼────────────────┼──────────────────────────────┘
         │               │                │
         │  HTTP / JSON  │                │   ← Every response is an
         │               │                │     APIEnvelope: {success, data, error}
┌────────┼───────────────┼────────────────┼──────────────────────────────┐
│        ▼               ▼                ▼                              │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │              FastAPI Backend (:8000)                              │  │
│  │                                                                  │  │
│  │  ┌─────────────────────┐  ┌──────────────────────────────────┐  │  │
│  │  │ Middleware           │  │ Routes                           │  │  │
│  │  │ • CORS              │  │ POST /api/v1/search              │  │  │
│  │  │ • Request Tracing   │  │ POST /api/v1/ingest/youtube      │  │  │
│  │  │   (X-Request-ID,    │  │ POST /api/v1/ingest/manual       │  │  │
│  │  │    latency)         │  │ GET  /api/v1/library             │  │  │
│  │  └─────────────────────┘  │ DELETE /api/v1/library/{id}      │  │  │
│  │                           │ GET  /health                      │  │  │
│  │                           └──────┬────────────┬──────────────┘  │  │
│  │                                  │            │                  │  │
│  │              ┌───────────────────┘            └──────────┐      │  │
│  │              ▼                                           ▼      │  │
│  │  ┌───────────────────────┐              ┌──────────────────┐   │  │
│  │  │  LangGraph Agent      │              │ Ingestion        │   │  │
│  │  │                       │              │ Pipeline         │   │  │
│  │  │  ┌─────────────────┐  │              │                  │   │  │
│  │  │  │ agent_reason    │◀─┐              │ 1. Transcriber   │   │  │
│  │  │  │     │           │  │              │ 2. Chunker       │   │  │
│  │  │  │     ▼           │  │              │ 3. Embedder      │   │  │
│  │  │  │ should_continue │  │              │ 4. Store         │   │  │
│  │  │  │   │       │     │  │              └────────┬─────────┘   │  │
│  │  │  │ tools   respond │  │                       │             │  │
│  │  │  │   │       │     │  │                       │             │  │
│  │  │  │   ▼       ▼     │  │                       │             │  │
│  │  │  │ tool_exec  END  │  │                       │             │  │
│  │  │  │   │             │  │                       │             │  │
│  │  │  │   └─────────────┘  │                       │             │  │
│  │  │  └────────────────────┘                       │             │  │
│  │  │                       │                       │             │  │
│  │  │  Tools:               │                       │             │  │
│  │  │  • get_initial_       │                       │             │  │
│  │  │    candidates         │                       │             │  │
│  │  │  • examine_clip_      │                       │             │  │
│  │  │    deeper             │                       │             │  │
│  │  │  • get_clip_quotes    │                       │             │  │
│  │  └───────────┬───────────┘                       │             │  │
│  │              │                                   │             │  │
│  │              ▼                                   ▼             │  │
│  │  ┌─────────────────────────────────────────────────────────┐  │  │
│  │  │  Repository Layer (db/repository.py)                     │  │  │
│  │  │  Single module that owns all SQL.                        │  │  │
│  │  │  Swap pgvector for Pinecone → only this file changes.   │  │  │
│  │  └──────────────────────────┬──────────────────────────────┘  │  │
│  └─────────────────────────────┼────────────────────────────────┘  │
└────────────────────────────────┼───────────────────────────────────┘
                                 │
              ┌──────────────────▼──────────────────────┐
              │    PostgreSQL + pgvector (:5432)         │
              │                                         │
              │  video_clips          transcript_chunks  │
              │  ┌──────────────┐    ┌────────────────┐ │
              │  │ id (PK)      │1──N│ clip_id (FK)   │ │
              │  │ title        │    │ segment_text   │ │
              │  │ description  │    │ start_time     │ │
              │  │ source_url   │    │ end_time       │ │
              │  │ duration_sec │    │ chunk_index    │ │
              │  │ channel_name │    │ embedding      │ │
              │  │ language     │    │   (1536-dim)   │ │
              │  │ ingested_at  │    │ HNSW index     │ │
              │  └──────────────┘    └────────────────┘ │
              └─────────────────────────────────────────┘
```

---

## How It Works

### 1. Agentic Search Flow

This is the core of the system. When a user asks a question, the LangGraph agent runs a **cyclic loop** — it reasons about what to do next, calls a tool, observes the result, and either calls another tool or produces a final answer.

```mermaid
sequenceDiagram
    participant U as User
    participant FE as Streamlit
    participant API as FastAPI /search
    participant MW as Middleware
    participant AG as LangGraph Agent
    participant T1 as get_initial_candidates
    participant T2 as examine_clip_deeper
    participant T3 as get_clip_quotes
    participant LLM as GPT-4o-mini
    participant DB as pgvector
    participant EMB as OpenAI Embeddings

    U->>FE: "How did they handle database scaling?"
    FE->>API: POST /api/v1/search
    API->>MW: Assign X-Request-ID, start timer
    MW->>AG: Build AgentState (system prompt + user message)

    rect rgb(240, 248, 255)
        Note over AG,LLM: Iteration 1 — Agent decides to search
        AG->>LLM: Conversation history + tool definitions
        LLM-->>AG: tool_call: get_initial_candidates(question)
        AG->>T1: Execute
        T1->>EMB: Embed the question
        EMB-->>T1: 1536-dim vector
        T1->>DB: Cosine KNN across all chunks (top-20)
        DB-->>T1: Matching chunks
        T1-->>AG: Candidates grouped by clip_id
    end

    rect rgb(240, 255, 240)
        Note over AG,LLM: Iteration 2 — Agent examines best candidate
        AG->>LLM: Conversation + tool result
        LLM-->>AG: tool_call: examine_clip_deeper("demo-incident-review")
        AG->>T2: Execute
        T2->>EMB: Embed question (scoped search)
        T2->>DB: KNN within this clip only (top-10)
        DB-->>T2: Relevant moments
        Note over T2: Cache clip data in memory
        T2-->>AG: Clip metadata + transcript context
    end

    rect rgb(255, 248, 240)
        Note over AG,LLM: Iteration 3 — Agent gets citations
        AG->>LLM: Conversation + examination result
        LLM-->>AG: tool_call: get_clip_quotes("demo-incident-review")
        AG->>T3: Execute
        Note over T3: Read from cache (zero DB calls)
        T3-->>AG: Chronological timestamped quotes
    end

    rect rgb(248, 240, 255)
        Note over AG,LLM: Iteration 4 — Agent formulates answer
        AG->>LLM: All context accumulated
        LLM-->>AG: Final JSON response (no tool calls)
        Note over AG: should_continue() → "respond"
        AG->>AG: Parse into SearchResponse schema
    end

    AG-->>API: {results: [{clip_id, answer, quotes, related_questions}]}
    API->>MW: Log elapsed_ms, attach X-Request-ID
    MW-->>FE: APIEnvelope {success: true, data: ...}
    FE->>U: Answer + timestamped quotes + video player + follow-ups
```

**Why this matters:**
- The agent **chose** to examine only one clip. If there were multiple relevant clips, it would have called `examine_clip_deeper` for each.
- The clip cache between tools 2 and 3 eliminates a redundant database round-trip.
- `should_continue()` enforces a hard cap of **8 iterations** to prevent runaway loops and unbounded LLM cost.
- If the LLM returns malformed JSON, the `respond` node wraps raw text in the expected schema (graceful degradation, not a crash).

---

### 2. YouTube Ingestion Pipeline

When you paste a YouTube URL, four independent stages run in sequence. Each stage is its own module and can be tested in isolation.

```mermaid
sequenceDiagram
    participant U as User
    participant FE as Streamlit Sidebar
    participant API as POST /ingest/youtube
    participant TR as Transcriber
    participant YT as youtube-transcript-api
    participant YD as yt-dlp (metadata)
    participant CH as Chunker
    participant EM as Embedder
    participant OAI as OpenAI API
    participant R as Repository
    participant DB as pgvector

    U->>FE: Paste YouTube URL
    FE->>API: {url, languages: ["en"]}

    Note over API: Pydantic validates input

    API->>TR: fetch_youtube_transcript(url)
    TR->>TR: extract_youtube_id() via regex
    TR->>YT: Fetch captions (no API key needed)
    YT-->>TR: [{text, start, duration}, ...]
    TR-->>API: segments[] + metadata

    API->>YD: fetch_youtube_metadata(video_id)
    YD-->>API: {title, channel, duration}
    Note over YD: Falls back gracefully if yt-dlp fails

    API->>CH: chunk_transcript(segments)
    Note over CH: Sentence-aware sliding window<br/>max=1500 chars, overlap=200 chars<br/>Preserves start/end timestamps
    CH-->>API: TranscriptChunkDTO[]

    API->>EM: embed_chunks(chunks)
    loop Batches of 512
        EM->>OAI: embed_documents(batch)
        OAI-->>EM: float[][] (1536-dim)
    end
    EM-->>API: vectors[] (1:1 with chunks)

    API->>R: upsert_clip(VideoClip)
    R->>DB: INSERT or UPDATE (idempotent)
    API->>R: bulk_insert_chunks(TranscriptChunk[])
    R->>DB: Batch INSERT with embeddings

    API-->>FE: {clip_id, title, chunks_stored}
    FE->>U: "Ingested 'Video Title' — 47 chunks stored"
```

**Key design choices:**
- **Idempotent re-ingestion** — Ingesting the same URL twice updates metadata and replaces chunks. No duplicates.
- **Sentence-aware chunking** — Naive fixed-size splitting destroys sentence boundaries and timestamps. The sliding window with 200-char overlap ensures context is preserved at chunk edges.
- **Batch embedding** — Chunks are embedded in batches of 512 to stay within OpenAI's rate limits.
- **Graceful degradation** — If yt-dlp can't fetch metadata (e.g., age-restricted video), the pipeline continues with a placeholder title.

---

### 3. Request Lifecycle

Every HTTP request, regardless of endpoint, passes through the same middleware stack:

```mermaid
sequenceDiagram
    participant C as Client
    participant CORS as CORS Middleware
    participant RT as Request Tracing
    participant LOG as structlog
    participant H as Route Handler
    participant BL as Business Logic

    C->>CORS: HTTP Request
    CORS->>CORS: Validate origin
    CORS->>RT: Forward

    RT->>RT: Generate UUID4 as X-Request-ID
    RT->>RT: Start perf_counter
    RT->>LOG: bind_contextvars(request_id, method, path)
    Note over LOG: Every log line in this request<br/>now carries this request_id

    RT->>H: Forward to route handler
    H->>BL: Execute business logic

    alt Success path
        BL-->>H: Result
        H-->>RT: APIEnvelope(success=true, data=result)
    else Client error (ValueError)
        BL-->>H: Raise ValueError
        H-->>RT: 400 + APIEnvelope(success=false, error=message)
    else Server error (Exception)
        BL-->>H: Raise Exception
        H->>LOG: logger.exception() with full traceback
        H-->>RT: 500 + APIEnvelope(success=false, error="safe message")
    end

    RT->>RT: Stop timer
    RT->>LOG: log(request_complete, status_code, elapsed_ms)
    RT->>RT: Set response headers
    RT-->>CORS: Response + X-Request-ID + X-Response-Time-Ms
    CORS-->>C: Response
```

This means you can take any request ID from the frontend error message, grep the logs, and trace every agent tool call, DB query, and LLM invocation that happened during that request.

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
        string clip_id FK "→ video_clips.id"
        text segment_text "transcript content"
        float start_time "seconds"
        float end_time
        int chunk_index "order within clip"
        vector_1536 embedding "HNSW indexed"
        datetime created_at "auto"
    }
```

**Vector search details:**
- Embedding model: `text-embedding-3-small` (1536 dimensions)
- Index type: **HNSW** (Hierarchical Navigable Small World) — builds a multi-layer navigable graph for approximate nearest neighbor search
- Index params: `m=16` (connections per node), `ef_construction=64` (build-time quality)
- Distance operator: `vector_cosine_ops` (cosine distance via pgvector's `<=>` operator)
- Result: sub-millisecond ANN queries even at millions of vectors

---

## Error Handling

Errors are handled at **six layers**, each with its own strategy. No raw tracebacks ever reach the client.

### Layer 1 — Input Validation (Pydantic)

Schemas strip whitespace and enforce constraints before any business logic runs:

```python
class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)

    @field_validator("query", mode="before")
    def strip_query(cls, v):
        return v.strip() if isinstance(v, str) else v
```

Empty or whitespace-only queries → automatic 422 from FastAPI.

### Layer 2 — Route Handlers

Every endpoint uses this pattern:

```python
try:
    result = await business_logic()
    return APIEnvelope(success=True, data=result)
except ValueError as exc:
    # Client did something wrong (bad URL, no transcript found)
    return JSONResponse(status_code=400,
        content=APIEnvelope(success=False, error=str(exc)).model_dump())
except Exception:
    # Our fault — log the full traceback, return a safe message
    logger.exception("operation_failed")
    return JSONResponse(status_code=500,
        content=APIEnvelope(success=False, error="Internal error").model_dump())
```

### Layer 3 — Agent Tool Execution

Each tool call is individually wrapped. A single failing tool doesn't crash the agent — the error is returned as a `ToolMessage` and the LLM can recover:

```python
try:
    result_str = await handler(**fn_args)
except Exception as exc:
    logger.exception("tool_execution_error", tool=fn_name)
    result_str = json.dumps({"error": str(exc)})
```

### Layer 4 — Response Parsing

If the LLM returns invalid JSON (it happens), the `respond` node wraps the raw text in the expected schema instead of crashing:

```python
try:
    parsed = json.loads(content)
    response = SearchResponse(**parsed)
except (json.JSONDecodeError, Exception):
    result = {"results": [{"answer": content[:600], "relevant_quotes": [], ...}]}
```

### Layer 5 — External Services

Metadata extraction is optional. If yt-dlp isn't installed or fails, the pipeline continues:

```python
except ImportError:
    return {"title": f"YouTube Video {video_id}", ...}  # Works without yt-dlp
except Exception:
    return {"title": f"YouTube Video {video_id}", ...}  # Works if yt-dlp errors
```

### Layer 6 — Frontend

A centralized `api_call()` function handles connection errors and HTTP errors:

```python
except requests.exceptions.ConnectionError:
    st.error("Cannot reach backend. Is FastAPI running on port 8000?")
```

---

## Quick Start

### Prerequisites

- **Docker** (for the PostgreSQL + pgvector database)
- **Python 3.12+**
- **OpenAI API Key** — [get one here](https://platform.openai.com/api-keys)

### Option A: Docker (everything containerized)

```bash
git clone <repo-url>
cd Semantic-Video-Search-Engine
cp .env.example .env
# Edit .env → set your OPENAI_API_KEY

make up    # Starts pgvector + backend + frontend
```

Open http://localhost:8501.

### Option B: Local development

```bash
git clone <repo-url>
cd Semantic-Video-Search-Engine
cp .env.example .env
# Edit .env → set your OPENAI_API_KEY

# 1. Start the database
make db

# 2. Set up Python
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. Seed demo data (embeds 28 chunks via OpenAI — costs ~$0.001)
python -m app.db.seed

# 4. Start the backend
uvicorn app.main:app --reload --port 8000

# 5. In a new terminal, start the frontend
cd frontend
pip install streamlit requests
streamlit run app.py --server.port 8501
```

### Verify it works

```bash
# Health check
curl http://localhost:8000/health
# → {"status": "healthy", "version": "2.0.0"}

# List seeded videos
curl -s http://localhost:8000/api/v1/library | python3 -m json.tool

# Run a search
curl -s -X POST http://localhost:8000/api/v1/search \
  -H "Content-Type: application/json" \
  -d '{"query": "How did they handle database scaling?"}' | python3 -m json.tool

# Ingest a real YouTube video
curl -s -X POST http://localhost:8000/api/v1/ingest/youtube \
  -H "Content-Type: application/json" \
  -d '{"url": "https://youtube.com/watch?v=aircAruvnKk"}' | python3 -m json.tool
```

---

## API Reference

Every endpoint returns an **APIEnvelope**:
```json
{
  "success": true,
  "data": { ... },
  "error": null
}
```

### POST /api/v1/search

Run an agentic semantic search across all ingested videos.

**Request:**
```json
{"query": "How did they handle database scaling?"}
```

**Response (200):**
```json
{
  "success": true,
  "data": {
    "results": [
      {
        "clip_id": "demo-incident-review",
        "question": "How did they handle database scaling?",
        "answer": "The fix was three-fold: increase pool size to 20, add connection timeouts, and implement read replicas for search queries.",
        "relevant_quotes": [
          {
            "quote": "The root cause was connection pool exhaustion.",
            "quote_description": "Root cause identification",
            "quote_timestamp": 30.0
          },
          {
            "quote": "The fix was three-fold: increase pool size to 20, add connection timeouts, and implement read replicas.",
            "quote_description": "Resolution steps",
            "quote_timestamp": 80.0
          }
        ],
        "related_questions": [
          "What monitoring was added after the incident?",
          "How do read replicas improve search performance?",
          "What is connection pool exhaustion?",
          "How does pgvector handle concurrent queries?",
          "What load testing practices were adopted?"
        ]
      }
    ]
  },
  "error": null
}
```

**Errors:** 422 (invalid input), 500 (agent failure)

### POST /api/v1/ingest/youtube

Ingest a YouTube video: fetch transcript → chunk → embed → store.

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

**Errors:** 400 (invalid URL, no transcript), 500 (embedding failure)

### POST /api/v1/ingest/manual

Ingest a manually provided transcript (for non-YouTube sources).

**Request:**
```json
{
  "clip_id": "meeting-2024-q4",
  "title": "Q4 Planning Meeting",
  "description": "Quarterly planning session",
  "transcript": [
    {"text": "Welcome everyone to Q4 planning.", "start": 0, "duration": 5},
    {"text": "Let's review our OKRs.", "start": 5, "duration": 3}
  ]
}
```

### GET /api/v1/library

List all ingested video clips with chunk counts.

**Response:**
```json
{
  "success": true,
  "data": {
    "clips": [
      {
        "id": "yt-aircAruvnKk",
        "title": "But what is a neural network?",
        "source_url": "https://www.youtube.com/watch?v=aircAruvnKk",
        "duration_seconds": 1140,
        "channel_name": "3Blue1Brown",
        "language": "en",
        "chunk_count": 47
      }
    ]
  }
}
```

### DELETE /api/v1/library/{clip_id}

Delete a clip and all its transcript chunks (cascade).

```bash
curl -X DELETE http://localhost:8000/api/v1/library/yt-aircAruvnKk
# → {"success": true, "data": {"deleted": "yt-aircAruvnKk"}, "error": null}
```

**Errors:** 404 (clip not found), 500 (database error)

### GET /health

Liveness probe for container orchestrators.

```json
{"status": "healthy", "version": "2.0.0"}
```

---

## Project Structure

```
Semantic-Video-Search-Engine/
├── backend/
│   ├── app/
│   │   ├── config.py                 # Pydantic Settings — all env vars validated at startup
│   │   ├── main.py                   # FastAPI app with lifespan hooks, CORS, middleware
│   │   │
│   │   ├── agent/                    # LangGraph state machine
│   │   │   ├── state.py              # TypedDict defining what flows through the graph
│   │   │   ├── graph.py              # Cyclic graph: agent → tool_exec → agent → respond
│   │   │   └── tools.py              # Three tools: candidates, examine, quotes
│   │   │
│   │   ├── api/                      # HTTP layer
│   │   │   ├── routes.py             # Six endpoints with consistent error handling
│   │   │   ├── schemas.py            # Pydantic request/response models with validators
│   │   │   └── middleware.py          # X-Request-ID injection + latency measurement
│   │   │
│   │   ├── db/                       # Persistence (repository pattern)
│   │   │   ├── models.py             # SQLAlchemy ORM: VideoClip, TranscriptChunk
│   │   │   ├── repository.py         # All SQL lives here — the only DB-aware module
│   │   │   ├── session.py            # Async engine, connection pool, init_db
│   │   │   └── seed.py               # Demo data seeder (3 clips, 28 chunks)
│   │   │
│   │   ├── ingestion/                # Data pipeline
│   │   │   ├── pipeline.py           # Orchestrator: URL → transcript → chunks → vectors → DB
│   │   │   ├── transcriber.py        # YouTube transcript extraction via youtube-transcript-api
│   │   │   ├── chunker.py            # Sentence-aware sliding window with overlap
│   │   │   └── embedder.py           # Batch embedding via OpenAI
│   │   │
│   │   ├── llm/                      # LLM abstraction
│   │   │   └── provider.py           # OpenAI + Anthropic, switchable via env var
│   │   │
│   │   └── observability/
│   │       └── logging.py            # structlog: JSON in production, console in dev
│   │
│   ├── tests/
│   │   ├── conftest.py               # Shared fixtures (mocked repo, mocked embeddings)
│   │   ├── unit/                     # 32 tests — no real API/DB calls
│   │   │   ├── test_tools.py         # Tool dispatch, caching, empty corpus
│   │   │   ├── test_agent_graph.py   # Routing logic, respond node, iteration cap
│   │   │   ├── test_chunker.py       # Boundaries, overlap, timestamps, edge cases
│   │   │   ├── test_transcriber.py   # URL parsing (full URL, short, bare ID, invalid)
│   │   │   └── test_api_schemas.py   # Pydantic validation, envelope shape
│   │   └── integration/              # 4 tests — full HTTP round-trip via httpx
│   │       └── test_api_routes.py
│   │
│   ├── Dockerfile
│   └── requirements.txt
│
├── frontend/
│   ├── app.py                        # Streamlit: chat, ingestion, library, embedded player
│   └── Dockerfile
│
├── docs/adr/                         # Architecture Decision Records
│   ├── 001-langgraph-over-langchain.md
│   ├── 002-pgvector-over-chromadb.md
│   └── 003-multi-provider-llm.md
│
├── .github/workflows/ci.yml          # GitHub Actions with pgvector service container
├── docker-compose.yml                # Full stack: pgvector + backend + frontend
├── Makefile                          # Developer commands (see below)
└── .env.example                      # Template with all config options documented
```

---

## Testing

```bash
make test              # All 36 tests
make test-unit         # 32 unit tests (no DB, no API keys needed)
make test-integration  # 4 integration tests (full HTTP stack)
make test-cov          # Coverage report
```

### What's tested

| File | What | Count |
|------|------|-------|
| `test_tools.py` | Tool dispatch, DB mocking, clip cache population/reset | 6 |
| `test_agent_graph.py` | `should_continue` routing, `respond` JSON parsing, iteration cap, fallback on bad JSON | 6 |
| `test_chunker.py` | Empty input, single segment, max_chars boundary, overlap correctness, sequential indices, monotonic timestamps, trailing fragment drop | 7 |
| `test_transcriber.py` | Full YouTube URL, short URL, bare ID, URL with extra params, invalid URL, empty string | 6 |
| `test_api_schemas.py` | Valid query, empty query rejection, whitespace stripping, envelope shape, error envelope, ingestion defaults | 7 |
| `test_api_routes.py` | Search envelope, empty query 422, health check, library list | 4 |

**Testing strategy:**
- All external calls (OpenAI, DB) are mocked in unit tests — they run in <1 second with zero cost.
- Integration tests use `httpx.AsyncClient` against the real FastAPI app with mocked business logic.
- CI spins up a real pgvector container via GitHub Actions services.

---

## Configuration

All settings are managed via environment variables, validated by Pydantic at startup. Copy `.env.example` to `.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | *(required)* | OpenAI API key |
| `ANTHROPIC_API_KEY` | *(optional)* | For Anthropic provider |
| `LLM_PROVIDER` | `openai` | `openai` or `anthropic` |
| `LLM_MODEL` | `gpt-4o-mini` | Chat model |
| `LLM_TEMPERATURE` | `0.1` | Low for factual retrieval |
| `EMBEDDING_MODEL` | `text-embedding-3-small` | Embedding model |
| `DATABASE_URL` | `postgresql+asyncpg://user:password@localhost:5432/vectordb` | Async PG connection string |
| `DB_POOL_SIZE` | `10` | Connection pool size |
| `DB_MAX_OVERFLOW` | `20` | Overflow connections |
| `VECTOR_SEARCH_TOP_K` | `20` | Initial KNN candidates |
| `HNSW_M` | `16` | HNSW connectivity |
| `HNSW_EF_CONSTRUCTION` | `64` | HNSW build quality |
| `APP_ENV` | `development` | `development` / `staging` / `production` |
| `APP_LOG_LEVEL` | `INFO` | Log level |
| `APP_CORS_ORIGINS` | `["http://localhost:8501"]` | CORS origins (JSON array) |

---

## Makefile Commands

```bash
make help              # Show all available commands
make install           # Install Python dependencies
make dev               # Start pgvector + backend + frontend locally
make db                # Start only pgvector
make seed              # Seed demo data (3 clips, 28 embedded chunks)
make up                # Docker Compose full-stack build + start
make down              # Stop all containers
make clean             # Stop + remove volumes (fresh start)
make test              # Run all 36 tests
make test-unit         # Unit tests only
make test-integration  # Integration tests only
make test-cov          # Tests with coverage report
make lint              # Type checking with mypy
```

---

## Technical Decisions

| Decision | What We Chose | What We Didn't | Why |
|----------|---------------|----------------|-----|
| Agent orchestration | LangGraph cyclic graph | LangChain linear chain | Need the agent to loop, backtrack, and conditionally skip tools |
| Vector storage | pgvector + HNSW | ChromaDB / FAISS / Pinecone | Production-grade PostgreSQL extension with ACID, HNSW indexing, same DB for metadata + vectors |
| LLM integration | Multi-provider (OpenAI + Anthropic) | Single provider | Vendor flexibility, cost optimization between providers |
| Transcript chunking | Sentence-aware sliding window | Fixed-size split / recursive | Preserves sentence boundaries and accurate timestamps |
| Embedding model | text-embedding-3-small | ada-002 / large variant | 5x cheaper, comparable quality for transcript search |
| DB access pattern | Repository + context manager | Direct ORM in routes | One file owns all SQL — swap pgvector for Pinecone by editing `repository.py` only |
| Session management | Async SQLAlchemy + pool | Raw asyncpg | Type-safe queries, configurable pool, pool_pre_ping for resilience |
| Logging | structlog (JSON prod / console dev) | stdlib logging | Request ID correlation across the entire call stack |
| Frontend | Streamlit | React | Good enough for demo; built-in chat components |

---

## Architecture Decision Records

| # | Decision | One-line Summary |
|---|----------|-----------------|
| [001](docs/adr/001-langgraph-over-langchain.md) | LangGraph over LangChain | Cyclic tool-calling graph for autonomous multi-step retrieval |
| [002](docs/adr/002-pgvector-over-chromadb.md) | pgvector over ChromaDB | ACID transactions, HNSW indexing, metadata colocation |
| [003](docs/adr/003-multi-provider-llm.md) | Multi-provider LLM | Single env var switches providers; embedding always uses OpenAI |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Agent | LangGraph `StateGraph` with cyclic tool-calling |
| LLM | OpenAI GPT-4o-mini (or Anthropic Claude) |
| Embeddings | `text-embedding-3-small` (1536 dimensions) |
| Vector DB | PostgreSQL + pgvector with HNSW index |
| Backend | FastAPI (fully async) |
| ORM | SQLAlchemy 2.0 (async, with connection pooling) |
| Frontend | Streamlit |
| Ingestion | youtube-transcript-api + yt-dlp |
| Logging | structlog (JSON structured logs) |
| Testing | pytest-asyncio + httpx |
| CI | GitHub Actions (pgvector service container) |
| Deployment | Docker Compose |

---

## License

MIT

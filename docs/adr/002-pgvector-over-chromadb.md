# ADR-002: pgvector Over ChromaDB / FAISS

## Status
Accepted

## Context
Most tutorial projects use ChromaDB or FAISS for vector storage. While these are convenient for prototyping, they have production limitations:

- **ChromaDB**: In-memory by default, no ACID guarantees, limited to ~1M vectors before performance degrades.
- **FAISS**: Requires manual index management, no built-in persistence, C++ dependency issues in Docker.
- Neither integrates with existing PostgreSQL infrastructure or provides SQL-level joins.

## Decision
We use **PostgreSQL + pgvector** with HNSW indexing:

1. **pgvector** stores 1536-dimensional OpenAI embeddings as native PostgreSQL columns.
2. **HNSW index** (`vector_cosine_ops`) provides sub-millisecond approximate nearest neighbor search.
3. **SQLAlchemy async** provides a Pythonic ORM with full connection pooling.
4. Video metadata (`VideoClip`) and transcript chunks (`TranscriptChunk`) live in the same database with proper foreign keys and cascade deletes.

## Consequences
- **Positive**: Production-ready storage; ACID transactions; relational joins between clips and chunks.
- **Positive**: HNSW index scales to millions of vectors with O(log N) query time.
- **Positive**: Same technology stack as enterprise deployments.
- **Negative**: Requires a running PostgreSQL instance (mitigated by Docker Compose).
- **Negative**: Slightly more setup than `pip install chromadb`.

"""
Database seeder for local development and demos.

Seeds the vector database with realistic mock transcript data from
multiple video clips, demonstrating the multi-clip search capability.

Usage:
    python -m app.db.seed
"""

from __future__ import annotations

import asyncio

from dotenv import load_dotenv

load_dotenv()

from app.db.models import TranscriptChunk, VideoClip
from app.db.repository import Repository
from app.db.session import init_db
from app.ingestion.chunker import TranscriptChunkDTO
from app.ingestion.embedder import embed_chunks
from app.observability.logging import setup_logging

setup_logging()

# ── Demo data ────────────────────────────────────────────────────────────

DEMO_CLIPS = [
    {
        "id": "demo-engineering-allhands",
        "title": "Engineering All-Hands: Platform Migration to Go",
        "description": "Q1 all-hands covering the transition from PHP to Go for core video services.",
        "source_url": "",
        "segments": [
            {"start": 10.0, "text": "Welcome to the engineering all-hands. Today we discuss our transition from PHP to Go for our core video processing pipeline."},
            {"start": 30.0, "text": "The main driver was latency. Our PHP workers were averaging 200ms per request, but Go brought that down to 12ms."},
            {"start": 55.0, "text": "We realized that video simulcasting required ultra-low latency, so we built a custom stream multiplexer in Go."},
            {"start": 80.0, "text": "The migration took six months. We used a strangler fig pattern, routing traffic gradually from the PHP monolith to Go microservices."},
            {"start": 120.0, "text": "By shifting our core ingest pipeline to Kafka, our database write amplification dropped by 40 percent."},
            {"start": 150.0, "text": "One unexpected benefit was memory usage. Go's garbage collector is much more predictable than PHP's, reducing our p99 tail latencies significantly."},
            {"start": 180.0, "text": "For the semantic search feature, we migrated from Elasticsearch full-text search to a dedicated vector store backed by pgvector."},
            {"start": 210.0, "text": "The vector search approach lets users ask natural language questions like 'where did we discuss scaling' and get precise timestamp results."},
            {"start": 240.0, "text": "We're now processing over 500 million embedding queries per month across the platform."},
            {"start": 270.0, "text": "Next quarter we're evaluating AWS Bedrock as an alternative to OpenAI for customers with strict data residency requirements."},
        ],
    },
    {
        "id": "demo-ml-deepdive",
        "title": "ML Deep Dive: Building the Semantic Search Pipeline",
        "description": "Technical deep-dive into the ML architecture behind video semantic search.",
        "source_url": "",
        "segments": [
            {"start": 5.0, "text": "Today I want to walk you through how we built the semantic search pipeline from scratch."},
            {"start": 25.0, "text": "The core idea is simple: we take video transcripts, chunk them into overlapping windows, embed each chunk, and store the vectors in pgvector."},
            {"start": 50.0, "text": "For embedding, we use OpenAI's text-embedding-3-small model. It produces 1536-dimensional vectors at a fraction of the cost of ada-002."},
            {"start": 75.0, "text": "Chunking strategy matters enormously. We use sentence-aware sliding windows with 200 character overlap to avoid losing context at chunk boundaries."},
            {"start": 100.0, "text": "The retrieval pattern is three steps: broad KNN sweep, scoped clip examination, then quote extraction. The LLM agent decides the order."},
            {"start": 130.0, "text": "We tested HNSW versus IVFFlat indexes. HNSW won decisively — 3x faster queries with only 5 percent more memory overhead."},
            {"start": 160.0, "text": "A critical insight was caching clip data between tool calls. Without it, the agent was making redundant database queries for the same clip."},
            {"start": 190.0, "text": "For evaluation, we built a golden dataset of 500 question-answer pairs and measure recall at k equals 5. We're currently at 87 percent."},
            {"start": 220.0, "text": "The biggest challenge was handling videos with poor transcript quality. ASR errors propagate through the entire pipeline."},
            {"start": 250.0, "text": "Our next step is adding visual understanding — using CLIP embeddings to search by visual content, not just speech."},
        ],
    },
    {
        "id": "demo-incident-review",
        "title": "Incident Review: The Great Database Scaling Event",
        "description": "Post-mortem review of the Q3 database scaling incident and lessons learned.",
        "source_url": "",
        "segments": [
            {"start": 8.0, "text": "Let's review the database scaling incident from last quarter. This was our highest severity incident of the year."},
            {"start": 30.0, "text": "The root cause was connection pool exhaustion. Our pgvector queries were holding connections for too long during peak traffic."},
            {"start": 55.0, "text": "We had configured pool_size of 5 with max_overflow of 10, which was fine at our previous scale but not after the product launch."},
            {"start": 80.0, "text": "The fix was three-fold: increase pool size to 20, add connection timeouts, and implement read replicas for search queries."},
            {"start": 110.0, "text": "We also discovered that our HNSW index was not being used for some queries because the planner chose a sequential scan for small result sets."},
            {"start": 140.0, "text": "The lesson learned is that you must test with production-like data volumes. Our staging environment had 1000 vectors; production had 50 million."},
            {"start": 170.0, "text": "We now have automated load testing that runs weekly against a production-mirror dataset to catch scaling issues early."},
            {"start": 200.0, "text": "Another improvement was adding structured logging with request IDs so we could trace a single user query across all microservices."},
        ],
    },
]


async def seed():
    """Seed the database with demo clips and their embedded transcript chunks."""
    print("Initializing database with HNSW index...")
    await init_db()

    for clip_data in DEMO_CLIPS:
        print(f"\nSeeding: {clip_data['title']}")

        # Build chunks for embedding
        chunk_dtos = [
            TranscriptChunkDTO(
                text=seg["text"],
                start_time=seg["start"],
                end_time=seg["start"] + 25.0,
                chunk_index=i,
            )
            for i, seg in enumerate(clip_data["segments"])
        ]

        print(f"  Embedding {len(chunk_dtos)} chunks via OpenAI...")
        vectors = await embed_chunks(chunk_dtos)

        async with Repository() as repo:
            clip = VideoClip(
                id=clip_data["id"],
                title=clip_data["title"],
                description=clip_data["description"],
                source_url=clip_data["source_url"],
            )
            await repo.upsert_clip(clip)

            db_chunks = [
                TranscriptChunk(
                    clip_id=clip_data["id"],
                    segment_text=dto.text,
                    start_time=dto.start_time,
                    end_time=dto.end_time,
                    chunk_index=dto.chunk_index,
                    embedding=vectors[i],
                )
                for i, dto in enumerate(chunk_dtos)
            ]
            count = await repo.bulk_insert_chunks(db_chunks)
            print(f"  Stored {count} chunks for '{clip_data['title']}'")

    print("\n✅ Database seeding complete! All demo vectors stored.")


if __name__ == "__main__":
    asyncio.run(seed())

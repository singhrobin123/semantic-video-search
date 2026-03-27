"""
Data-access repository — the *only* module that speaks SQL.

Every other layer (agent tools, API routes, ingestion pipeline) goes through
this repository.  This enforces a clean boundary: if we ever swap pgvector
for Pinecone or Weaviate, only this file changes.
"""

from __future__ import annotations

from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import TranscriptChunk, VideoClip
from app.db.session import get_session_factory
from app.observability.logging import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Video Clip CRUD
# ---------------------------------------------------------------------------

async def upsert_clip(session: AsyncSession, clip: VideoClip) -> VideoClip:
    """Insert or merge a VideoClip (idempotent on ``clip.id``)."""
    merged = await session.merge(clip)
    await session.flush()
    return merged


async def get_clip(session: AsyncSession, clip_id: str) -> VideoClip | None:
    result = await session.execute(
        select(VideoClip).where(VideoClip.id == clip_id)
    )
    return result.scalar_one_or_none()


async def list_clips(session: AsyncSession, limit: int = 50) -> Sequence[VideoClip]:
    result = await session.execute(
        select(VideoClip).order_by(VideoClip.ingested_at.desc()).limit(limit)
    )
    return result.scalars().all()


async def delete_clip(session: AsyncSession, clip_id: str) -> bool:
    """Delete a clip and all its chunks (cascade). Returns True if found."""
    clip = await get_clip(session, clip_id)
    if clip is None:
        return False
    await session.delete(clip)
    await session.flush()
    return True


# ---------------------------------------------------------------------------
# Transcript Chunk operations
# ---------------------------------------------------------------------------

async def bulk_insert_chunks(
    session: AsyncSession,
    chunks: list[TranscriptChunk],
) -> int:
    """Batch-insert transcript chunks. Returns the count inserted."""
    session.add_all(chunks)
    await session.flush()
    return len(chunks)


async def semantic_search(
    session: AsyncSession,
    query_embedding: list[float],
    top_k: int = 20,
) -> Sequence[TranscriptChunk]:
    """
    HNSW-accelerated cosine similarity search.

    Returns the ``top_k`` closest transcript chunks to ``query_embedding``,
    ordered by ascending cosine distance (most similar first).
    """
    stmt = (
        select(TranscriptChunk)
        .order_by(TranscriptChunk.embedding.cosine_distance(query_embedding))
        .limit(top_k)
    )
    result = await session.execute(stmt)
    rows = result.scalars().all()
    logger.info(
        "semantic_search_complete",
        top_k=top_k,
        results_returned=len(rows),
    )
    return rows


async def get_clip_chunks(
    session: AsyncSession,
    clip_id: str,
) -> Sequence[TranscriptChunk]:
    """Retrieve all chunks for a clip, ordered chronologically."""
    stmt = (
        select(TranscriptChunk)
        .where(TranscriptChunk.clip_id == clip_id)
        .order_by(TranscriptChunk.start_time.asc())
    )
    result = await session.execute(stmt)
    return result.scalars().all()


async def search_within_clip(
    session: AsyncSession,
    clip_id: str,
    query_embedding: list[float],
    top_k: int = 10,
) -> Sequence[TranscriptChunk]:
    """
    KNN search scoped to a single clip. After picking a candidate clip,
    we drill deeper into its transcript for the most relevant moments.
    """
    stmt = (
        select(TranscriptChunk)
        .where(TranscriptChunk.clip_id == clip_id)
        .order_by(TranscriptChunk.embedding.cosine_distance(query_embedding))
        .limit(top_k)
    )
    result = await session.execute(stmt)
    return result.scalars().all()


# ---------------------------------------------------------------------------
# Context-manager helper
# ---------------------------------------------------------------------------

class Repository:
    """
    Convenience wrapper that auto-manages the session lifecycle.

    Usage::

        async with Repository() as repo:
            chunks = await repo.semantic_search(embedding, top_k=10)
    """

    def __init__(self) -> None:
        self._session: AsyncSession | None = None

    async def __aenter__(self) -> "Repository":
        factory = get_session_factory()
        self._session = factory()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:  # type: ignore[override]
        if self._session is not None:
            if exc_type is None:
                await self._session.commit()
            else:
                await self._session.rollback()
            await self._session.close()

    @property
    def session(self) -> AsyncSession:
        assert self._session is not None, "Repository used outside of context manager"
        return self._session

    # -- Delegate methods so callers don't need to pass session explicitly ----

    async def upsert_clip(self, clip: VideoClip) -> VideoClip:
        return await upsert_clip(self.session, clip)

    async def get_clip(self, clip_id: str) -> VideoClip | None:
        return await get_clip(self.session, clip_id)

    async def list_clips(self, limit: int = 50) -> Sequence[VideoClip]:
        return await list_clips(self.session, limit)

    async def delete_clip(self, clip_id: str) -> bool:
        return await delete_clip(self.session, clip_id)

    async def bulk_insert_chunks(self, chunks: list[TranscriptChunk]) -> int:
        return await bulk_insert_chunks(self.session, chunks)

    async def semantic_search(
        self, query_embedding: list[float], top_k: int = 20
    ) -> Sequence[TranscriptChunk]:
        return await semantic_search(self.session, query_embedding, top_k)

    async def get_clip_chunks(self, clip_id: str) -> Sequence[TranscriptChunk]:
        return await get_clip_chunks(self.session, clip_id)

    async def search_within_clip(
        self, clip_id: str, query_embedding: list[float], top_k: int = 10
    ) -> Sequence[TranscriptChunk]:
        return await search_within_clip(self.session, clip_id, query_embedding, top_k)

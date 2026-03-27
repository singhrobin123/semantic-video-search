"""
Ingestion pipeline orchestrator.

Coordinates the full flow: URL → transcript → chunks → embeddings → pgvector.

This is the single entry-point that the API ``/ingest`` endpoint calls.
Each step is independently testable and swappable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.db.models import TranscriptChunk, VideoClip
from app.db.repository import Repository
from app.ingestion.chunker import chunk_transcript
from app.ingestion.embedder import embed_chunks
from app.ingestion.transcriber import (
    fetch_youtube_metadata,
    fetch_youtube_transcript,
)
from app.observability.logging import get_logger

logger = get_logger(__name__)


@dataclass
class IngestionResult:
    """Summary returned to the caller after a successful ingestion."""
    clip_id: str
    title: str
    chunks_stored: int
    source_url: str


async def ingest_youtube_video(
    url_or_id: str,
    languages: list[str] | None = None,
) -> IngestionResult:
    """
    End-to-end ingestion of a YouTube video.

    Steps:
      1. Fetch transcript via ``youtube-transcript-api``.
      2. Fetch metadata (title, channel) via ``yt-dlp`` (optional).
      3. Chunk the transcript with overlap for embedding quality.
      4. Batch-embed all chunks via OpenAI.
      5. Store the ``VideoClip`` and ``TranscriptChunk`` rows in pgvector.
    """
    # 1. Transcript
    segments, meta = await fetch_youtube_transcript(url_or_id, languages)
    if not segments:
        raise ValueError(f"No transcript found for {url_or_id}")

    video_id = meta["video_id"]
    clip_id = f"yt-{video_id}"

    # 2. Metadata
    yt_meta = await fetch_youtube_metadata(video_id)
    title = yt_meta.get("title", f"YouTube Video {video_id}")

    logger.info(
        "ingestion_started",
        clip_id=clip_id,
        title=title,
        transcript_segments=len(segments),
    )

    # 3. Chunk
    chunks = chunk_transcript(segments)
    if not chunks:
        raise ValueError(f"Chunking produced no output for {clip_id}")

    # 4. Embed
    vectors = await embed_chunks(chunks)

    # 5. Store
    async with Repository() as repo:
        # Upsert the clip (idempotent — re-ingesting updates metadata)
        clip = VideoClip(
            id=clip_id,
            title=title,
            description=yt_meta.get("description", ""),
            source_url=meta["source_url"],
            duration_seconds=yt_meta.get("duration_seconds", 0),
            channel_name=yt_meta.get("channel_name", ""),
            language=meta.get("language", "en"),
        )
        await repo.upsert_clip(clip)

        # Delete old chunks if re-ingesting
        existing = await repo.get_clip_chunks(clip_id)
        if existing:
            logger.info("re_ingestion_clearing_old_chunks", clip_id=clip_id, old_count=len(existing))
            await repo.delete_clip(clip_id)
            await repo.upsert_clip(clip)

        # Build chunk ORM objects
        db_chunks = [
            TranscriptChunk(
                clip_id=clip_id,
                segment_text=c.text,
                start_time=c.start_time,
                end_time=c.end_time,
                chunk_index=c.chunk_index,
                embedding=vectors[i],
            )
            for i, c in enumerate(chunks)
        ]
        stored = await repo.bulk_insert_chunks(db_chunks)

    result = IngestionResult(
        clip_id=clip_id,
        title=title,
        chunks_stored=stored,
        source_url=meta["source_url"],
    )

    logger.info(
        "ingestion_complete",
        clip_id=clip_id,
        title=title,
        chunks_stored=stored,
    )
    return result


async def ingest_manual_transcript(
    clip_id: str,
    title: str,
    transcript_entries: list[dict[str, Any]],
    description: str = "",
    source_url: str = "",
) -> IngestionResult:
    """
    Ingest a manually provided transcript (for non-YouTube sources).

    ``transcript_entries`` should be a list of dicts with keys:
      - ``text`` (str): The transcript text
      - ``start`` (float): Start time in seconds
      - ``duration`` (float): Duration in seconds
    """
    from app.ingestion.transcriber import TranscriptSegment

    segments = [
        TranscriptSegment(
            text=e["text"],
            start=e["start"],
            duration=e.get("duration", 5.0),
        )
        for e in transcript_entries
    ]

    chunks = chunk_transcript(segments)
    if not chunks:
        raise ValueError(f"Chunking produced no output for {clip_id}")

    vectors = await embed_chunks(chunks)

    async with Repository() as repo:
        clip = VideoClip(
            id=clip_id,
            title=title,
            description=description,
            source_url=source_url,
        )
        await repo.upsert_clip(clip)

        db_chunks = [
            TranscriptChunk(
                clip_id=clip_id,
                segment_text=c.text,
                start_time=c.start_time,
                end_time=c.end_time,
                chunk_index=c.chunk_index,
                embedding=vectors[i],
            )
            for i, c in enumerate(chunks)
        ]
        stored = await repo.bulk_insert_chunks(db_chunks)

    return IngestionResult(
        clip_id=clip_id,
        title=title,
        chunks_stored=stored,
        source_url=source_url,
    )

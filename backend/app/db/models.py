"""
SQLAlchemy ORM models for pgvector-backed video transcript storage.

Design decisions:
  - ``VideoClip`` stores per-video metadata (title, source URL, duration).
  - ``TranscriptChunk`` stores individual transcript segments with their
    1536-dimensional embedding vector and a timestamp for seek-to-moment UX.
  - The HNSW index is created via ``init_db()`` for sub-millisecond ANN
    searches across millions of vectors.
"""

from __future__ import annotations

from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class VideoClip(Base):
    """A video that has been ingested into the search engine."""

    __tablename__ = "video_clips"

    id = Column(String, primary_key=True)                        # e.g. "yt-dQw4w9WgXcQ"
    title = Column(String(512), nullable=False)
    description = Column(Text, nullable=True)
    source_url = Column(String(2048), nullable=True)             # Original YouTube / upload URL
    duration_seconds = Column(Integer, nullable=True)
    channel_name = Column(String(256), nullable=True)
    language = Column(String(10), default="en")
    ingested_at = Column(DateTime, default=func.now(), nullable=False)

    chunks = relationship(
        "TranscriptChunk",
        back_populates="clip",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<VideoClip id={self.id!r} title={self.title[:40]!r}>"


class TranscriptChunk(Base):
    """A single segment of a video's transcript, stored with its embedding."""

    __tablename__ = "transcript_chunks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    clip_id = Column(
        String,
        ForeignKey("video_clips.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    segment_text = Column(Text, nullable=False)
    start_time = Column(Float, nullable=False)                   # Seconds into the video
    end_time = Column(Float, nullable=True)
    chunk_index = Column(Integer, nullable=False, default=0)     # Ordering within clip
    embedding = Column(Vector(1536), nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)

    clip = relationship("VideoClip", back_populates="chunks")

    def __repr__(self) -> str:
        return (
            f"<TranscriptChunk clip={self.clip_id!r} "
            f"t={self.start_time:.1f}s text={self.segment_text[:30]!r}>"
        )

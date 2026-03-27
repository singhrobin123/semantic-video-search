"""
API request/response schemas.

Every API response is wrapped in a consistent ``APIEnvelope`` so the
frontend never has to guess the shape of error vs. success payloads.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator


# ── Request schemas ──────────────────────────────────────────────────────

class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)

    @field_validator("query", mode="before")
    @classmethod
    def strip_query(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip()
        return v


class IngestYouTubeRequest(BaseModel):
    url: str = Field(..., description="YouTube URL or video ID")
    languages: list[str] = Field(default=["en"])


class IngestManualRequest(BaseModel):
    clip_id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    description: str = Field(default="")
    source_url: str = Field(default="")
    transcript: list[dict[str, Any]] = Field(
        ...,
        description="List of {text, start, duration} objects",
    )


# ── Response schemas ─────────────────────────────────────────────────────

class APIEnvelope(BaseModel):
    """
    Standardized API response wrapper.

    Every endpoint returns this shape, guaranteeing the frontend can always
    check ``success`` before accessing ``data``, and ``error`` is always a
    human-readable string (never a raw traceback).
    """
    success: bool
    data: Any | None = None
    error: str | None = None


class ClipSummary(BaseModel):
    id: str
    title: str
    source_url: str | None = None
    duration_seconds: int | None = None
    channel_name: str | None = None
    language: str | None = None
    chunk_count: int = 0


class IngestionResponse(BaseModel):
    clip_id: str
    title: str
    chunks_stored: int
    source_url: str

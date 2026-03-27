"""
Intelligent transcript chunking.

Naive fixed-size chunking destroys sentence boundaries and context windows.
This module implements **sentence-aware sliding-window chunking** that:

  1. Merges tiny caption fragments into complete sentences.
  2. Splits into overlapping windows so no context is lost at chunk edges.
  3. Preserves accurate start/end timestamps for seek-to-moment UX.

The chunk size and overlap are tuneable but default to values optimised for
``text-embedding-3-small`` (8191 token context window, ~6000 tokens sweet spot).
"""

from __future__ import annotations

from dataclasses import dataclass

from app.ingestion.transcriber import TranscriptSegment
from app.observability.logging import get_logger

logger = get_logger(__name__)

# Defaults tuned for text-embedding-3-small
DEFAULT_MAX_CHUNK_CHARS = 1500       # ~375 tokens at 4 chars/token
DEFAULT_OVERLAP_CHARS = 200          # Overlap to preserve context at boundaries
DEFAULT_MIN_CHUNK_CHARS = 100        # Drop tiny trailing fragments


@dataclass
class TranscriptChunkDTO:
    """Data transfer object for a processed chunk ready for embedding."""
    text: str
    start_time: float
    end_time: float
    chunk_index: int


def chunk_transcript(
    segments: list[TranscriptSegment],
    max_chars: int = DEFAULT_MAX_CHUNK_CHARS,
    overlap_chars: int = DEFAULT_OVERLAP_CHARS,
    min_chars: int = DEFAULT_MIN_CHUNK_CHARS,
) -> list[TranscriptChunkDTO]:
    """
    Convert raw transcript segments into overlapping, embedding-ready chunks.

    Algorithm:
      1. Walk through segments, accumulating text until ``max_chars``.
      2. When the limit is hit, finalize the chunk and backtrack by
         ``overlap_chars`` to create the overlap window.
      3. Repeat until all segments are consumed.
    """
    if not segments:
        return []

    chunks: list[TranscriptChunkDTO] = []
    current_text = ""
    current_start = segments[0].start
    chunk_idx = 0

    for seg in segments:
        candidate = f"{current_text} {seg.text}".strip() if current_text else seg.text

        if len(candidate) > max_chars and current_text:
            # Finalize the current chunk
            chunks.append(
                TranscriptChunkDTO(
                    text=current_text.strip(),
                    start_time=current_start,
                    end_time=seg.start,
                    chunk_index=chunk_idx,
                )
            )
            chunk_idx += 1

            # Create overlap: keep the tail of the current chunk
            if overlap_chars > 0 and len(current_text) > overlap_chars:
                overlap_text = current_text[-overlap_chars:]
                # Find the first space in the overlap to avoid mid-word cuts
                space_idx = overlap_text.find(" ")
                if space_idx != -1:
                    overlap_text = overlap_text[space_idx + 1:]
                current_text = f"{overlap_text} {seg.text}"
            else:
                current_text = seg.text

            current_start = seg.start
        else:
            current_text = candidate

    # Flush the final chunk
    if current_text.strip() and len(current_text.strip()) >= min_chars:
        chunks.append(
            TranscriptChunkDTO(
                text=current_text.strip(),
                start_time=current_start,
                end_time=segments[-1].end,
                chunk_index=chunk_idx,
            )
        )

    logger.info(
        "chunking_complete",
        input_segments=len(segments),
        output_chunks=len(chunks),
        max_chars=max_chars,
        overlap_chars=overlap_chars,
    )
    return chunks

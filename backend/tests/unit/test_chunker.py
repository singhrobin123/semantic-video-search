"""
Unit tests for the transcript chunking algorithm.

These tests verify edge cases: empty input, single-segment videos,
long transcripts, and overlap correctness.
"""

import pytest
from app.ingestion.chunker import chunk_transcript, DEFAULT_MAX_CHUNK_CHARS
from app.ingestion.transcriber import TranscriptSegment


def _make_segments(texts: list[str], gap: float = 5.0) -> list[TranscriptSegment]:
    """Helper to build segment lists with auto-incrementing timestamps."""
    return [
        TranscriptSegment(text=t, start=i * gap, duration=gap)
        for i, t in enumerate(texts)
    ]


def test_empty_input_returns_empty():
    assert chunk_transcript([]) == []


def test_single_short_segment():
    segs = _make_segments(["Hello, welcome to the talk."])
    chunks = chunk_transcript(segs, min_chars=5)
    assert len(chunks) == 1
    assert chunks[0].text == "Hello, welcome to the talk."
    assert chunks[0].chunk_index == 0


def test_respects_max_chars_boundary():
    """Multiple short segments should be grouped without wildly exceeding max_chars."""
    # Each segment is ~50 chars, so chunks should contain ~4 segments each
    segs = _make_segments(["short words here now. " * 2] * 20)
    chunks = chunk_transcript(segs, max_chars=200, overlap_chars=0, min_chars=10)
    for chunk in chunks:
        # Allow one extra segment overshoot (the segment that triggered the split)
        assert len(chunk.text) <= 260, f"Chunk too large: {len(chunk.text)} chars"


def test_overlap_creates_redundancy():
    """With overlap, consecutive chunks should share some text."""
    segs = _make_segments(
        ["Alpha bravo charlie. " * 10, "Delta echo foxtrot. " * 10],
        gap=60.0,
    )
    chunks = chunk_transcript(segs, max_chars=150, overlap_chars=50, min_chars=10)
    if len(chunks) >= 2:
        # The end of chunk N should overlap with the start of chunk N+1
        tail = chunks[0].text[-30:]
        head = chunks[1].text[:80]
        # At least some words from the tail should appear in the head
        shared_words = set(tail.split()) & set(head.split())
        assert len(shared_words) > 0, "Overlap should create shared content"


def test_chunk_indices_are_sequential():
    segs = _make_segments(["Test segment. " * 20] * 5)
    chunks = chunk_transcript(segs, max_chars=200, overlap_chars=0, min_chars=10)
    for i, chunk in enumerate(chunks):
        assert chunk.chunk_index == i


def test_timestamps_are_monotonically_increasing():
    segs = _make_segments(["Segment. " * 15] * 8, gap=10.0)
    chunks = chunk_transcript(segs, max_chars=200, overlap_chars=0, min_chars=10)
    for i in range(1, len(chunks)):
        assert chunks[i].start_time >= chunks[i - 1].start_time


def test_tiny_trailing_fragment_is_dropped():
    """Fragments below min_chars should be dropped."""
    segs = _make_segments(["Long content here. " * 20, "Hi"])
    chunks = chunk_transcript(segs, max_chars=200, overlap_chars=0, min_chars=50)
    # The "Hi" fragment alone is only 2 chars — should be dropped
    for chunk in chunks:
        assert len(chunk.text) >= 50

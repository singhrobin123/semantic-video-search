"""
Unit tests for the three-step agentic tool pattern.

These tests verify the tool logic in complete isolation — no real DB,
no real OpenAI API calls.  Every external dependency is mocked.
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
@patch("app.agent.tools.get_embeddings")
@patch("app.agent.tools.Repository")
async def test_get_initial_candidates_groups_by_clip(mock_repo_cls, mock_get_emb):
    """Tool 1 should group transcript chunks by clip_id."""
    from app.agent.tools import get_initial_candidates

    # Mock embeddings
    mock_emb = AsyncMock()
    mock_emb.aembed_query = AsyncMock(return_value=[0.1] * 1536)
    mock_get_emb.return_value = mock_emb

    # Mock DB chunks from two different clips
    chunk1 = MagicMock(clip_id="clip-A", segment_text="Hello world")
    chunk2 = MagicMock(clip_id="clip-A", segment_text="More from clip A")
    chunk3 = MagicMock(clip_id="clip-B", segment_text="Different clip")

    mock_repo = AsyncMock()
    mock_repo.semantic_search = AsyncMock(return_value=[chunk1, chunk2, chunk3])
    mock_repo.__aenter__ = AsyncMock(return_value=mock_repo)
    mock_repo.__aexit__ = AsyncMock(return_value=False)
    mock_repo_cls.return_value = mock_repo

    result = json.loads(await get_initial_candidates("test question"))

    assert len(result) == 2
    clip_a = next(r for r in result if r["clip_id"] == "clip-A")
    assert len(clip_a["transcript_segments"]) == 2
    mock_emb.aembed_query.assert_awaited_once_with("test question")


@pytest.mark.asyncio
@patch("app.agent.tools.get_embeddings")
@patch("app.agent.tools.Repository")
async def test_get_initial_candidates_empty_corpus(mock_repo_cls, mock_get_emb):
    """Tool 1 should return empty list when corpus has no matches."""
    from app.agent.tools import get_initial_candidates

    mock_emb = AsyncMock()
    mock_emb.aembed_query = AsyncMock(return_value=[0.1] * 1536)
    mock_get_emb.return_value = mock_emb

    mock_repo = AsyncMock()
    mock_repo.semantic_search = AsyncMock(return_value=[])
    mock_repo.__aenter__ = AsyncMock(return_value=mock_repo)
    mock_repo.__aexit__ = AsyncMock(return_value=False)
    mock_repo_cls.return_value = mock_repo

    result = json.loads(await get_initial_candidates("meaning of life"))
    assert result == []


@pytest.mark.asyncio
@patch("app.agent.tools.get_embeddings")
@patch("app.agent.tools.Repository")
async def test_examine_clip_deeper_populates_cache(mock_repo_cls, mock_get_emb):
    """Tool 2 should populate the clip cache for downstream Tool 3 access."""
    from app.agent.tools import examine_clip_deeper, _clip_cache, reset_clip_cache

    reset_clip_cache()

    mock_emb = AsyncMock()
    mock_emb.aembed_query = AsyncMock(return_value=[0.1] * 1536)
    mock_get_emb.return_value = mock_emb

    mock_clip = MagicMock()
    mock_clip.title = "Engineering All-Hands"
    mock_clip.description = "A discussion about scaling"

    mock_moment = MagicMock()
    mock_moment.segment_text = "We discussed database scaling"
    mock_moment.start_time = 45.0

    mock_repo = AsyncMock()
    mock_repo.get_clip = AsyncMock(return_value=mock_clip)
    mock_repo.search_within_clip = AsyncMock(return_value=[mock_moment])
    mock_repo.__aenter__ = AsyncMock(return_value=mock_repo)
    mock_repo.__aexit__ = AsyncMock(return_value=False)
    mock_repo_cls.return_value = mock_repo

    result = json.loads(await examine_clip_deeper("clip-X", "database scaling"))

    assert result["clip_id"] == "clip-X"
    assert result["title"] == "Engineering All-Hands"
    assert "database scaling" in result["transcript"]
    assert "clip-X" in _clip_cache
    assert len(_clip_cache["clip-X"]["moments"]) == 1


@pytest.mark.asyncio
@patch("app.agent.tools.get_embeddings")
@patch("app.agent.tools.Repository")
async def test_examine_clip_deeper_missing_clip(mock_repo_cls, mock_get_emb):
    """Tool 2 should return an error when the clip doesn't exist."""
    from app.agent.tools import examine_clip_deeper

    mock_emb = AsyncMock()
    mock_emb.aembed_query = AsyncMock(return_value=[0.1] * 1536)
    mock_get_emb.return_value = mock_emb

    mock_repo = AsyncMock()
    mock_repo.get_clip = AsyncMock(return_value=None)
    mock_repo.__aenter__ = AsyncMock(return_value=mock_repo)
    mock_repo.__aexit__ = AsyncMock(return_value=False)
    mock_repo_cls.return_value = mock_repo

    result = json.loads(await examine_clip_deeper("nonexistent", "question"))
    assert "error" in result


@pytest.mark.asyncio
async def test_get_clip_quotes_from_cache():
    """Tool 3 should return quotes from the in-memory clip cache."""
    from app.agent.tools import get_clip_quotes, _clip_cache, reset_clip_cache

    reset_clip_cache()

    _clip_cache["test-clip"] = {
        "clip_id": "test-clip",
        "title": "Test",
        "description": "",
        "moments": [
            {"type": "transcript", "start_time": 120.0, "contents": "Second quote"},
            {"type": "transcript", "start_time": 30.0, "contents": "First quote"},
        ],
    }

    result = json.loads(await get_clip_quotes("test-clip"))

    assert len(result) == 2
    # Should be sorted chronologically
    assert result[0]["quote_timestamp"] == 30.0
    assert result[1]["quote_timestamp"] == 120.0
    assert result[0]["quote"] == "First quote"


@pytest.mark.asyncio
async def test_reset_clip_cache_clears_state():
    """Cache reset should prevent cross-request data leakage."""
    from app.agent.tools import _clip_cache, reset_clip_cache

    _clip_cache["stale-clip"] = {"moments": []}
    assert "stale-clip" in _clip_cache

    reset_clip_cache()
    assert len(_clip_cache) == 0

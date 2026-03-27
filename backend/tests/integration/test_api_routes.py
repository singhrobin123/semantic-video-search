"""
Integration tests for the FastAPI API layer.

Uses ``httpx.AsyncClient`` with the real FastAPI app (but mocked
downstream dependencies) to validate HTTP status codes, response shapes,
and the API envelope contract.
"""

import json
import pytest
from unittest.mock import AsyncMock, patch

from httpx import ASGITransport, AsyncClient


@pytest.fixture
def app():
    """Import the app after env vars are set by conftest."""
    from app.main import app
    return app


@pytest.mark.asyncio
@patch("app.api.routes._agent_executor")
async def test_search_returns_envelope(mock_executor, app):
    """POST /api/v1/search should return a valid APIEnvelope."""
    mock_executor.ainvoke = AsyncMock(return_value={
        "final_result": {
            "results": [{
                "clip_id": "test-clip",
                "question": "test",
                "answer": "Test answer",
                "relevant_quotes": [],
                "related_questions": [],
            }]
        }
    })

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.post(
            "/api/v1/search",
            json={"query": "What is scaling?"},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert "results" in body["data"]


@pytest.mark.asyncio
async def test_search_empty_query_rejected(app):
    """Empty query should be rejected by Pydantic validation."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.post("/api/v1/search", json={"query": ""})

    assert resp.status_code == 422  # Pydantic validation error


@pytest.mark.asyncio
async def test_health_check(app):
    """GET /health should always return 200."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.get("/health")

    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"


@pytest.mark.asyncio
@patch("app.api.routes.Repository")
async def test_library_list(mock_repo_cls, app):
    """GET /api/v1/library should return the clips envelope."""
    mock_repo = AsyncMock()
    mock_repo.list_clips = AsyncMock(return_value=[])
    mock_repo.__aenter__ = AsyncMock(return_value=mock_repo)
    mock_repo.__aexit__ = AsyncMock(return_value=False)
    mock_repo_cls.return_value = mock_repo

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.get("/api/v1/library")

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["clips"] == []

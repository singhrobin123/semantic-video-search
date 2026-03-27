"""
Shared pytest fixtures and environment setup.

Sets dummy API keys so LangChain modules can be imported without crashing
during test collection (they validate key presence at import time).
"""

import os

os.environ.setdefault(
    "OPENAI_API_KEY",
    "sk-test-mock-key-for-pytest-collection-only",
)
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://user:password@localhost:5432/vectordb")
os.environ.setdefault("LLM_PROVIDER", "openai")
os.environ.setdefault("APP_ENV", "development")


import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.fixture
def mock_repository():
    """Provide a mocked Repository context manager."""
    repo = AsyncMock()
    repo.__aenter__ = AsyncMock(return_value=repo)
    repo.__aexit__ = AsyncMock(return_value=False)
    return repo


@pytest.fixture
def mock_embeddings():
    """Provide a mocked OpenAI embeddings client."""
    emb = AsyncMock()
    emb.aembed_query = AsyncMock(return_value=[0.1] * 1536)
    emb.aembed_documents = AsyncMock(
        side_effect=lambda texts: [[0.1] * 1536 for _ in texts]
    )
    return emb

"""
Multi-provider LLM abstraction.

This module provides:
  - A unified ``get_chat_model()`` that returns a LangChain-compatible chat
    model regardless of the underlying provider.
  - A unified ``get_embeddings()`` for embedding generation.
  - Provider switching via a single env var (``LLM_PROVIDER``).
"""

from __future__ import annotations

from functools import lru_cache

from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from app.config import LLMProvider, get_settings
from app.observability.logging import get_logger

logger = get_logger(__name__)


def get_chat_model(
    temperature: float | None = None,
    model: str | None = None,
) -> BaseChatModel:
    """
    Return a chat model for the configured provider.

    Parameters override the global defaults from Settings, allowing
    per-call tuning (e.g. temperature=0 for deterministic extraction).
    """
    settings = get_settings()
    _temperature = temperature if temperature is not None else settings.llm_temperature
    _model = model or settings.llm_model

    if settings.llm_provider == LLMProvider.ANTHROPIC:
        try:
            from langchain_anthropic import ChatAnthropic
        except ImportError as exc:
            raise ImportError(
                "langchain-anthropic is required when LLM_PROVIDER=anthropic. "
                "Install it with: pip install langchain-anthropic"
            ) from exc

        logger.info("llm_provider_init", provider="anthropic", model=_model)
        return ChatAnthropic(
            model=_model,
            temperature=_temperature,
            api_key=settings.anthropic_api_key,
            max_tokens=4096,
        )

    # Default: OpenAI
    logger.info("llm_provider_init", provider="openai", model=_model)
    return ChatOpenAI(
        model=_model,
        temperature=_temperature,
        api_key=settings.openai_api_key,
    )


@lru_cache(maxsize=1)
def get_embeddings() -> OpenAIEmbeddings:
    """
    Return a cached embedding client.

    Note: Even when the chat model is Anthropic, we use OpenAI embeddings
    because Anthropic does not offer an embedding API.  This mirrors the
    enterprise pattern where embedding and generation providers may differ.
    """
    settings = get_settings()
    return OpenAIEmbeddings(
        model=settings.embedding_model,
        api_key=settings.openai_api_key,
    )

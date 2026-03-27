"""
Centralized configuration via Pydantic Settings.

All environment variables are validated at startup. Missing required values
cause an immediate, developer-friendly error — never a cryptic KeyError
buried three stack frames deep in a LangChain constructor.
"""

from __future__ import annotations

import json
from enum import Enum
from functools import lru_cache
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMProvider(str, Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"


class AppEnv(str, Enum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class Settings(BaseSettings):
    """
    Single source of truth for every tuneable parameter.
    Values are loaded from environment variables (or a .env file).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # --- LLM Providers -------------------------------------------------------
    openai_api_key: str = Field(default="", description="OpenAI API key")
    anthropic_api_key: str = Field(default="", description="Anthropic API key")

    # --- LLM Configuration ---------------------------------------------------
    llm_provider: LLMProvider = Field(default=LLMProvider.OPENAI)
    llm_model: str = Field(default="gpt-4o-mini")
    llm_temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    embedding_model: str = Field(default="text-embedding-3-small")

    # --- Database ------------------------------------------------------------
    database_url: str = Field(
        default="postgresql+asyncpg://user:password@localhost:5432/vectordb"
    )
    db_pool_size: int = Field(default=10, ge=1)
    db_max_overflow: int = Field(default=20, ge=0)

    # --- Vector Search Tuning ------------------------------------------------
    vector_search_top_k: int = Field(default=20, ge=1)
    vector_search_rerank_top_k: int = Field(default=5, ge=1)
    hnsw_m: int = Field(default=16, ge=2)
    hnsw_ef_construction: int = Field(default=64, ge=16)

    # --- Application ---------------------------------------------------------
    app_env: AppEnv = Field(default=AppEnv.DEVELOPMENT)
    app_log_level: str = Field(default="INFO")
    app_cors_origins: List[str] = Field(
        default=["http://localhost:8501", "http://localhost:3000"]
    )

    @field_validator("app_cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str | List[str]) -> List[str]:
        if isinstance(v, str):
            return json.loads(v)
        return v

    @property
    def is_production(self) -> bool:
        return self.app_env == AppEnv.PRODUCTION

    @property
    def embedding_dimensions(self) -> int:
        """Return the vector dimensionality for the configured embedding model."""
        dims = {
            "text-embedding-3-small": 1536,
            "text-embedding-3-large": 3072,
            "text-embedding-ada-002": 1536,
        }
        return dims.get(self.embedding_model, 1536)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached singleton — parsed once, reused everywhere."""
    return Settings()

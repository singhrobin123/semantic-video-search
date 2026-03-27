"""
Application entry-point.

Bootstraps logging, database connections, CORS, request-tracing middleware,
and the API router.  Uses the modern FastAPI ``lifespan`` context manager
instead of the deprecated ``on_event`` hooks.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import routes
from app.api.middleware import RequestTracingMiddleware
from app.config import get_settings
from app.db.session import dispose_engine, init_db
from app.observability.logging import get_logger, setup_logging

setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle hook."""
    logger.info("application_starting", env=get_settings().app_env.value)
    await init_db()
    logger.info("database_initialized")
    yield
    await dispose_engine()
    logger.info("application_shutdown_complete")


app = FastAPI(
    title="Semantic Video Search Engine",
    description=(
        "Production-grade agentic RAG system for semantic video transcript search. "
        "Powered by LangGraph, pgvector, and multi-provider LLM support."
    ),
    version="2.0.0",
    lifespan=lifespan,
)

# ── Middleware (order matters — outermost first) ─────────────────────────
settings = get_settings()

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.app_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestTracingMiddleware)

# ── Routes ───────────────────────────────────────────────────────────────
app.include_router(routes.router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    """Liveness probe for container orchestrators."""
    return {"status": "healthy", "version": "2.0.0"}

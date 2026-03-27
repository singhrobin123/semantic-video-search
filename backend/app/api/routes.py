"""
API route definitions.

All endpoints return an ``APIEnvelope`` so the frontend always sees a
consistent ``{success, data, error}`` shape — even on 500 errors.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from langchain_core.messages import HumanMessage, SystemMessage

from app.agent.graph import SYSTEM_PROMPT, build_graph
from app.agent.tools import reset_clip_cache
from app.api.schemas import (
    APIEnvelope,
    ClipSummary,
    IngestManualRequest,
    IngestYouTubeRequest,
    IngestionResponse,
    SearchRequest,
)
from app.db.repository import Repository
from app.observability.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()

# Compile the graph once — reused across all requests
_agent_executor = build_graph()


# ── Search ───────────────────────────────────────────────────────────────

@router.post("/search", response_model=APIEnvelope)
async def semantic_search(request: SearchRequest):
    """
    Agentic semantic video search.

    The LangGraph agent autonomously decides which tools to call
    (initial candidates → deep examination → quote extraction) and
    in what order.
    """
    # Reset per-request clip cache to prevent cross-request leakage
    reset_clip_cache()

    try:
        initial_state = {
            "messages": [
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=f"<question>{request.query}</question>"),
            ],
            "query": request.query,
            "candidates": [],
            "examined_clips": [],
            "final_result": {},
        }

        state = await _agent_executor.ainvoke(initial_state)
        result_data = state.get("final_result", {})

        return APIEnvelope(success=True, data=result_data)

    except Exception:
        logger.exception("agent_orchestration_failed")
        return JSONResponse(
            status_code=500,
            content=APIEnvelope(
                success=False,
                error="Internal AI Processing Error. Please try again later.",
            ).model_dump(),
        )


# ── Ingestion ────────────────────────────────────────────────────────────

@router.post("/ingest/youtube", response_model=APIEnvelope)
async def ingest_youtube(request: IngestYouTubeRequest):
    """
    Ingest a YouTube video: fetch transcript → chunk → embed → store.
    """
    from app.ingestion.pipeline import ingest_youtube_video

    try:
        result = await ingest_youtube_video(request.url, request.languages)
        return APIEnvelope(
            success=True,
            data=IngestionResponse(
                clip_id=result.clip_id,
                title=result.title,
                chunks_stored=result.chunks_stored,
                source_url=result.source_url,
            ).model_dump(),
        )
    except ValueError as exc:
        return JSONResponse(
            status_code=400,
            content=APIEnvelope(success=False, error=str(exc)).model_dump(),
        )
    except Exception:
        logger.exception("youtube_ingestion_failed")
        return JSONResponse(
            status_code=500,
            content=APIEnvelope(
                success=False,
                error="Failed to ingest YouTube video. Check logs for details.",
            ).model_dump(),
        )


@router.post("/ingest/manual", response_model=APIEnvelope)
async def ingest_manual(request: IngestManualRequest):
    """
    Ingest a manually provided transcript (for non-YouTube sources).
    """
    from app.ingestion.pipeline import ingest_manual_transcript

    try:
        result = await ingest_manual_transcript(
            clip_id=request.clip_id,
            title=request.title,
            transcript_entries=request.transcript,
            description=request.description,
            source_url=request.source_url,
        )
        return APIEnvelope(
            success=True,
            data=IngestionResponse(
                clip_id=result.clip_id,
                title=result.title,
                chunks_stored=result.chunks_stored,
                source_url=result.source_url,
            ).model_dump(),
        )
    except ValueError as exc:
        return JSONResponse(
            status_code=400,
            content=APIEnvelope(success=False, error=str(exc)).model_dump(),
        )
    except Exception:
        logger.exception("manual_ingestion_failed")
        return JSONResponse(
            status_code=500,
            content=APIEnvelope(
                success=False, error="Ingestion failed."
            ).model_dump(),
        )


# ── Library Management ───────────────────────────────────────────────────

@router.get("/library", response_model=APIEnvelope)
async def list_library():
    """List all ingested video clips with chunk counts."""
    try:
        async with Repository() as repo:
            clips = await repo.list_clips()
            summaries = []
            for clip in clips:
                chunks = await repo.get_clip_chunks(clip.id)
                summaries.append(
                    ClipSummary(
                        id=clip.id,
                        title=clip.title,
                        source_url=clip.source_url,
                        duration_seconds=clip.duration_seconds,
                        channel_name=clip.channel_name,
                        language=clip.language,
                        chunk_count=len(chunks),
                    ).model_dump()
                )
        return APIEnvelope(success=True, data={"clips": summaries})
    except Exception:
        logger.exception("list_library_failed")
        return JSONResponse(
            status_code=500,
            content=APIEnvelope(
                success=False, error="Failed to list library."
            ).model_dump(),
        )


@router.delete("/library/{clip_id}", response_model=APIEnvelope)
async def delete_clip(clip_id: str):
    """Delete a clip and all its transcript chunks."""
    try:
        async with Repository() as repo:
            deleted = await repo.delete_clip(clip_id)
        if not deleted:
            return JSONResponse(
                status_code=404,
                content=APIEnvelope(
                    success=False, error=f"Clip '{clip_id}' not found."
                ).model_dump(),
            )
        return APIEnvelope(success=True, data={"deleted": clip_id})
    except Exception:
        logger.exception("delete_clip_failed")
        return JSONResponse(
            status_code=500,
            content=APIEnvelope(
                success=False, error="Failed to delete clip."
            ).model_dump(),
        )

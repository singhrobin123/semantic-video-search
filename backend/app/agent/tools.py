"""
Agent tools — the three-step retrieval pattern.

Three purpose-built tools that the LLM calls autonomously:

  1. ``get_initial_candidates`` — broad KNN sweep across the entire library.
  2. ``examine_clip_deeper``   — scoped KNN within a single clip for fine-
                                  grained moment extraction.
  3. ``get_clip_quotes``       — retrieve chronologically-sorted quotes
                                  with timestamps for the final answer.

The LLM agent decides *which* tools to call and *in what order*, making
this a true agentic (not linear-chain) architecture.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from app.config import get_settings
from app.db.repository import Repository
from app.llm.provider import get_embeddings
from app.observability.logging import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# In-memory clip cache (per-request).
# Avoids redundant DB round-trips when the agent calls multiple tools for
# the same clip within a single query lifecycle.
# ---------------------------------------------------------------------------
_clip_cache: dict[str, dict[str, Any]] = {}


def reset_clip_cache() -> None:
    """Clear the cache between requests to prevent cross-request leakage."""
    _clip_cache.clear()


# ---------------------------------------------------------------------------
# Tool 1: Initial KNN Candidate Retrieval
# ---------------------------------------------------------------------------

async def get_initial_candidates(question: str) -> str:
    """
    Broad cosine-similarity sweep across the entire transcript corpus.

    Returns a JSON-serialisable list of ``{clip_id, transcript_segments}``
    grouped by clip.  The agent uses this to decide which clips deserve
    deeper examination.
    """
    import json

    settings = get_settings()
    embeddings = get_embeddings()
    query_vector = await embeddings.aembed_query(question)

    async with Repository() as repo:
        chunks = await repo.semantic_search(
            query_vector, top_k=settings.vector_search_top_k
        )

    if not chunks:
        logger.info("get_initial_candidates_empty", question=question[:80])
        return json.dumps([])

    # Group by clip_id
    grouped: dict[str, list[str]] = defaultdict(list)
    for chunk in chunks:
        grouped[chunk.clip_id].append(chunk.segment_text)

    candidates = [
        {"clip_id": cid, "transcript_segments": segments}
        for cid, segments in grouped.items()
    ]

    logger.info(
        "get_initial_candidates_complete",
        question=question[:80],
        num_clips=len(candidates),
        total_chunks=len(chunks),
    )
    return json.dumps(candidates, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Tool 2: Deep-dive Clip Examination
# ---------------------------------------------------------------------------

async def examine_clip_deeper(clip_id: str, question: str) -> str:
    """
    Scoped KNN search within a single clip.

    Once the agent picks a promising clip, it calls this tool to get the
    clip's metadata plus the most question-relevant transcript moments.
    Results are cached so ``get_clip_quotes`` can reuse them.
    """
    import json

    embeddings = get_embeddings()
    query_vector = await embeddings.aembed_query(question)

    async with Repository() as repo:
        clip = await repo.get_clip(clip_id)
        if clip is None:
            return json.dumps({"error": f"Clip {clip_id} not found"})

        moments = await repo.search_within_clip(clip_id, query_vector, top_k=10)

    # Populate the clip cache for downstream tool access
    _clip_cache[clip_id] = {
        "clip_id": clip_id,
        "title": clip.title,
        "description": clip.description or "",
        "moments": [
            {
                "type": "transcript",
                "start_time": m.start_time,
                "contents": m.segment_text,
            }
            for m in moments
        ],
    }

    payload = {
        "clip_id": clip_id,
        "title": clip.title,
        "description": clip.description or "",
        "transcript": " ".join(m.segment_text for m in moments),
    }

    logger.info(
        "examine_clip_deeper_complete",
        clip_id=clip_id,
        question=question[:80],
        moments_found=len(moments),
    )
    return json.dumps(payload, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Tool 3: Final Quote Extraction
# ---------------------------------------------------------------------------

async def get_clip_quotes(clip_id: str) -> str:
    """
    Retrieve chronologically-sorted transcript quotes with timestamps.

    After the agent has decided on the best clip and formulated an answer,
    it calls this to get the precise timestamped evidence for citation.
    """
    import json

    cached = _clip_cache.get(clip_id)
    if not cached or not cached.get("moments"):
        # Fallback: fetch from DB if cache miss
        async with Repository() as repo:
            all_chunks = await repo.get_clip_chunks(clip_id)

        quotes = [
            {
                "quote": c.segment_text,
                "quote_timestamp": c.start_time,
            }
            for c in all_chunks
        ]
    else:
        quotes = [
            {
                "quote": m["contents"],
                "quote_timestamp": m["start_time"],
            }
            for m in cached["moments"]
            if m["type"] == "transcript"
        ]

    # Sort chronologically
    quotes.sort(key=lambda q: q["quote_timestamp"])

    logger.info(
        "get_clip_quotes_complete",
        clip_id=clip_id,
        num_quotes=len(quotes),
    )
    return json.dumps(quotes, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Tool definitions for LangGraph tool-calling node
# ---------------------------------------------------------------------------

def get_tool_definitions() -> list[dict[str, Any]]:
    """
    Return OpenAI-compatible function/tool definitions.

    These are bound to the LLM via ``.bind_tools()`` so the model can
    autonomously decide which tool to invoke at each step.
    """
    return [
        {
            "type": "function",
            "function": {
                "name": "get_initial_candidates",
                "description": (
                    "Get initial candidate video clips that could answer the "
                    "user's question. Returns clip IDs and transcript segments. "
                    "Always call this first."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "question": {
                            "type": "string",
                            "description": "The user's original question",
                        }
                    },
                    "required": ["question"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "examine_clip_deeper",
                "description": (
                    "Get detailed information about a specific clip including "
                    "its title, description, and a fuller transcript context. "
                    "Call this for each promising candidate clip."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "clip_id": {
                            "type": "string",
                            "description": "The ID of the candidate clip to examine",
                        },
                        "question": {
                            "type": "string",
                            "description": "The original question from the user",
                        },
                    },
                    "required": ["clip_id", "question"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_clip_quotes",
                "description": (
                    "After determining the best clip, get its timestamped "
                    "transcript quotes for the final answer citations."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "clip_id": {
                            "type": "string",
                            "description": "The ID of the clip to get quotes from",
                        }
                    },
                    "required": ["clip_id"],
                },
            },
        },
    ]


# Dispatch map for the tool-execution node
TOOL_DISPATCH = {
    "get_initial_candidates": get_initial_candidates,
    "get_clip_quotes": get_clip_quotes,
    "examine_clip_deeper": examine_clip_deeper,
}

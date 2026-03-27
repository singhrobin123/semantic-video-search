"""
LangGraph agent state definition.

The state is the single data structure that flows through every node in the
graph.  Keeping it in its own module prevents circular imports between
``graph.py``, ``nodes.py``, and ``tools.py``.
"""

from __future__ import annotations

from typing import Annotated, Any, Sequence, TypedDict

from langchain_core.messages import BaseMessage


class CandidateChunk(TypedDict):
    """A transcript chunk returned by the initial KNN retrieval."""
    clip_id: str
    segment_text: str
    start_time: float
    score: float


class ClipExamination(TypedDict):
    """Deep-dive result for a single clip."""
    clip_id: str
    title: str
    transcript_context: str
    relevant_moments: list[dict[str, Any]]


class AgentState(TypedDict):
    """
    The typed state that flows through the LangGraph state machine.

    This is deliberately flat — LangGraph serializes state between nodes,
    so deeply nested objects add serialization overhead.
    """
    messages: Annotated[Sequence[BaseMessage], "Conversation history"]
    query: str
    candidates: list[CandidateChunk]
    examined_clips: list[ClipExamination]
    final_result: dict[str, Any]

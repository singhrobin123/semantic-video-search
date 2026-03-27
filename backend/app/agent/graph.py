"""
LangGraph agentic state machine — the orchestration core.

Unlike simple linear chains (query → retrieve → generate), this graph
implements a *cyclic* tool-calling loop where the LLM autonomously decides
which tools to call and in what order:

    ┌──────────────────────────────────────────────┐
    │                                              │
    │   ┌─────────┐     ┌────────────┐     ┌───┐  │
    │   │  agent   │────▶│ tool_exec  │────▶│   │  │
    │   │ (reason) │◀────│ (execute)  │     │ C │  │
    │   └─────────┘     └────────────┘     │ O │  │
    │        │                              │ N │  │
    │        │ (no more tool calls)         │ T │  │
    │        ▼                              │ I │  │
    │   ┌─────────┐                        │ N │  │
    │   │ respond  │───────────────────────▶│ U │  │
    │   │ (final)  │                        │ E │  │
    │   └─────────┘                        └───┘  │
    │                                              │
    └──────────────────────────────────────────────┘

The provider loop runs until the model stops emitting tool calls.
"""

from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langgraph.graph import END, StateGraph
from pydantic import BaseModel, Field

from app.agent.state import AgentState
from app.agent.tools import (
    TOOL_DISPATCH,
    get_tool_definitions,
    reset_clip_cache,
)
from app.llm.provider import get_chat_model
from app.observability.logging import get_logger

logger = get_logger(__name__)

# ── Maximum agentic loop iterations (safety rail against infinite loops) ──
MAX_AGENT_ITERATIONS = 8


# ── Structured output schema (final JSON the API returns) ────────────────

class Quote(BaseModel):
    quote: str = Field(description="The exact transcript quote")
    quote_description: str = Field(
        default="", description="A brief summary of what the quote conveys"
    )
    quote_timestamp: float = Field(
        description="Timestamp in seconds where the quote occurs"
    )


class SearchResultItem(BaseModel):
    clip_id: str = Field(description="The ID of the relevant clip")
    question: str = Field(description="The user's original question")
    answer: str = Field(
        description="Concise answer, max 300 characters"
    )
    relevant_quotes: list[Quote] = Field(
        default_factory=list,
        description="Timestamped transcript quotes that support the answer",
    )
    related_questions: list[str] = Field(
        default_factory=list,
        description="5 logical follow-up questions",
    )


class SearchResponse(BaseModel):
    results: list[SearchResultItem] = Field(default_factory=list)


# ── System prompt ─────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are an intelligent agent tasked with answering a user's question by finding the best video clips in their library.

You have three tools:
1. "get_initial_candidates" — get initial candidate clips via semantic search. Always call this first.
2. "examine_clip_deeper" — examine a specific clip in detail. Call this for every promising candidate.
3. "get_clip_quotes" — get timestamped quotes from the best clip for the final answer.

Your workflow:
1. First call get_initial_candidates with the user's question.
2. For every clip that seems relevant, call examine_clip_deeper to get more context.
3. If there are no good candidates, return empty results.
4. Once you have a good answer, call get_clip_quotes to get the evidence.
5. Formulate your final answer using ONLY information from the tools.

Rules:
- Your final answer must be concise (under 300 characters).
- Always include timestamped relevant_quotes to prove your answer.
- If you cannot find an answer, return empty results.
- Suggest 5 related follow-up questions.

Your final response MUST be valid JSON matching this schema:
{
  "results": [
    {
      "clip_id": "string",
      "question": "string",
      "answer": "string",
      "relevant_quotes": [
        {"quote": "string", "quote_description": "string", "quote_timestamp": number}
      ],
      "related_questions": ["string", "string", "string", "string", "string"]
    }
  ]
}
"""


# ── Graph nodes ──────────────────────────────────────────────────────────

async def agent_reason(state: AgentState) -> dict[str, Any]:
    """
    The 'thinking' node — send conversation history to the LLM and let it
    decide whether to call a tool or provide a final answer.
    """
    llm = get_chat_model()
    llm_with_tools = llm.bind_tools(get_tool_definitions())

    messages = list(state["messages"])
    response: AIMessage = await llm_with_tools.ainvoke(messages)

    logger.info(
        "agent_reason_complete",
        tool_calls=len(response.tool_calls) if response.tool_calls else 0,
        query=state["query"][:60],
    )
    return {"messages": [*state["messages"], response]}


async def tool_execute(state: AgentState) -> dict[str, Any]:
    """
    Execute every tool call the LLM requested in the last message.

    Each result is appended as a ``ToolMessage`` so the LLM sees the
    output on the next reasoning iteration.
    """
    last_message: AIMessage = state["messages"][-1]  # type: ignore[assignment]
    tool_results: list[BaseMessage] = []

    for call in last_message.tool_calls:
        fn_name = call["name"]
        fn_args = call["args"]

        handler = TOOL_DISPATCH.get(fn_name)
        if handler is None:
            result_str = json.dumps({"error": f"Unknown tool: {fn_name}"})
        else:
            try:
                result_str = await handler(**fn_args)
            except Exception as exc:
                logger.exception("tool_execution_error", tool=fn_name)
                result_str = json.dumps({"error": str(exc)})

        tool_results.append(
            ToolMessage(content=result_str, tool_call_id=call["id"])
        )

        logger.info("tool_executed", tool=fn_name, args_keys=list(fn_args.keys()))

    return {"messages": [*state["messages"], *tool_results]}


async def respond(state: AgentState) -> dict[str, Any]:
    """
    Terminal node — parse the LLM's final text response into our
    structured ``SearchResponse`` schema.
    """
    last_message = state["messages"][-1]
    content = last_message.content if isinstance(last_message.content, str) else ""

    try:
        parsed = json.loads(content)
        response = SearchResponse(**parsed)
        result = response.model_dump()
    except (json.JSONDecodeError, Exception) as exc:
        logger.warning("response_parse_fallback", error=str(exc))
        # Fallback: wrap raw text in the expected envelope
        result = {
            "results": [
                {
                    "clip_id": "",
                    "question": state["query"],
                    "answer": content[:600] if content else "No relevant video found.",
                    "relevant_quotes": [],
                    "related_questions": [],
                }
            ]
        }

    return {"final_result": result}


# ── Routing logic ────────────────────────────────────────────────────────

def should_continue(state: AgentState) -> str:
    """
    After the agent reasons, decide whether to execute tools or produce
    the final response.

    Also enforces a hard iteration cap to prevent runaway loops.
    """
    messages = state["messages"]
    last = messages[-1]

    # Count how many agent iterations have occurred
    agent_turns = sum(1 for m in messages if isinstance(m, AIMessage))
    if agent_turns >= MAX_AGENT_ITERATIONS:
        logger.warning("agent_max_iterations_reached", turns=agent_turns)
        return "respond"

    if isinstance(last, AIMessage) and last.tool_calls:
        return "tool_execute"

    return "respond"


# ── Graph assembly ───────────────────────────────────────────────────────

def build_graph() -> Any:
    """
    Compile the LangGraph state machine.

    The graph is compiled once at import time and reused for every request.
    ``reset_clip_cache()`` is called per-request in the API layer to prevent
    cross-request data leakage.
    """
    workflow = StateGraph(AgentState)

    workflow.add_node("agent", agent_reason)
    workflow.add_node("tool_execute", tool_execute)
    workflow.add_node("respond", respond)

    workflow.set_entry_point("agent")

    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {"tool_execute": "tool_execute", "respond": "respond"},
    )
    workflow.add_edge("tool_execute", "agent")
    workflow.add_edge("respond", END)

    compiled = workflow.compile()
    logger.info("agent_graph_compiled", nodes=["agent", "tool_execute", "respond"])
    return compiled

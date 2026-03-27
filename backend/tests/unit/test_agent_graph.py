"""
Unit tests for the LangGraph agent state machine.

Tests routing logic and the respond node in isolation, without invoking
real LLM calls or the full graph.
"""

import json
import pytest
from unittest.mock import MagicMock
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from app.agent.graph import should_continue, respond, MAX_AGENT_ITERATIONS
from app.agent.state import AgentState


def _make_state(**overrides) -> AgentState:
    """Build a minimal valid AgentState with overrides."""
    base: AgentState = {
        "messages": [],
        "query": "test query",
        "candidates": [],
        "examined_clips": [],
        "final_result": {},
    }
    base.update(overrides)
    return base


class TestShouldContinue:
    """Tests for the routing function between agent → tool_execute | respond."""

    def test_routes_to_tool_execute_when_tool_calls_present(self):
        ai_msg = AIMessage(content="", tool_calls=[
            {"name": "get_initial_candidates", "args": {"question": "test"}, "id": "1"}
        ])
        state = _make_state(messages=[SystemMessage(content="sys"), ai_msg])
        assert should_continue(state) == "tool_execute"

    def test_routes_to_respond_when_no_tool_calls(self):
        ai_msg = AIMessage(content='{"results": []}')
        state = _make_state(messages=[SystemMessage(content="sys"), ai_msg])
        assert should_continue(state) == "respond"

    def test_enforces_max_iterations(self):
        """Safety rail: after MAX_AGENT_ITERATIONS, force respond."""
        messages = [SystemMessage(content="sys")]
        for i in range(MAX_AGENT_ITERATIONS):
            messages.append(AIMessage(content="", tool_calls=[
                {"name": "get_initial_candidates", "args": {"question": "q"}, "id": str(i)}
            ]))
            messages.append(ToolMessage(content="[]", tool_call_id=str(i)))

        # Add one more AI message with tool calls — should be blocked
        messages.append(AIMessage(content="", tool_calls=[
            {"name": "get_initial_candidates", "args": {"question": "q"}, "id": "extra"}
        ]))

        state = _make_state(messages=messages)
        assert should_continue(state) == "respond"


class TestRespondNode:
    """Tests for the terminal respond node that parses LLM output."""

    @pytest.mark.asyncio
    async def test_parses_valid_json(self):
        valid_response = json.dumps({
            "results": [{
                "clip_id": "yt-abc123",
                "question": "What is scaling?",
                "answer": "Scaling involves horizontal sharding.",
                "relevant_quotes": [
                    {"quote": "We scaled horizontally", "quote_description": "Scaling approach", "quote_timestamp": 45.0}
                ],
                "related_questions": ["How?", "When?", "Why?", "Where?", "What?"],
            }]
        })
        ai_msg = AIMessage(content=valid_response)
        state = _make_state(messages=[ai_msg], query="What is scaling?")

        result = await respond(state)
        assert "final_result" in result
        assert len(result["final_result"]["results"]) == 1
        assert result["final_result"]["results"][0]["clip_id"] == "yt-abc123"

    @pytest.mark.asyncio
    async def test_handles_malformed_json_gracefully(self):
        ai_msg = AIMessage(content="This is not JSON at all")
        state = _make_state(messages=[ai_msg], query="test query")

        result = await respond(state)
        assert "final_result" in result
        # Should fallback to wrapping raw text
        assert len(result["final_result"]["results"]) == 1
        assert "not JSON" in result["final_result"]["results"][0]["answer"]

    @pytest.mark.asyncio
    async def test_handles_empty_content(self):
        ai_msg = AIMessage(content="")
        state = _make_state(messages=[ai_msg])

        result = await respond(state)
        assert result["final_result"]["results"][0]["answer"] == "No relevant video found."

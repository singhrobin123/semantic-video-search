# ADR-001: LangGraph Over Linear LangChain Chains

## Status
Accepted

## Context
The initial prototype used a linear LangChain chain: `query → retrieve → generate`. This is the pattern taught in 95% of tutorials, but it has critical limitations for production video search:

1. **No autonomy** — the chain always executes every step, even when the first retrieval returns zero results (wasting LLM tokens).
2. **No multi-step reasoning** — the model cannot decide to examine multiple clips or drill deeper into a promising candidate.
3. **No loop safety** — without an iteration cap, a poorly prompted model could loop indefinitely.

## Decision
We adopt **LangGraph's `StateGraph`** with a cyclic tool-calling architecture:

```
agent → tool_execute → agent → ... → respond → END
```

The LLM is given three tools (`get_initial_candidates`, `examine_clip_deeper`, `get_clip_quotes`) and autonomously decides:
- Which tools to call
- In what order
- When to stop and produce a final answer

The agent graph binds the three tools and loops until the model stops emitting tool calls or the iteration cap is reached.

## Consequences
- **Positive**: True agentic behavior; model can skip unnecessary steps; handles multi-clip results naturally.
- **Positive**: `MAX_AGENT_ITERATIONS` safety rail prevents runaway loops.
- **Negative**: Slightly higher latency due to multiple LLM round-trips (mitigated by `gpt-4o-mini`'s speed).
- **Negative**: Harder to unit test than a linear chain (mitigated by our node-level test isolation pattern).

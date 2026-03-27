# ADR-003: Multi-Provider LLM Abstraction

## Status
Accepted

## Context
Enterprise systems cannot be locked into a single LLM provider. Reasons include:

1. **Cost optimization** — different providers have different pricing tiers.
2. **Compliance** — some customers require AWS-only infrastructure (Bedrock).
3. **Resilience** — if one provider has an outage, the system should be able to failover.
4. **A/B testing** — comparing model quality across providers.

In production at scale, systems use a `HammerheadAIProvider` abstraction that switches between GPT-4.1-mini and Bedrock Nova based on customer preferences.

## Decision
We implement a provider abstraction in `app/llm/provider.py`:

- `get_chat_model()` returns a LangChain-compatible `BaseChatModel` for the configured provider.
- `get_embeddings()` returns an OpenAI embeddings client (used regardless of chat provider, since Anthropic doesn't offer embeddings).
- Provider selection is driven by a single env var: `LLM_PROVIDER=openai|anthropic`.
- Per-call overrides are supported for temperature and model.

## Consequences
- **Positive**: Swap providers with zero code changes.
- **Positive**: Demonstrates enterprise multi-vendor resilience.
- **Positive**: Embedding provider is decoupled from chat provider (realistic pattern).
- **Negative**: Anthropic requires a separate `pip install langchain-anthropic` (lazy import with clear error message).

"""
Batch embedding generation with rate-limit awareness.

OpenAI's embedding API allows batching up to ~2048 inputs.  This module
batches chunks to minimize API round-trips while staying under token limits.
"""

from __future__ import annotations

from app.ingestion.chunker import TranscriptChunkDTO
from app.llm.provider import get_embeddings
from app.observability.logging import get_logger

logger = get_logger(__name__)

# OpenAI batch embedding limit (safe default)
MAX_BATCH_SIZE = 512


async def embed_chunks(
    chunks: list[TranscriptChunkDTO],
    batch_size: int = MAX_BATCH_SIZE,
) -> list[list[float]]:
    """
    Generate embeddings for a list of transcript chunks.

    Returns a list of embedding vectors aligned 1:1 with the input chunks.
    """
    embeddings_client = get_embeddings()
    texts = [c.text for c in chunks]
    all_vectors: list[list[float]] = []

    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        logger.info(
            "embedding_batch",
            batch_start=i,
            batch_size=len(batch),
            total=len(texts),
        )
        vectors = await embeddings_client.aembed_documents(batch)
        all_vectors.extend(vectors)

    logger.info(
        "embedding_complete",
        total_chunks=len(chunks),
        total_vectors=len(all_vectors),
        dimensions=len(all_vectors[0]) if all_vectors else 0,
    )
    return all_vectors

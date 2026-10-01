import asyncio
import math
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.config import settings
from app.db.repositories.prompt_cache_repository import (
    PromptCacheCandidate,
    find_nearest_prompt_cache,
    insert_prompt_cache,
)


def _validate_embedding(embedding: list[float]) -> None:
    if not isinstance(embedding, list) or len(embedding) != 768:
        raise ValueError("Embedding must contain exactly 768 dimensions")
    for value in embedding:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("Embedding values must be finite numbers")
        try:
            if not math.isfinite(float(value)):
                raise ValueError("Embedding values must be finite numbers")
        except OverflowError:
            raise ValueError(
                "Embedding values must be finite numbers"
            ) from None


async def save_prompt_cache(
    prompt: str,
    embedding: list[float],
    response: dict[str, Any],
    model: str,
    provider: str | None = None,
    expires_at: datetime | None = None,
) -> None:
    _validate_embedding(embedding)
    if not isinstance(response, dict):
        raise ValueError("Response must be a dictionary")
    if not isinstance(model, str) or not model:
        raise ValueError("Model must not be empty")

    await asyncio.to_thread(
        insert_prompt_cache,
        prompt,
        [float(value) for value in embedding],
        response,
        model,
        provider,
        expires_at,
    )


@dataclass(frozen=True)
class SemanticCacheHit:
    id: int
    prompt: str
    similarity: float
    response: dict[str, Any]
    model: str
    provider: str | None


async def find_similar_prompt_cache(
    embedding: list[float],
    similarity_threshold: float | None = None,
) -> SemanticCacheHit | None:
    _validate_embedding(embedding)
    threshold = (
        settings.semantic_cache_similarity_threshold
        if similarity_threshold is None
        else similarity_threshold
    )
    if (
        isinstance(threshold, bool)
        or not isinstance(threshold, (int, float))
        or not math.isfinite(float(threshold))
        or not 0.0 <= threshold <= 1.0
    ):
        raise ValueError("Similarity threshold must be between 0 and 1")

    candidate: PromptCacheCandidate | None = await asyncio.to_thread(
        find_nearest_prompt_cache,
        [float(value) for value in embedding],
    )
    if candidate is None:
        return None

    similarity = 1.0 - candidate.cosine_distance
    if similarity < threshold:
        return None

    return SemanticCacheHit(
        id=candidate.id,
        prompt=candidate.prompt,
        similarity=similarity,
        response=candidate.response,
        model=candidate.model,
        provider=candidate.provider,
    )

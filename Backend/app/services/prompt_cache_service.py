import asyncio
import math
from datetime import datetime
from typing import Any

from app.db.repositories.prompt_cache_repository import insert_prompt_cache


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

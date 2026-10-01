import logging
from dataclasses import dataclass
from typing import Any

from app.services.embedding_service import generate_embedding
from app.services.prompt_cache_service import (
    SemanticCacheHit,
    find_similar_prompt_cache,
    save_prompt_cache,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SemanticCacheLookup:
    prompt: str
    embedding: list[float] | None
    hit: SemanticCacheHit | None


async def lookup_semantic_cache(
    prompt: str,
    model: str,
) -> SemanticCacheLookup:
    try:
        embedding = await generate_embedding(prompt)
    except Exception as error:
        logger.warning(
            "Semantic cache embedding failed model=%s error_type=%s",
            model,
            type(error).__name__,
        )
        return SemanticCacheLookup(prompt=prompt, embedding=None, hit=None)

    try:
        hit = await find_similar_prompt_cache(embedding, model=model)
    except Exception as error:
        logger.warning(
            "Semantic cache lookup failed model=%s error_type=%s",
            model,
            type(error).__name__,
        )
        return SemanticCacheLookup(prompt=prompt, embedding=embedding, hit=None)

    outcome = "hit" if hit is not None else "miss"
    logger.info("Semantic cache lookup outcome=%s model=%s", outcome, model)
    return SemanticCacheLookup(prompt=prompt, embedding=embedding, hit=hit)


async def save_semantic_cache(
    lookup: SemanticCacheLookup,
    response: dict[str, Any],
    model: str,
    provider: str,
) -> None:
    if lookup.embedding is None:
        return

    try:
        await save_prompt_cache(
            prompt=lookup.prompt,
            embedding=lookup.embedding,
            response=response,
            model=model,
            provider=provider,
        )
    except Exception as error:
        logger.warning(
            "Semantic cache persistence failed model=%s error_type=%s",
            model,
            type(error).__name__,
        )

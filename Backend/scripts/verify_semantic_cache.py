"""Run from Backend with: python scripts/verify_semantic_cache.py"""

import asyncio
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

PROMPTS = {
    "A": "How can I learn Python?",
    "B": "What is the best way to learn Python?",
    "C": "How do I configure PostgreSQL?",
}


def cosine_similarity(first: list[float], second: list[float]) -> float:
    dot_product = math.fsum(left * right for left, right in zip(first, second))
    first_norm = math.sqrt(math.fsum(value * value for value in first))
    second_norm = math.sqrt(math.fsum(value * value for value in second))
    if first_norm == 0 or second_norm == 0:
        raise ValueError("Cannot compare an embedding with zero magnitude")
    return dot_product / (first_norm * second_norm)


async def verify() -> int:
    try:
        from pydantic import ValidationError

        from app.config import settings
    except ValidationError:
        print(
            "Configuration is incomplete. Configure the required Backend "
            "settings and GEMINI_API_KEY in Backend/.env or the environment.",
            file=sys.stderr,
        )
        return 1

    if not settings.gemini_api_key:
        print(
            "GEMINI_API_KEY is not configured in Backend/.env or the environment.",
            file=sys.stderr,
        )
        return 1

    from fastapi import HTTPException

    from app.services.embedding_service import generate_embedding

    try:
        embeddings = {
            label: await generate_embedding(prompt)
            for label, prompt in PROMPTS.items()
        }
    except HTTPException as error:
        print(
            f"Gemini embedding request failed (HTTP {error.status_code}): "
            f"{error.detail}",
            file=sys.stderr,
        )
        return 1

    threshold = settings.semantic_cache_similarity_threshold
    comparisons = (("A", "B"), ("A", "C"), ("B", "C"))
    for first, second in comparisons:
        similarity = cosine_similarity(
            embeddings[first],
            embeddings[second],
        )
        outcome = "HIT" if similarity >= threshold else "MISS"
        print(
            f"{first} vs {second} similarity: {similarity:.6f} "
            f"({outcome}, threshold: {threshold:.2f})"
        )
    return 0


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(verify())
    except (ValueError, OverflowError) as error:
        print(f"Semantic similarity verification failed: {error}", file=sys.stderr)
        exit_code = 1
    raise SystemExit(exit_code)

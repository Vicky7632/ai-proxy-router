from dataclasses import dataclass
from datetime import datetime
import math
from typing import Any

from sqlalchemy import func, or_

from app.db.models.prompt_cache import PromptCache
from app.db.session import SessionLocal


@dataclass(frozen=True)
class PromptCacheCandidate:
    id: int
    prompt: str
    response: dict[str, Any]
    model: str
    provider: str | None
    cosine_distance: float


def insert_prompt_cache(
    prompt: str,
    embedding: list[float],
    response: dict[str, Any],
    model: str,
    provider: str | None = None,
    expires_at: datetime | None = None,
) -> None:
    db = SessionLocal()
    try:
        db.add(
            PromptCache(
                prompt=prompt,
                embedding=embedding,
                response=response,
                model=model,
                provider=provider,
                expires_at=expires_at,
            )
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def find_nearest_prompt_cache(
    embedding: list[float],
) -> PromptCacheCandidate | None:
    if not isinstance(embedding, list) or len(embedding) != 768:
        raise ValueError("Embedding must contain exactly 768 dimensions")
    for value in embedding:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("Embedding values must be finite numbers")
        try:
            if not math.isfinite(float(value)):
                raise ValueError("Embedding values must be finite numbers")
        except OverflowError:
            raise ValueError("Embedding values must be finite numbers") from None

    db = SessionLocal()
    try:
        distance = PromptCache.embedding.cosine_distance(embedding)
        row = (
            db.query(PromptCache, distance.label("cosine_distance"))
            .filter(
                or_(
                    PromptCache.expires_at.is_(None),
                    PromptCache.expires_at > func.now(),
                ),
                distance.is_not(None),
            )
            .order_by(distance.asc())
            .limit(1)
            .first()
        )
        if row is None:
            return None

        entry, cosine_distance = row
        return PromptCacheCandidate(
            id=entry.id,
            prompt=entry.prompt,
            response=entry.response,
            model=entry.model,
            provider=entry.provider,
            cosine_distance=float(cosine_distance),
        )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

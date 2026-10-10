from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.repositories.request_log_analytics_repository import (
    get_cache_analytics_counts,
)


@dataclass(frozen=True)
class CacheAnalytics:
    total_requests: int
    redis_hits: int
    redis_misses: int
    semantic_hits: int
    semantic_misses: int
    provider_calls: int
    cache_hits: int
    cache_hit_rate: float


def get_cache_analytics(
    db: Session,
    api_key_id: UUID,
    from_datetime: datetime | None = None,
    to_datetime: datetime | None = None,
) -> CacheAnalytics:
    (
        total_requests,
        redis_hits,
        redis_misses,
        semantic_hits,
        semantic_misses,
        provider_calls,
    ) = get_cache_analytics_counts(
        db,
        api_key_id=api_key_id,
        from_datetime=normalize_utc_datetime(from_datetime),
        to_datetime=normalize_utc_datetime(to_datetime),
    )
    cache_hits = redis_hits + semantic_hits
    cache_hit_rate = (
        cache_hits / total_requests * 100 if total_requests else 0.0
    )

    return CacheAnalytics(
        total_requests=total_requests,
        redis_hits=redis_hits,
        redis_misses=redis_misses,
        semantic_hits=semantic_hits,
        semantic_misses=semantic_misses,
        provider_calls=provider_calls,
        cache_hits=cache_hits,
        cache_hit_rate=cache_hit_rate,
    )


def normalize_utc_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)

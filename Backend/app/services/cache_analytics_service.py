from dataclasses import dataclass

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


def get_cache_analytics(db: Session) -> CacheAnalytics:
    (
        total_requests,
        redis_hits,
        redis_misses,
        semantic_hits,
        semantic_misses,
        provider_calls,
    ) = get_cache_analytics_counts(db)
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

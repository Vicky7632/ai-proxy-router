from pydantic import BaseModel


class CacheAnalyticsResponse(BaseModel):
    total_requests: int
    redis_hits: int
    redis_misses: int
    semantic_hits: int
    semantic_misses: int
    redis_errors: int
    semantic_errors: int
    provider_calls: int
    cache_hits: int
    cache_hit_rate: float

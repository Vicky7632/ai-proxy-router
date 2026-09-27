import asyncio
import math
import time
from uuid import uuid4

from fastapi import HTTPException
from redis.exceptions import RedisError

from app.services.redis_service import redis_client

CAPACITY = 10
REFILL_TOKENS = 10
REFILL_INTERVAL_SECONDS = 60
REQUEST_COST = 1
WINDOW_SECONDS = 60

TOKEN_BUCKET_SCRIPT = """
local capacity = tonumber(ARGV[1])
local refill_per_second = tonumber(ARGV[2])
local cost = tonumber(ARGV[3])
local now = tonumber(ARGV[4])
local key_ttl = tonumber(ARGV[5])

local state = redis.call("HMGET", KEYS[1], "tokens", "last_refill")
local tokens = tonumber(state[1])
local last_refill = tonumber(state[2])

if tokens == nil or last_refill == nil then
    tokens = capacity
    last_refill = now
else
    local elapsed = math.max(0, now - last_refill)
    tokens = math.min(capacity, tokens + elapsed * refill_per_second)
    last_refill = now
end

local allowed = 0
if tokens >= cost then
    tokens = tokens - cost
    allowed = 1
end

redis.call("HSET", KEYS[1], "tokens", string.format("%.6f", tokens),
    "last_refill", string.format("%.6f", last_refill))
redis.call("EXPIRE", KEYS[1], key_ttl)

return {allowed, tokens}
"""


class RateLimiter:
    def __init__(
        self,
        redis=redis_client,
        capacity: int = CAPACITY,
        refill_tokens: int = REFILL_TOKENS,
        refill_interval_seconds: int = REFILL_INTERVAL_SECONDS,
        request_cost: int = REQUEST_COST,
        window_seconds: int = WINDOW_SECONDS,
    ) -> None:
        self.redis = redis
        self.capacity = capacity
        self.refill_tokens = refill_tokens
        self.refill_interval_seconds = refill_interval_seconds
        self.request_cost = request_cost
        self.window_seconds = window_seconds

    async def check_limit(self, api_key_id) -> float:
        try:
            allowed, remaining = await asyncio.to_thread(
                self._check_limit_sync, str(api_key_id)
            )
        except RedisError as error:
            raise HTTPException(
                status_code=503,
                detail="Rate limit storage is unavailable.",
            ) from error

        if not allowed:
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded. Try again later.",
            )
        return remaining

    def _check_limit_sync(self, api_key_id: str) -> tuple[bool, float]:
        now = time.time()
        now_ms = int(now * 1000)
        bucket_key = f"bucket:{api_key_id}"
        window_key = f"window:{api_key_id}"
        refill_per_second = self.refill_tokens / self.refill_interval_seconds
        bucket_ttl = max(
            1,
            math.ceil(self.capacity / refill_per_second * 2),
        )
        allowed, remaining = self.redis.eval(
            TOKEN_BUCKET_SCRIPT,
            1,
            bucket_key,
            self.capacity,
            refill_per_second,
            self.request_cost,
            now,
            bucket_ttl,
        )

        pipeline = self.redis.pipeline(transaction=True)
        pipeline.zremrangebyscore(
            window_key,
            "-inf",
            now_ms - self.window_seconds * 1000,
        )
        pipeline.zadd(window_key, {f"{now_ms}:{uuid4().hex}": now_ms})
        pipeline.zcard(window_key)
        pipeline.expire(window_key, self.window_seconds)
        pipeline.execute()
        return bool(allowed), float(remaining)


rate_limiter = RateLimiter()

import os

os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("GROQ_API_KEY", "test-groq-key")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")

import pytest
from fastapi import HTTPException

from app.services.rate_limiter import RateLimiter, TOKEN_BUCKET_SCRIPT


class FakePipeline:
    def __init__(self, redis):
        self.redis = redis
        self.commands = []

    def zremrangebyscore(self, key, minimum, maximum):
        self.commands.append(("zremrangebyscore", key, minimum, maximum))
        return self

    def zadd(self, key, members):
        self.commands.append(("zadd", key, members))
        return self

    def zcard(self, key):
        self.commands.append(("zcard", key))
        return self

    def expire(self, key, seconds):
        self.commands.append(("expire", key, seconds))
        return self

    def execute(self):
        self.redis.pipeline_commands = [command[0] for command in self.commands]
        results = []
        for command in self.commands:
            name, *args = command
            results.append(getattr(self.redis, name)(*args))
        return results


class FakeRedis:
    def __init__(self):
        self.buckets = {}
        self.windows = {}
        self.expirations = {}
        self.last_script = None
        self.pipeline_commands = []

    def eval(self, script, key_count, key, capacity, refill_rate, cost, now, ttl):
        self.last_script = script
        state = self.buckets.get(key)
        if state is None:
            tokens, last_refill = float(capacity), float(now)
        else:
            tokens, last_refill = state
            tokens = min(
                float(capacity),
                tokens + max(0, now - last_refill) * float(refill_rate),
            )
            last_refill = float(now)

        allowed = tokens >= float(cost)
        if allowed:
            tokens -= float(cost)
        self.buckets[key] = (tokens, last_refill)
        self.expirations[key] = ttl
        return [int(allowed), tokens]

    def pipeline(self, transaction=True):
        return FakePipeline(self)

    def zremrangebyscore(self, key, minimum, maximum):
        maximum = int(maximum)
        entries = self.windows.setdefault(key, {})
        removed = [member for member, score in entries.items() if score <= maximum]
        for member in removed:
            del entries[member]
        return len(removed)

    def zadd(self, key, members):
        entries = self.windows.setdefault(key, {})
        entries.update(members)
        return len(members)

    def zcard(self, key):
        return len(self.windows.get(key, {}))

    def expire(self, key, seconds):
        self.expirations[key] = seconds
        return True


@pytest.mark.asyncio
async def test_token_bucket_limits_and_refills_after_30_seconds(monkeypatch):
    fake_redis = FakeRedis()
    limiter = RateLimiter(
        redis=fake_redis,
        capacity=3,
        refill_tokens=3,
        refill_interval_seconds=30,
        window_seconds=30,
    )
    now = [1000.0]
    monkeypatch.setattr("app.services.rate_limiter.time.time", lambda: now[0])

    assert await limiter.check_limit("key-123") == 2
    assert await limiter.check_limit("key-123") == 1
    assert await limiter.check_limit("key-123") == 0
    for _ in range(2):
        with pytest.raises(HTTPException) as error:
            await limiter.check_limit("key-123")
        assert error.value.status_code == 429
        assert error.value.detail == "Rate limit exceeded. Try again later."

    window = fake_redis.windows["window:key-123"]
    assert len(window) == 5
    assert fake_redis.expirations["window:key-123"] == 30
    assert fake_redis.pipeline_commands == [
        "zremrangebyscore",
        "zadd",
        "zcard",
        "expire",
    ]

    now[0] += 30
    assert await limiter.check_limit("key-123") == 2
    assert len(fake_redis.windows["window:key-123"]) == 1


def test_uses_atomic_lua_for_token_bucket():
    assert 'redis.call("HMGET"' in TOKEN_BUCKET_SCRIPT
    assert 'redis.call("HSET"' in TOKEN_BUCKET_SCRIPT
    assert "redis.call(\"EXPIRE\"" in TOKEN_BUCKET_SCRIPT

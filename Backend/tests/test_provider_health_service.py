import os
from datetime import timezone

os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("GROQ_API_KEY", "test-groq-key")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")

import pytest

from app.services.provider_health_service import (
    PROVIDER_HEALTH_KEY_PREFIX,
    ProviderHealth,
    ProviderHealthService,
)


class FakePipeline:
    def __init__(self, redis):
        self.redis = redis
        self.commands = []

    def hincrby(self, key, field, amount):
        self.commands.append(("hincrby", key, field, amount))
        return self

    def hset(self, key, field=None, value=None, mapping=None):
        self.commands.append(("hset", key, field, value, mapping))
        return self

    def execute(self):
        for command in self.commands:
            name, key, *args = command
            if name == "hincrby":
                field, amount = args
                self.redis.hashes.setdefault(key, {})[field] = str(
                    int(self.redis.hashes.get(key, {}).get(field, 0)) + amount
                )
            else:
                field, value, mapping = args
                values = self.redis.hashes.setdefault(key, {})
                if mapping is not None:
                    values.update({name: str(item) for name, item in mapping.items()})
                else:
                    values[field] = str(value)


class FakeRedis:
    def __init__(self):
        self.hashes = {}

    def pipeline(self, transaction=True):
        assert transaction is True
        return FakePipeline(self)

    def hgetall(self, key):
        return dict(self.hashes.get(key, {}))

    def scan_iter(self, match):
        assert match == f"{PROVIDER_HEALTH_KEY_PREFIX}*"
        return iter(
            key for key in self.hashes if key.startswith(PROVIDER_HEALTH_KEY_PREFIX)
        )


@pytest.mark.asyncio
async def test_initial_provider_health_is_empty():
    service = ProviderHealthService(redis=FakeRedis())

    assert await service.get_health("groq") == ProviderHealth()
    assert await service.get_all_health() == {}


@pytest.mark.asyncio
async def test_success_updates_request_count_timestamp_and_resets_failures():
    service = ProviderHealthService(redis=FakeRedis())

    await service.record_success("groq")
    health = await service.get_health("groq")

    assert health.total_requests == 1
    assert health.total_failures == 0
    assert health.consecutive_failures == 0
    assert health.last_success_at is not None
    assert health.last_success_at.tzinfo == timezone.utc
    assert health.last_failure_at is None


@pytest.mark.asyncio
async def test_failure_updates_failure_counters_and_timestamp():
    service = ProviderHealthService(redis=FakeRedis())

    await service.record_failure("gemini")
    health = await service.get_health("gemini")

    assert health.total_requests == 1
    assert health.total_failures == 1
    assert health.consecutive_failures == 1
    assert health.last_failure_at is not None
    assert health.last_failure_at.tzinfo == timezone.utc
    assert health.last_success_at is None


@pytest.mark.asyncio
async def test_consecutive_failures_increment_and_success_resets_them():
    service = ProviderHealthService(redis=FakeRedis())

    await service.record_failure("openrouter")
    await service.record_failure("openrouter")
    assert (await service.get_health("openrouter")).consecutive_failures == 2

    await service.record_success("openrouter")
    health = await service.get_health("openrouter")
    assert health.total_requests == 3
    assert health.total_failures == 2
    assert health.consecutive_failures == 0


@pytest.mark.asyncio
async def test_provider_health_is_isolated():
    service = ProviderHealthService(redis=FakeRedis())

    await service.record_failure("groq")
    await service.record_success("gemini")

    groq_health = await service.get_health("groq")
    gemini_health = await service.get_health("gemini")
    all_health = await service.get_all_health()

    assert groq_health.total_failures == 1
    assert groq_health.consecutive_failures == 1
    assert gemini_health.total_failures == 0
    assert gemini_health.consecutive_failures == 0
    assert set(all_health) == {"groq", "gemini"}
    assert all_health["groq"] == groq_health
    assert all_health["gemini"] == gemini_health

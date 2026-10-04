import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone

from redis.exceptions import RedisError

from app.services.redis_service import redis_client

PROVIDER_HEALTH_KEY_PREFIX = "provider_health:v1:"


@dataclass(frozen=True)
class ProviderHealth:
    total_requests: int = 0
    total_failures: int = 0
    consecutive_failures: int = 0
    last_success_at: datetime | None = None
    last_failure_at: datetime | None = None


class ProviderHealthService:
    def __init__(self, redis=redis_client) -> None:
        self.redis = redis

    async def record_success(self, provider_name: str) -> None:
        await asyncio.to_thread(self._record_success, provider_name)

    async def record_failure(self, provider_name: str) -> None:
        await asyncio.to_thread(self._record_failure, provider_name)

    async def get_health(self, provider_name: str) -> ProviderHealth:
        try:
            stored_health = await asyncio.to_thread(
                self.redis.hgetall,
                self._key(provider_name),
            )
        except RedisError as error:
            raise RuntimeError("Provider health storage is unavailable") from error
        return self._parse_health(stored_health)

    async def get_all_health(self) -> dict[str, ProviderHealth]:
        try:
            health = await asyncio.to_thread(self._get_all_health)
        except RedisError as error:
            raise RuntimeError("Provider health storage is unavailable") from error
        return health

    def _record_success(self, provider_name: str) -> None:
        key = self._key(provider_name)
        pipeline = self.redis.pipeline(transaction=True)
        pipeline.hincrby(key, "total_requests", 1)
        pipeline.hset(
            key,
            mapping={
                "consecutive_failures": 0,
                "last_success_at": self._timestamp(),
            },
        )
        self._execute(pipeline)

    def _record_failure(self, provider_name: str) -> None:
        key = self._key(provider_name)
        pipeline = self.redis.pipeline(transaction=True)
        pipeline.hincrby(key, "total_requests", 1)
        pipeline.hincrby(key, "total_failures", 1)
        pipeline.hincrby(key, "consecutive_failures", 1)
        pipeline.hset(key, "last_failure_at", self._timestamp())
        self._execute(pipeline)

    def _get_all_health(self) -> dict[str, ProviderHealth]:
        health = {}
        for key in self.redis.scan_iter(
            match=f"{PROVIDER_HEALTH_KEY_PREFIX}*"
        ):
            provider_name = key[len(PROVIDER_HEALTH_KEY_PREFIX):]
            health[provider_name] = self._parse_health(self.redis.hgetall(key))
        return health

    @staticmethod
    def _key(provider_name: str) -> str:
        if not provider_name:
            raise ValueError("Provider name must not be empty")
        return f"{PROVIDER_HEALTH_KEY_PREFIX}{provider_name}"

    @staticmethod
    def _timestamp() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _parse_health(stored_health: dict[str, str]) -> ProviderHealth:
        def parse_timestamp(field: str) -> datetime | None:
            value = stored_health.get(field)
            return datetime.fromisoformat(value) if value else None

        return ProviderHealth(
            total_requests=int(stored_health.get("total_requests", 0)),
            total_failures=int(stored_health.get("total_failures", 0)),
            consecutive_failures=int(
                stored_health.get("consecutive_failures", 0)
            ),
            last_success_at=parse_timestamp("last_success_at"),
            last_failure_at=parse_timestamp("last_failure_at"),
        )

    @staticmethod
    def _execute(pipeline) -> None:
        try:
            pipeline.execute()
        except RedisError as error:
            raise RuntimeError(
                "Provider health storage is unavailable"
            ) from error


provider_health_service = ProviderHealthService()

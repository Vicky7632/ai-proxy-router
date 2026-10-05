import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from redis.exceptions import RedisError

from app.config import settings
from app.services.redis_service import redis_client

PROVIDER_HEALTH_KEY_PREFIX = "provider_health:v1:"
logger = logging.getLogger(__name__)


class ProviderHealthDataError(ValueError):
    """Raised when stored provider health data cannot be interpreted."""


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

    async def is_provider_healthy(self, provider_name: str) -> bool:
        self._key(provider_name)
        try:
            health = await self.get_health(provider_name)
        except (RuntimeError, ProviderHealthDataError):
            logger.exception(
                "Provider health unavailable or malformed provider=%s; "
                "failing open",
                provider_name,
            )
            return True

        if (
            health.consecutive_failures
            < settings.provider_health_failure_threshold
            or health.last_failure_at is None
        ):
            return True

        last_failure_at = health.last_failure_at
        try:
            if last_failure_at.tzinfo is None:
                last_failure_at = last_failure_at.replace(tzinfo=timezone.utc)
            else:
                last_failure_at = last_failure_at.astimezone(timezone.utc)
            now = datetime.now(timezone.utc)
            if last_failure_at > now:
                logger.warning(
                    "Provider failure timestamp is in the future "
                    "provider=%s; failing open",
                    provider_name,
                )
                return True
            cooldown_expires_at = last_failure_at + timedelta(
                seconds=settings.provider_health_cooldown_seconds
            )
        except (OverflowError, ValueError):
            logger.exception(
                "Provider failure timestamp is out of range provider=%s; "
                "failing open",
                provider_name,
            )
            return True
        return now >= cooldown_expires_at

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
        if not isinstance(stored_health, dict):
            raise ProviderHealthDataError(
                "Provider health data must be a Redis hash"
            )

        def parse_timestamp(field: str) -> datetime | None:
            value = stored_health.get(field)
            if not value:
                return None
            if not isinstance(value, str):
                raise ProviderHealthDataError(
                    f"Provider health field {field} must be a timestamp string"
                )
            try:
                return datetime.fromisoformat(value)
            except ValueError as error:
                raise ProviderHealthDataError(
                    f"Provider health field {field} is not a valid timestamp"
                ) from error

        try:
            return ProviderHealth(
                total_requests=int(stored_health.get("total_requests", 0)),
                total_failures=int(stored_health.get("total_failures", 0)),
                consecutive_failures=int(
                    stored_health.get("consecutive_failures", 0)
                ),
                last_success_at=parse_timestamp("last_success_at"),
                last_failure_at=parse_timestamp("last_failure_at"),
            )
        except ProviderHealthDataError:
            raise
        except (TypeError, ValueError, OverflowError) as error:
            raise ProviderHealthDataError(
                "Provider health counters are malformed"
            ) from error

    @staticmethod
    def _execute(pipeline) -> None:
        try:
            pipeline.execute()
        except RedisError as error:
            raise RuntimeError(
                "Provider health storage is unavailable"
            ) from error


provider_health_service = ProviderHealthService()

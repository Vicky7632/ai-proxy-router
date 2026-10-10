import asyncio
import hashlib
import json
import logging
from dataclasses import dataclass
from typing import Any, Literal

from redis.exceptions import RedisError

from app.schemas.chat import ChatCompletionRequest
from app.services.redis_service import redis_client

CACHE_KEY_PREFIX = "cache:v1:"
CACHE_TTL_SECONDS = 3600
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CacheLookupResult:
    response: dict[str, Any] | None
    status: Literal["hit", "miss", "error"]


def normalize_request(
    request: ChatCompletionRequest | dict[str, Any],
) -> str:
    """Serialize cache-relevant request fields canonically."""
    validated_request = (
        request
        if isinstance(request, ChatCompletionRequest)
        else ChatCompletionRequest.model_validate(request)
    )
    payload = validated_request.model_dump(mode="json", exclude_none=False)
    payload.pop("stream", None)
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def get_cache_key(
    request: ChatCompletionRequest | dict[str, Any],
) -> str:
    normalized = normalize_request(request)
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return f"{CACHE_KEY_PREFIX}{digest}"


def _get_legacy_cache_keys(
    request: ChatCompletionRequest | dict[str, Any],
) -> list[str]:
    validated_request = (
        request
        if isinstance(request, ChatCompletionRequest)
        else ChatCompletionRequest.model_validate(request)
    )
    payload = validated_request.model_dump(mode="json", exclude_none=False)
    keys = []
    for stream_value in (False, None):
        payload["stream"] = stream_value
        normalized = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        key = f"{CACHE_KEY_PREFIX}{digest}"
        if key not in keys:
            keys.append(key)
    return keys


def _get_cached_response_result(
    key: str,
) -> tuple[dict[str, Any] | None, bool]:
    try:
        encoded = redis_client.get(key)
    except RedisError:
        logger.exception("Redis cache lookup failed key=%s", key)
        return None, True
    if encoded is None:
        return None, False
    try:
        response = json.loads(encoded)
    except (TypeError, UnicodeDecodeError, json.JSONDecodeError):
        logger.warning("Discarding invalid cached response key=%s", key)
        try:
            redis_client.delete(key)
        except RedisError:
            logger.exception("Failed to delete invalid cache entry key=%s", key)
        return None, True
    if not isinstance(response, dict):
        logger.warning("Discarding non-object cached response key=%s", key)
        try:
            redis_client.delete(key)
        except RedisError:
            logger.exception("Failed to delete invalid cache entry key=%s", key)
        return None, True
    return response, False


def _get_cached_response(key: str) -> dict[str, Any] | None:
    response, _ = _get_cached_response_result(key)
    return response


async def lookup_cached_response(
    request: ChatCompletionRequest | dict[str, Any],
    cache_key: str | None = None,
) -> CacheLookupResult:
    current_key = get_cache_key(request)
    key = cache_key or current_key
    response, had_error = await asyncio.to_thread(
        _get_cached_response_result,
        key,
    )
    if response is not None:
        return CacheLookupResult(response=response, status="hit")
    if key != current_key:
        return CacheLookupResult(
            response=None,
            status="error" if had_error else "miss",
        )

    for legacy_key in _get_legacy_cache_keys(request):
        if legacy_key == current_key:
            continue
        response, key_had_error = await asyncio.to_thread(
            _get_cached_response_result,
            legacy_key,
        )
        had_error = had_error or key_had_error
        if response is not None:
            return CacheLookupResult(response=response, status="hit")
    return CacheLookupResult(
        response=None,
        status="error" if had_error else "miss",
    )


async def get_cached_response(
    request: ChatCompletionRequest | dict[str, Any],
    cache_key: str | None = None,
) -> dict[str, Any] | None:
    result = await lookup_cached_response(request, cache_key)
    return result.response


def _save_cached_response(
    key: str,
    response: dict[str, Any],
    ttl: int,
) -> bool:
    encoded = json.dumps(
        response,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    try:
        return bool(redis_client.setex(key, ttl, encoded))
    except RedisError:
        logger.exception("Redis cache write failed key=%s", key)
        return False


async def save_cached_response(
    request: ChatCompletionRequest | dict[str, Any],
    response: dict[str, Any],
    ttl: int = CACHE_TTL_SECONDS,
    cache_key: str | None = None,
) -> bool:
    key = cache_key or get_cache_key(request)
    return await asyncio.to_thread(_save_cached_response, key, response, ttl)
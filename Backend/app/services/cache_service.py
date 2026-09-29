import asyncio
import hashlib
import json
import logging
from typing import Any

from redis.exceptions import RedisError

from app.schemas.chat import ChatCompletionRequest
from app.services.redis_service import redis_client

CACHE_KEY_PREFIX = "cache:v1:"
CACHE_TTL_SECONDS = 3600
logger = logging.getLogger(__name__)


def _is_streaming(request: ChatCompletionRequest | dict[str, Any]) -> bool:
    if isinstance(request, ChatCompletionRequest):
        return request.stream
    return bool(request.get("stream", False))


def normalize_request(
    request: ChatCompletionRequest | dict[str, Any],
) -> str:
    """Serialize request fields canonically without altering prompt content."""
    validated_request = (
        request
        if isinstance(request, ChatCompletionRequest)
        else ChatCompletionRequest.model_validate(request)
    )
    payload = validated_request.model_dump(mode="json", exclude_none=False)
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


def _get_cached_response(key: str) -> dict[str, Any] | None:
    try:
        encoded = redis_client.get(key)
    except RedisError:
        logger.exception("Redis cache lookup failed key=%s", key)
        return None
    if encoded is None:
        return None
    try:
        response = json.loads(encoded)
    except (TypeError, UnicodeDecodeError, json.JSONDecodeError):
        logger.warning("Discarding invalid cached response key=%s", key)
        try:
            redis_client.delete(key)
        except RedisError:
            logger.exception("Failed to delete invalid cache entry key=%s", key)
        return None
    if not isinstance(response, dict):
        logger.warning("Discarding non-object cached response key=%s", key)
        try:
            redis_client.delete(key)
        except RedisError:
            logger.exception("Failed to delete invalid cache entry key=%s", key)
        return None
    return response


async def get_cached_response(
    request: ChatCompletionRequest | dict[str, Any],
    cache_key: str | None = None,
) -> dict[str, Any] | None:
    if _is_streaming(request):
        return None
    key = cache_key or get_cache_key(request)
    return await asyncio.to_thread(_get_cached_response, key)


def _save_cached_response(
    key: str,
    response: dict[str, Any],
    ttl: int,
) -> None:
    encoded = json.dumps(
        response,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    try:
        redis_client.setex(key, ttl, encoded)
    except RedisError:
        logger.exception("Redis cache write failed key=%s", key)


async def save_cached_response(
    request: ChatCompletionRequest | dict[str, Any],
    response: dict[str, Any],
    ttl: int = CACHE_TTL_SECONDS,
    cache_key: str | None = None,
) -> None:
    if _is_streaming(request):
        return
    key = cache_key or get_cache_key(request)
    await asyncio.to_thread(_save_cached_response, key, response, ttl)
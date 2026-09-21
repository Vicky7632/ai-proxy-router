import redis
from redis.exceptions import RedisError

from app.config import settings


def _create_redis_client() -> redis.Redis:
    if settings.redis_url:
        return redis.Redis.from_url(settings.redis_url, decode_responses=True)

    return redis.Redis(
        host=settings.redis_host,
        port=settings.redis_port,
        db=settings.redis_db,
        username=settings.redis_username,
        password=settings.redis_password,
        ssl=settings.redis_ssl,
        decode_responses=True,
    )


redis_client = _create_redis_client()

def _blacklist_key(token_id: str) -> str:
    return f"auth:blacklist:{token_id}"


def blacklist_token(token_id: str, ttl_seconds: int) -> None:
    try:
        redis_client.setex(_blacklist_key(token_id), max(ttl_seconds, 1), "revoked")
    except RedisError as exc:
        raise RuntimeError("Authentication session storage is unavailable") from exc


def is_token_blacklisted(token_id: str) -> bool:
    try:
        return redis_client.exists(_blacklist_key(token_id)) == 1
    except RedisError as exc:
        raise RuntimeError("Authentication session storage is unavailable") from exc


def store_refresh_token(token_id: str, user_id: str, ttl_seconds: int) -> None:
    try:
        redis_client.setex(f"auth:refresh:{token_id}", ttl_seconds, user_id)
    except RedisError as exc:
        raise RuntimeError("Authentication session storage is unavailable") from exc


def consume_refresh_token(token_id: str, user_id: str) -> bool:
    key = f"auth:refresh:{token_id}"
    try:
        with redis_client.pipeline() as pipeline:
            while True:
                try:
                    pipeline.watch(key)
                    if pipeline.get(key) != user_id:
                        pipeline.unwatch()
                        return False
                    pipeline.multi()
                    pipeline.delete(key)
                    pipeline.execute()
                    return True
                except redis.WatchError:
                    continue
    except RedisError as exc:
        raise RuntimeError("Authentication session storage is unavailable") from exc


def revoke_refresh_token(token_id: str, ttl_seconds: int) -> None:
    try:
        redis_client.delete(f"auth:refresh:{token_id}")
        blacklist_token(token_id, ttl_seconds)
    except RedisError as exc:
        raise RuntimeError("Authentication session storage is unavailable") from exc

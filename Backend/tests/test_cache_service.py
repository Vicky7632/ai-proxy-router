import asyncio
import hashlib
import json
import os
import time
from types import SimpleNamespace
from uuid import uuid4

os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("GROQ_API_KEY", "test-groq-key")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")

import pytest
from fastapi import BackgroundTasks
from redis.exceptions import RedisError
from starlette.responses import Response

import app.api.v1.chat as chat_api
from app.db.models.request_log import RequestLog
from app.providers.router import RoutedCompletion
from app.schemas.chat import ChatCompletionRequest
from app.services import cache_service


class FakeRedis:
    def __init__(self):
        self.values = {}
        self.expirations = {}

    def get(self, key):
        expiry = self.expirations.get(key)
        if expiry is not None and expiry <= time.monotonic():
            self.values.pop(key, None)
            self.expirations.pop(key, None)
            return None
        return self.values.get(key)

    def setex(self, key, ttl, value):
        self.values[key] = value
        self.expirations[key] = time.monotonic() + ttl
        return True

    def delete(self, key):
        self.values.pop(key, None)
        self.expirations.pop(key, None)
        return 1


def request(model="openai/gpt-oss-20b", prompt="Hello", stream=False):
    return ChatCompletionRequest(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        stream=stream,
    )


@pytest.mark.asyncio
async def test_cache_lookup_save_and_ttl_expiration(monkeypatch):
    redis = FakeRedis()
    monkeypatch.setattr(cache_service, "redis_client", redis)
    req = request()

    assert await cache_service.get_cached_response(req) is None
    lookup = await cache_service.lookup_cached_response(req)
    assert lookup.response is None
    assert lookup.status == "miss"

    await cache_service.save_cached_response(req, {"id": "cached"}, ttl=1)
    key = cache_service.get_cache_key(req)
    assert key.startswith("cache:v1:")
    assert await cache_service.get_cached_response(req) == {"id": "cached"}

    redis.expirations[key] = time.monotonic() - 1
    assert await cache_service.get_cached_response(req) is None


@pytest.mark.asyncio
async def test_invalid_redis_entry_is_reported_as_lookup_error(monkeypatch):
    redis = FakeRedis()
    monkeypatch.setattr(cache_service, "redis_client", redis)
    req = request()
    key = cache_service.get_cache_key(req)
    redis.values[key] = "{invalid json"

    result = await cache_service.lookup_cached_response(req, key)

    assert result.response is None
    assert result.status == "error"


@pytest.mark.asyncio
async def test_redis_lookup_error_is_logged_and_provider_fallback_continues(
    monkeypatch,
):
    class UnavailableRedis:
        def get(self, key):
            raise RedisError("Redis unavailable")

        def setex(self, key, ttl, value):
            raise RedisError("Redis unavailable")

    monkeypatch.setattr(cache_service, "redis_client", UnavailableRedis())
    logged_requests = []
    monkeypatch.setattr(
        chat_api,
        "save_request_log",
        lambda *args: logged_requests.append(args),
    )

    class FakeEngine:
        def __init__(self):
            self.calls = 0

        def resolve(self, model):
            return object(), model

        async def chat_completion(
            self,
            completion_request,
            on_provider_attempt=None,
        ):
            self.calls += 1
            if on_provider_attempt is not None:
                on_provider_attempt("groq", completion_request.model)
            return RoutedCompletion(
                response={"id": "provider-response", "choices": []},
                provider="groq",
            )

    engine = FakeEngine()
    monkeypatch.setattr(chat_api, "router_engine", engine)
    monkeypatch.setattr(
        chat_api.semantic_cache_service,
        "lookup_semantic_cache",
        _semantic_miss,
    )
    monkeypatch.setattr(
        chat_api.rate_limiter,
        "check_limit",
        lambda api_key_id: asyncio.sleep(0, result=9),
    )
    monkeypatch.setattr(
        chat_api.budget_service,
        "check_budget",
        lambda api_key: asyncio.sleep(0, result=3.42),
    )

    tasks = BackgroundTasks()
    result = await chat_api.chat_completions(
        request(),
        tasks,
        Response(),
        SimpleNamespace(id=uuid4()),
    )
    await tasks()

    assert result.status_code == 200
    assert json.loads(result.body)["id"] == "provider-response"
    assert engine.calls == 1
    assert logged_requests[0][7] == "error"
    assert logged_requests[0][8] == "miss"
    assert logged_requests[0][9] is True


def test_normalized_request_is_deterministic_and_key_ignores_stream_mode():
    first = {
        "stream": False,
        "messages": [{"content": "Hello", "role": "user"}],
        "model": "model-a",
    }
    equivalent = {
        "model": "model-a",
        "messages": [{"role": "user", "content": "Hello"}],
        "stream": False,
    }
    assert cache_service.normalize_request(first) == cache_service.normalize_request(
        equivalent
    )
    assert cache_service.get_cache_key(first) == cache_service.get_cache_key(
        equivalent
    )
    assert cache_service.get_cache_key(first) == cache_service.get_cache_key(
        {**first, "stream": True}
    )
    assert cache_service.get_cache_key({**first, "api_key": "secret-a"}) == (
        cache_service.get_cache_key({**first, "api_key": "secret-b"})
    )
    assert cache_service.get_cache_key(request(model="model-b")) != (
        cache_service.get_cache_key(request(model="model-a"))
    )
    assert cache_service.get_cache_key(request(prompt="Different")) != (
        cache_service.get_cache_key(request(prompt="Hello"))
    )


@pytest.mark.asyncio
async def test_stream_lookup_falls_back_to_legacy_non_stream_cache_key(
    monkeypatch,
):
    redis = FakeRedis()
    monkeypatch.setattr(cache_service, "redis_client", redis)
    req = request(stream=True)
    legacy_payload = req.model_copy(update={"stream": False}).model_dump(
        mode="json",
        exclude_none=False,
    )
    legacy_normalized = json.dumps(
        legacy_payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    legacy_digest = hashlib.sha256(legacy_normalized.encode("utf-8")).hexdigest()
    legacy_key = f"{cache_service.CACHE_KEY_PREFIX}{legacy_digest}"
    redis.values[legacy_key] = json.dumps({"id": "legacy-cached"})

    assert legacy_key != cache_service.get_cache_key(req)
    assert await cache_service.get_cached_response(req) == {
        "id": "legacy-cached"
    }


@pytest.mark.asyncio
async def test_stream_and_non_stream_requests_share_cache(monkeypatch):
    redis = FakeRedis()
    monkeypatch.setattr(cache_service, "redis_client", redis)
    non_stream_request = request()
    stream_request = request(stream=True)

    assert cache_service.get_cache_key(non_stream_request) == (
        cache_service.get_cache_key(stream_request)
    )
    assert await cache_service.get_cached_response(stream_request) is None
    await cache_service.save_cached_response(
        stream_request,
        {"id": "saved-from-stream"},
    )

    assert await cache_service.get_cached_response(non_stream_request) == {
        "id": "saved-from-stream"
    }


@pytest.mark.asyncio
async def test_identical_requests_share_cache_and_route_once(monkeypatch):
    redis = FakeRedis()
    monkeypatch.setattr(cache_service, "redis_client", redis)

    async def allow_rate_limit(api_key_id):
        return 9

    async def allow_budget(api_key):
        return 3.42

    class FakeEngine:
        def __init__(self):
            self.calls = 0

        def resolve(self, model):
            return object(), model

        async def chat_completion(
            self,
            completion_request,
            on_provider_attempt=None,
        ):
            self.calls += 1
            if on_provider_attempt is not None:
                on_provider_attempt("groq", completion_request.model)
            return RoutedCompletion(
                response={
                    "id": "completion-1",
                    "model": completion_request.model,
                    "choices": [],
                },
                provider="groq",
            )

    engine = FakeEngine()
    monkeypatch.setattr(chat_api, "router_engine", engine)
    monkeypatch.setattr(chat_api.rate_limiter, "check_limit", allow_rate_limit)
    monkeypatch.setattr(chat_api.budget_service, "check_budget", allow_budget)
    monkeypatch.setattr(chat_api, "save_request_log", lambda *args: None)
    monkeypatch.setattr(
        chat_api.semantic_cache_service,
        "lookup_semantic_cache",
        _semantic_miss,
    )

    api_key = SimpleNamespace(id=uuid4())
    first_tasks = BackgroundTasks()
    second_tasks = BackgroundTasks()

    first_response = Response()
    first = await chat_api.chat_completions(
        request(),
        first_tasks,
        first_response,
        api_key,
    )
    second_response = Response()
    second = await chat_api.chat_completions(
        request(),
        second_tasks,
        second_response,
        api_key,
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.headers["X-Cache"] == "MISS"
    assert second.headers["X-Cache"] == "HIT"
    assert first.headers["X-Remaining-Budget"] == "3.42"
    assert second.headers["X-Remaining-Budget"] == "3.42"
    assert json.loads(first.body) == json.loads(second.body)
    assert engine.calls == 1
    hit_log_args = second_tasks.tasks[0].args
    assert hit_log_args[1] == "cache"
    assert hit_log_args[3:5] == (None, None)
    assert hit_log_args[6] == 200
    assert hit_log_args[7:] == ("hit", None, False)


@pytest.mark.parametrize(
    (
        "scenario",
        "expected_redis_status",
        "expected_semantic_status",
        "expected_provider_called",
    ),
    [
        ("redis_hit", "hit", None, False),
        ("semantic_hit", "miss", "hit", False),
        ("provider", "miss", "miss", True),
    ],
)
@pytest.mark.asyncio
async def test_chat_logs_cache_analytics(
    monkeypatch,
    scenario,
    expected_redis_status,
    expected_semantic_status,
    expected_provider_called,
):
    redis = FakeRedis()
    monkeypatch.setattr(cache_service, "redis_client", redis)

    class FakeEngine:
        def __init__(self):
            self.calls = 0

        def resolve(self, model):
            return object(), model

        async def chat_completion(
            self,
            completion_request,
            on_provider_attempt=None,
        ):
            self.calls += 1
            if on_provider_attempt is not None:
                on_provider_attempt("groq", completion_request.model)
            return RoutedCompletion(
                response={"id": "provider-response", "choices": []},
                provider="groq",
            )

    class FakeSession:
        def __init__(self):
            self.bind = None
            self.rows = []

        def query(self, model):
            return self

        def filter(self, condition):
            return self

        def first(self):
            return SimpleNamespace(id=uuid4())

        def add(self, row):
            self.rows.append(row)

        def flush(self):
            self.rows[-1].id = uuid4()

        def commit(self):
            pass

        def rollback(self):
            pass

        def close(self):
            pass

    sessions = []

    def make_session():
        session = FakeSession()
        sessions.append(session)
        return session

    engine = FakeEngine()
    monkeypatch.setattr(chat_api, "router_engine", engine)
    monkeypatch.setattr(chat_api, "SessionLocal", make_session)

    async def allow_rate_limit(api_key_id):
        return 9

    async def allow_budget(api_key):
        return 3.42

    semantic_calls = []

    async def semantic_lookup(prompt, model, temperature):
        semantic_calls.append((prompt, model, temperature))
        if scenario == "semantic_hit":
            return SimpleNamespace(
                prompt=prompt,
                embedding=None,
                hit=SimpleNamespace(response={"id": "semantic-response"}),
            )
        return chat_api.semantic_cache_service.SemanticCacheLookup(
            prompt=prompt,
            embedding=None,
            hit=None,
            cache_model=model,
        )

    async def no_op_semantic_save(*args):
        pass

    monkeypatch.setattr(chat_api.rate_limiter, "check_limit", allow_rate_limit)
    monkeypatch.setattr(chat_api.budget_service, "check_budget", allow_budget)
    monkeypatch.setattr(
        chat_api.semantic_cache_service,
        "lookup_semantic_cache",
        semantic_lookup,
    )
    monkeypatch.setattr(
        chat_api.semantic_cache_service,
        "save_semantic_cache",
        no_op_semantic_save,
    )

    req = request(prompt=f"analytics-{scenario}")
    if scenario == "redis_hit":
        await cache_service.save_cached_response(
            req,
            {"id": "redis-response"},
        )

    tasks = BackgroundTasks()
    result = await chat_api.chat_completions(
        req,
        tasks,
        Response(),
        SimpleNamespace(id=uuid4()),
    )
    await tasks()

    assert result.status_code == 200
    assert engine.calls == (1 if expected_provider_called else 0)
    assert len(semantic_calls) == (0 if scenario == "redis_hit" else 1)
    request_log = sessions[0].rows[0]
    assert isinstance(request_log, RequestLog)
    assert request_log.redis_cache_status == expected_redis_status
    assert request_log.semantic_cache_status == expected_semantic_status
    assert request_log.provider_called is expected_provider_called


async def _semantic_miss(prompt, model, temperature):
    return chat_api.semantic_cache_service.SemanticCacheLookup(
        prompt=prompt,
        embedding=None,
        hit=None,
        cache_model=model,
    )

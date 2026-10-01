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
from starlette.responses import Response

import app.api.v1.chat as chat_api
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
    await cache_service.save_cached_response(req, {"id": "cached"}, ttl=1)
    key = cache_service.get_cache_key(req)
    assert key.startswith("cache:v1:")
    assert await cache_service.get_cached_response(req) == {"id": "cached"}

    redis.expirations[key] = time.monotonic() - 1
    assert await cache_service.get_cached_response(req) is None


def test_normalized_request_is_deterministic_and_key_includes_model_and_prompt():
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
async def test_stream_requests_bypass_cache(monkeypatch):
    redis = FakeRedis()
    monkeypatch.setattr(cache_service, "redis_client", redis)
    stream_request = request(stream=True)

    assert await cache_service.get_cached_response(stream_request) is None
    await cache_service.save_cached_response(
        stream_request,
        {"id": "must-not-be-saved"},
    )

    assert redis.values == {}


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

        async def chat_completion(self, completion_request):
            self.calls += 1
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
    assert hit_log_args[-1] == 200


async def _semantic_miss(prompt, model):
    return chat_api.semantic_cache_service.SemanticCacheLookup(
        prompt=prompt,
        embedding=None,
        hit=None,
    )

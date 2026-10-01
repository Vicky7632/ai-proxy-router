import json
import os
import time
from types import SimpleNamespace
from uuid import uuid4

os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("GROQ_API_KEY", "test-groq-key")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")

import pytest
from fastapi import BackgroundTasks, HTTPException
from starlette.responses import Response

import app.api.v1.chat as chat_api
from app.providers.router import RoutedCompletion
from app.schemas.chat import ChatCompletionRequest
from app.services import cache_service, semantic_cache_service
from app.services.prompt_cache_service import SemanticCacheHit


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

    def delete(self, key):
        self.values.pop(key, None)
        self.expirations.pop(key, None)


def make_request(prompt="How can I learn Python?"):
    return ChatCompletionRequest(
        model="openai/gpt-oss-20b",
        messages=[{"role": "user", "content": prompt}],
    )


def install_endpoint_fakes(monkeypatch):
    redis = FakeRedis()
    monkeypatch.setattr(cache_service, "redis_client", redis)

    async def allow_rate_limit(api_key_id):
        return 9

    async def allow_budget(api_key):
        return 3.42

    monkeypatch.setattr(chat_api.rate_limiter, "check_limit", allow_rate_limit)
    monkeypatch.setattr(chat_api.budget_service, "check_budget", allow_budget)
    monkeypatch.setattr(chat_api, "save_request_log", lambda *args: None)

    class FakeEngine:
        def __init__(self):
            self.calls = 0

        def resolve(self, model):
            return object(), model

        async def chat_completion(self, completion_request):
            self.calls += 1
            return RoutedCompletion(
                response={
                    "id": "provider-response",
                    "model": completion_request.model,
                    "choices": [{"message": {"content": "provider answer"}}],
                },
                provider="groq",
            )

    engine = FakeEngine()
    monkeypatch.setattr(chat_api, "router_engine", engine)
    return redis, engine


async def call_endpoint(req=None):
    return await chat_api.chat_completions(
        req or make_request(),
        BackgroundTasks(),
        Response(),
        SimpleNamespace(id=uuid4()),
    )


def response_json(response):
    return json.loads(response.body)


def semantic_hit(response=None):
    return SemanticCacheHit(
        id=1,
        prompt="cached prompt",
        similarity=0.95,
        response=response
        or {
            "id": "semantic-response",
            "model": "openai/gpt-oss-20b",
            "choices": [{"message": {"content": "semantic answer"}}],
        },
        model="openai/gpt-oss-20b",
        provider="groq",
    )


@pytest.mark.asyncio
async def test_redis_hit_skips_embedding_semantic_lookup_and_provider(monkeypatch):
    _, engine = install_endpoint_fakes(monkeypatch)
    req = make_request()
    cached_response = {"id": "exact-response", "choices": []}
    await cache_service.save_cached_response(req, cached_response)

    async def unexpected_call(*args, **kwargs):
        raise AssertionError("Semantic cache must not run after Redis HIT")

    monkeypatch.setattr(
        semantic_cache_service,
        "generate_embedding",
        unexpected_call,
    )
    monkeypatch.setattr(
        semantic_cache_service,
        "find_similar_prompt_cache",
        unexpected_call,
    )
    monkeypatch.setattr(
        semantic_cache_service,
        "save_prompt_cache",
        unexpected_call,
    )

    response = await call_endpoint(req)

    assert response.status_code == 200
    assert response_json(response) == cached_response
    assert response.headers["X-Cache"] == "HIT"
    assert response.headers["X-Remaining-Budget"] == "3.42"
    assert engine.calls == 0


@pytest.mark.asyncio
async def test_semantic_hit_skips_provider_and_does_not_resave(monkeypatch):
    _, engine = install_endpoint_fakes(monkeypatch)
    embedding = [0.25] * 768
    embedding_calls = []
    lookup_calls = []
    save_calls = []

    async def generate(prompt):
        embedding_calls.append(prompt)
        return embedding

    async def find(vector, model=None):
        lookup_calls.append((vector, model))
        return semantic_hit()

    async def save(*args, **kwargs):
        save_calls.append((args, kwargs))

    monkeypatch.setattr(semantic_cache_service, "generate_embedding", generate)
    monkeypatch.setattr(
        semantic_cache_service,
        "find_similar_prompt_cache",
        find,
    )
    monkeypatch.setattr(semantic_cache_service, "save_prompt_cache", save)

    response = await call_endpoint()

    assert response.status_code == 200
    assert response_json(response)["id"] == "semantic-response"
    assert response.headers["X-Cache"] == "HIT"
    assert response.headers["X-Remaining-Budget"] == "3.42"
    assert len(embedding_calls) == 1
    assert len(lookup_calls) == 1
    assert lookup_calls[0][0] is embedding
    assert lookup_calls[0][1] == "openai/gpt-oss-20b"
    assert save_calls == []
    assert engine.calls == 0


@pytest.mark.asyncio
async def test_semantic_miss_calls_provider_once_and_saves_same_embedding(
    monkeypatch,
):
    _, engine = install_endpoint_fakes(monkeypatch)
    embedding = [0.5] * 768
    embedding_calls = []
    lookup_calls = []
    save_calls = []

    async def generate(prompt):
        embedding_calls.append(prompt)
        return embedding

    async def find(vector, model=None):
        lookup_calls.append((vector, model))
        return None

    async def save_prompt_cache(**kwargs):
        save_calls.append(kwargs)

    monkeypatch.setattr(semantic_cache_service, "generate_embedding", generate)
    monkeypatch.setattr(
        semantic_cache_service,
        "find_similar_prompt_cache",
        find,
    )
    monkeypatch.setattr(
        semantic_cache_service,
        "save_prompt_cache",
        save_prompt_cache,
    )

    req = make_request()
    response = await call_endpoint(req)

    assert response.status_code == 200
    assert response_json(response)["id"] == "provider-response"
    assert response.headers["X-Cache"] == "MISS"
    assert len(embedding_calls) == 1
    assert len(lookup_calls) == 1
    assert engine.calls == 1
    assert len(save_calls) == 1
    assert save_calls[0]["embedding"] is embedding
    assert save_calls[0]["prompt"] == json.dumps(
        [{"role": "user", "content": "How can I learn Python?"}],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    assert save_calls[0]["response"] == response_json(response)
    assert save_calls[0]["model"] == "openai/gpt-oss-20b"
    assert save_calls[0]["provider"] == "groq"


@pytest.mark.asyncio
async def test_embedding_failure_does_not_block_provider(monkeypatch):
    _, engine = install_endpoint_fakes(monkeypatch)

    async def fail_embedding(prompt):
        raise HTTPException(status_code=502, detail="embedding unavailable")

    async def unexpected_lookup(*args, **kwargs):
        raise AssertionError("Lookup must be skipped without an embedding")

    async def unexpected_save(**kwargs):
        raise AssertionError("Persistence must be skipped without an embedding")

    monkeypatch.setattr(
        semantic_cache_service,
        "generate_embedding",
        fail_embedding,
    )
    monkeypatch.setattr(
        semantic_cache_service,
        "find_similar_prompt_cache",
        unexpected_lookup,
    )
    monkeypatch.setattr(
        semantic_cache_service,
        "save_prompt_cache",
        unexpected_save,
    )

    response = await call_endpoint()

    assert response.status_code == 200
    assert response_json(response)["id"] == "provider-response"
    assert engine.calls == 1


@pytest.mark.asyncio
async def test_semantic_lookup_failure_does_not_block_provider(monkeypatch):
    _, engine = install_endpoint_fakes(monkeypatch)
    embedding = [0.1] * 768
    save_calls = []

    async def generate(prompt):
        return embedding

    async def fail_lookup(vector, model=None):
        raise RuntimeError("database unavailable")

    async def save_prompt_cache(**kwargs):
        save_calls.append(kwargs)

    monkeypatch.setattr(semantic_cache_service, "generate_embedding", generate)
    monkeypatch.setattr(
        semantic_cache_service,
        "find_similar_prompt_cache",
        fail_lookup,
    )
    monkeypatch.setattr(
        semantic_cache_service,
        "save_prompt_cache",
        save_prompt_cache,
    )

    response = await call_endpoint()

    assert response.status_code == 200
    assert response_json(response)["id"] == "provider-response"
    assert engine.calls == 1
    assert len(save_calls) == 1


@pytest.mark.asyncio
async def test_semantic_persistence_failure_does_not_fail_provider_response(
    monkeypatch,
):
    _, engine = install_endpoint_fakes(monkeypatch)

    async def generate(prompt):
        return [0.0] * 768

    async def miss(vector, model=None):
        return None

    async def fail_save(**kwargs):
        raise RuntimeError("database write failed")

    monkeypatch.setattr(semantic_cache_service, "generate_embedding", generate)
    monkeypatch.setattr(semantic_cache_service, "find_similar_prompt_cache", miss)
    monkeypatch.setattr(semantic_cache_service, "save_prompt_cache", fail_save)

    response = await call_endpoint()

    assert response.status_code == 200
    assert response_json(response)["id"] == "provider-response"
    assert engine.calls == 1

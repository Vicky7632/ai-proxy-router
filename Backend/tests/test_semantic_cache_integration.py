import json
import math
import os
import time
from types import SimpleNamespace
from uuid import uuid4

os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("GROQ_API_KEY", "test-groq-key")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")

import pytest
from fastapi import BackgroundTasks, HTTPException
from pgvector.sqlalchemy import Vector
from sqlalchemy import BigInteger, create_engine, event
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.sql.elements import BinaryExpression
from sqlalchemy.sql.operators import custom_op
from starlette.responses import Response

import app.api.v1.chat as chat_api
from app.db.base import Base
from app.db.models.prompt_cache import PromptCache
from app.db.repositories import prompt_cache_repository
from app.providers.router import RoutedCompletion
from app.schemas.chat import ChatCompletionRequest
from app.services import cache_service, semantic_cache_service
from app.services.prompt_cache_service import SemanticCacheHit


@compiles(BigInteger, "sqlite")
def compile_bigint_for_sqlite(type_, compiler, **kwargs):
    return "INTEGER"


@compiles(JSONB, "sqlite")
def compile_jsonb_for_sqlite(type_, compiler, **kwargs):
    return "JSON"


@compiles(Vector, "sqlite")
def compile_vector_for_sqlite(type_, compiler, **kwargs):
    return "TEXT"


@compiles(BinaryExpression, "sqlite")
def compile_vector_distance_for_sqlite(element, compiler, **kwargs):
    operator = element.operator
    if isinstance(operator, custom_op) and operator.opstring == "<=>":
        left = compiler.process(element.left, **kwargs)
        right = compiler.process(element.right, **kwargs)
        return f"cosine_distance({left}, {right})"
    return compiler.visit_binary(element, **kwargs)


@pytest.fixture
def prompt_cache_database(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    def register_cosine_distance(connection, _):
        def cosine_distance(left, right):
            left_vector = json.loads(left)
            right_vector = json.loads(right)
            dot_product = sum(
                left_value * right_value
                for left_value, right_value in zip(
                    left_vector,
                    right_vector,
                )
            )
            left_norm = math.sqrt(sum(value * value for value in left_vector))
            right_norm = math.sqrt(
                sum(value * value for value in right_vector)
            )
            if left_norm == 0 or right_norm == 0:
                return None
            return 1.0 - dot_product / (left_norm * right_norm)

        connection.create_function(
            "cosine_distance",
            2,
            cosine_distance,
        )

    event.listen(engine, "connect", register_cosine_distance)
    Base.metadata.create_all(engine, tables=[PromptCache.__table__])
    monkeypatch.setattr(
        prompt_cache_repository,
        "SessionLocal",
        sessionmaker(bind=engine),
    )
    try:
        yield
    finally:
        engine.dispose()


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
    assert lookup_calls[0][1] == (
        '{"model":"openai/gpt-oss-20b","temperature":0.7}'
    )
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
    assert save_calls[0]["model"] == (
        '{"model":"openai/gpt-oss-20b","temperature":0.7}'
    )
    assert save_calls[0]["provider"] == "groq"


@pytest.mark.asyncio
async def test_semantic_cache_scopes_entries_by_temperature(monkeypatch):
    redis, engine = install_endpoint_fakes(monkeypatch)
    cached_entries = {}
    lookup_models = []

    async def generate(prompt):
        return [0.5] * 768

    async def find(vector, model=None):
        lookup_models.append(model)
        return cached_entries.get(model)

    async def save_prompt_cache(**kwargs):
        cached_entries[kwargs["model"]] = SemanticCacheHit(
            id=len(cached_entries) + 1,
            prompt=kwargs["prompt"],
            similarity=1.0,
            response=kwargs["response"],
            model=kwargs["model"],
            provider=kwargs["provider"],
        )

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

    low_temperature = make_request().model_copy(update={"temperature": 0.2})
    high_temperature = make_request().model_copy(update={"temperature": 0.8})

    first_response = await call_endpoint(low_temperature)
    second_response = await call_endpoint(high_temperature)

    assert first_response.status_code == second_response.status_code == 200
    assert first_response.headers["X-Cache"] == "MISS"
    assert second_response.headers["X-Cache"] == "MISS"
    assert engine.calls == 2
    assert len(cached_entries) == 2
    assert lookup_models[0] != lookup_models[1]
    assert lookup_models[0] == (
        '{"model":"openai/gpt-oss-20b","temperature":0.2}'
    )
    assert lookup_models[1] == (
        '{"model":"openai/gpt-oss-20b","temperature":0.8}'
    )

    redis.values.clear()
    compatible_response = await call_endpoint(low_temperature)

    assert compatible_response.status_code == 200
    assert compatible_response.headers["X-Cache"] == "HIT"
    assert engine.calls == 2


@pytest.mark.asyncio
async def test_database_semantic_cache_isolates_temperature(
    prompt_cache_database,
    monkeypatch,
):
    embedding = [0.25] * 768

    async def generate(prompt):
        return embedding

    monkeypatch.setattr(semantic_cache_service, "generate_embedding", generate)
    prompt = json.dumps(
        [{"role": "user", "content": "How can I learn Python?"}],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    model = "openai/gpt-oss-20b"

    low_temperature_lookup = await semantic_cache_service.lookup_semantic_cache(
        prompt,
        model,
        0.2,
    )
    assert low_temperature_lookup.hit is None

    low_temperature_response = {"choices": [{"message": {"content": "low"}}]}
    await semantic_cache_service.save_semantic_cache(
        low_temperature_lookup,
        low_temperature_response,
        model,
        "groq",
    )

    high_temperature_lookup = await semantic_cache_service.lookup_semantic_cache(
        prompt,
        model,
        0.8,
    )
    assert high_temperature_lookup.hit is None
    assert low_temperature_lookup.cache_model != high_temperature_lookup.cache_model

    high_temperature_response = {"choices": [{"message": {"content": "high"}}]}
    await semantic_cache_service.save_semantic_cache(
        high_temperature_lookup,
        high_temperature_response,
        model,
        "groq",
    )

    low_temperature_hit = await semantic_cache_service.lookup_semantic_cache(
        prompt,
        model,
        0.2,
    )
    high_temperature_hit = await semantic_cache_service.lookup_semantic_cache(
        prompt,
        model,
        0.8,
    )

    assert low_temperature_hit.hit is not None
    assert low_temperature_hit.hit.response == low_temperature_response
    assert high_temperature_hit.hit is not None
    assert high_temperature_hit.hit.response == high_temperature_response


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

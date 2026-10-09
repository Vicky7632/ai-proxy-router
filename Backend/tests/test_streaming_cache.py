import json
import logging
import os
from types import SimpleNamespace
from uuid import uuid4

os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("GROQ_API_KEY", "test-groq-key")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")

import pytest
from fastapi import BackgroundTasks
from starlette.responses import Response

import app.api.v1.chat as chat_api
from app.providers.base import ProviderStream
from app.providers.router import RoutedStream
from app.schemas.chat import ChatCompletionRequest
from app.services import cache_service


class FakeRedis:
    def __init__(self):
        self.values = {}

    def get(self, key):
        return self.values.get(key)

    def setex(self, key, ttl, value):
        self.values[key] = value
        return True

    def delete(self, key):
        self.values.pop(key, None)


def make_request(stream=True):
    return ChatCompletionRequest(
        model="openai/gpt-oss-20b",
        messages=[{"role": "user", "content": "Hello"}],
        stream=stream,
    )


def completion(content="cached answer"):
    return {
        "id": "chatcmpl-cached",
        "object": "chat.completion",
        "created": 123,
        "model": "openai/gpt-oss-20b",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 2,
            "completion_tokens": 3,
            "total_tokens": 5,
        },
    }


def sse_event(data):
    return b"data: " + json.dumps(data, separators=(",", ":")).encode() + b"\n\n"


def provider_events(include_done=True):
    events = [
        {
            "id": "chatcmpl-provider",
            "object": "chat.completion.chunk",
            "created": 456,
            "model": "openai/gpt-oss-20b",
            "choices": [
                {
                    "index": 0,
                    "delta": {"role": "assistant", "content": "hello "},
                    "finish_reason": None,
                }
            ],
        },
        {
            "id": "chatcmpl-provider",
            "object": "chat.completion.chunk",
            "created": 456,
            "model": "openai/gpt-oss-20b",
            "choices": [
                {"index": 0, "delta": {"content": "world"}, "finish_reason": None}
            ],
        },
        {
            "id": "chatcmpl-provider",
            "object": "chat.completion.chunk",
            "created": 456,
            "model": "openai/gpt-oss-20b",
            "choices": [
                {
                    "index": 0,
                    "delta": {
                        "tool_calls": [
                            {
                                "index": 0,
                                "id": "call_1",
                                "type": "function",
                                "function": {
                                    "name": "lookup",
                                    "arguments": "{\"query\":",
                                },
                            }
                        ]
                    },
                    "finish_reason": None,
                }
            ],
        },
        {
            "id": "chatcmpl-provider",
            "object": "chat.completion.chunk",
            "created": 456,
            "model": "openai/gpt-oss-20b",
            "choices": [
                {
                    "index": 0,
                    "delta": {
                        "tool_calls": [
                            {
                                "index": 0,
                                "function": {"arguments": "\"x\"}"},
                            }
                        ]
                    },
                    "finish_reason": None,
                }
            ],
        },
        {
            "id": "chatcmpl-provider",
            "object": "chat.completion.chunk",
            "created": 456,
            "model": "openai/gpt-oss-20b",
            "choices": [
                {
                    "index": 0,
                    "delta": {},
                    "finish_reason": "stop",
                    "logprobs": {"content": []},
                }
            ],
        },
        {
            "id": "chatcmpl-provider",
            "object": "chat.completion.chunk",
            "created": 456,
            "model": "openai/gpt-oss-20b",
            "choices": [],
            "usage": {
                "prompt_tokens": 2,
                "completion_tokens": 3,
                "total_tokens": 5,
            },
        },
    ]
    chunks = [sse_event(event) for event in events]
    if include_done:
        chunks.append(b"data: [DONE]\n\n")
    return chunks


def install_fakes(monkeypatch, stream_factory=None):
    redis = FakeRedis()
    logs = []
    monkeypatch.setattr(cache_service, "redis_client", redis)
    monkeypatch.setattr(chat_api, "save_request_log", lambda *args: logs.append(args))

    async def allow_rate_limit(api_key_id):
        return 9

    async def allow_budget(api_key):
        return 3.42

    monkeypatch.setattr(chat_api.rate_limiter, "check_limit", allow_rate_limit)
    monkeypatch.setattr(chat_api.budget_service, "check_budget", allow_budget)

    async def semantic_miss(prompt, model):
        return SimpleNamespace(prompt=prompt, embedding=None, hit=None)

    monkeypatch.setattr(
        chat_api.semantic_cache_service,
        "lookup_semantic_cache",
        semantic_miss,
    )
    saved_semantic = []

    async def semantic_save(lookup, response, model, provider):
        saved_semantic.append((response, model, provider))

    monkeypatch.setattr(
        chat_api.semantic_cache_service,
        "save_semantic_cache",
        semantic_save,
    )

    class FakeEngine:
        def __init__(self):
            self.stream_calls = 0
            self.closed = 0

        def resolve(self, model):
            return object(), model

        def provider_name(self, model):
            return "groq"

        async def chat_completion_stream(self, request):
            self.stream_calls += 1

            async def chunks():
                for chunk in stream_factory():
                    yield chunk

            async def close():
                self.closed += 1

            return RoutedStream(
                stream=ProviderStream(chunks=chunks(), close=close),
                provider="groq",
                model=request.model,
            )

    engine = FakeEngine()
    monkeypatch.setattr(chat_api, "router_engine", engine)
    return redis, engine, logs, saved_semantic


async def call_endpoint(request=None):
    return await chat_api.chat_completions(
        request or make_request(),
        BackgroundTasks(),
        Response(),
        SimpleNamespace(id=uuid4()),
    )


def test_application_info_logs_are_enabled():
    import app.main

    assert logging.getLogger().getEffectiveLevel() == logging.INFO
    assert logging.getLogger(chat_api.__name__).isEnabledFor(logging.INFO)


async def consume(response):
    chunks = [chunk async for chunk in response.body_iterator]
    if response.background is not None:
        await response.background()
    return chunks


def parse_sse(chunks):
    events = []
    for chunk in chunks:
        for frame in chunk.replace(b"\r\n", b"\n").split(b"\n\n"):
            if frame.startswith(b"data:"):
                payload = frame[5:].strip()
                if payload and payload != b"[DONE]":
                    events.append(json.loads(payload))
    return events


@pytest.mark.asyncio
async def test_streaming_redis_hit_returns_openai_sse_without_provider(monkeypatch):
    redis, engine, logs, _ = install_fakes(monkeypatch)
    req = make_request(stream=False)
    cached = completion()
    await cache_service.save_cached_response(req, cached)

    async def unexpected_semantic_lookup(*args, **kwargs):
        raise AssertionError("Redis HIT must bypass semantic lookup")

    monkeypatch.setattr(
        chat_api.semantic_cache_service,
        "lookup_semantic_cache",
        unexpected_semantic_lookup,
    )
    response = await call_endpoint(make_request())

    assert response.media_type == "text/event-stream"
    assert response.headers["X-Cache"] == "HIT"
    chunks = await consume(response)
    assert engine.stream_calls == 0
    assert len(redis.values) == 1
    assert logs[0][1] == "cache"
    assert logs[0][7:] == ("hit", None, False)
    events = parse_sse(chunks)
    assert events[0]["choices"][0]["delta"]["content"] == "cached answer"
    assert events[1]["choices"][0]["finish_reason"] == "stop"
    assert events[2]["usage"]["total_tokens"] == 5
    assert chunks[-1] == b"data: [DONE]\n\n"


@pytest.mark.asyncio
async def test_streaming_semantic_hit_returns_sse_and_skips_provider(monkeypatch):
    _, engine, logs, _ = install_fakes(monkeypatch)
    semantic_response = completion("semantic answer")

    async def semantic_hit(prompt, model):
        return SimpleNamespace(
            prompt=prompt,
            embedding=None,
            hit=SimpleNamespace(response=semantic_response),
        )

    monkeypatch.setattr(
        chat_api.semantic_cache_service,
        "lookup_semantic_cache",
        semantic_hit,
    )
    response = await call_endpoint()
    chunks = await consume(response)

    assert response.headers["X-Cache"] == "HIT"
    assert chunks[-1] == b"data: [DONE]\n\n"
    assert parse_sse(chunks)[0]["choices"][0]["delta"]["content"] == (
        "semantic answer"
    )
    assert engine.stream_calls == 0
    assert logs[0][7:] == ("miss", "hit", False)


@pytest.mark.asyncio
async def test_streaming_miss_is_cached_and_reused_as_stream_hit(
    monkeypatch,
    caplog,
):
    caplog.set_level("INFO")
    _, engine, logs, semantic_saves = install_fakes(
        monkeypatch,
        stream_factory=provider_events,
    )
    response = await call_endpoint()
    original_chunks = await consume(response)

    assert response.headers["X-Cache"] == "MISS"
    assert original_chunks == provider_events()
    assert len(semantic_saves) == 1
    assembled = semantic_saves[0][0]
    assert assembled["choices"][0]["message"]["role"] == "assistant"
    assert assembled["choices"][0]["message"]["content"] == "hello world"
    assert assembled["choices"][0]["message"]["tool_calls"] == [
        {
            "id": "call_1",
            "type": "function",
            "function": {"name": "lookup", "arguments": "{\"query\":\"x\"}"},
        }
    ]
    assert assembled["choices"][0]["logprobs"] == {"content": []}
    assert assembled["usage"]["total_tokens"] == 5
    assert semantic_saves[0][1:] == ("openai/gpt-oss-20b", "groq")

    second_response = await call_endpoint()
    cached_chunks = await consume(second_response)
    events = parse_sse(cached_chunks)

    assert second_response.headers["X-Cache"] == "HIT"
    assert engine.stream_calls == 1
    assert events[0]["choices"][0]["delta"]["content"] == "hello world"
    assert events[0]["choices"][0]["delta"]["tool_calls"][0]["function"] == {
        "name": "lookup",
        "arguments": "{\"query\":\"x\"}",
    }
    assert events[1]["choices"][0]["finish_reason"] == "stop"
    assert events[1]["choices"][0]["logprobs"] == {"content": []}
    assert events[2]["usage"]["total_tokens"] == 5
    assert logs[0][7:] == ("miss", "miss", True)
    assert logs[1][7:] == ("hit", None, False)
    assert caplog.text.count(
        "event=provider_invocation request_mode=stream "
        "provider=groq model=openai/gpt-oss-20b"
    ) == 1
    assert "event=cache_lookup outcome=redis_miss cache_type=redis" in (
        caplog.text
    )
    assert "event=cache_lookup outcome=semantic_miss cache_type=semantic" in (
        caplog.text
    )
    assert "event=stream_cache_save cache_type=redis outcome=saved" in (
        caplog.text
    )
    assert "event=cache_lookup outcome=redis_hit cache_type=redis" in (
        caplog.text
    )
    assert "Hello" not in caplog.text


@pytest.mark.asyncio
async def test_incomplete_stream_is_not_cached(monkeypatch):
    redis, engine, logs, semantic_saves = install_fakes(
        monkeypatch,
        stream_factory=lambda: provider_events(include_done=False),
    )
    response = await call_endpoint()
    await consume(response)

    assert redis.values == {}
    assert semantic_saves == []
    assert engine.closed == 1
    assert logs[0][6] == 502


@pytest.mark.asyncio
async def test_malformed_provider_event_prevents_cache_write(monkeypatch):
    provider_chunks = provider_events()
    redis, engine, logs, semantic_saves = install_fakes(
        monkeypatch,
        stream_factory=lambda: provider_chunks[:-1]
        + [b"data: {invalid json}\n\n", provider_chunks[-1]],
    )
    response = await call_endpoint()
    await consume(response)

    assert response.headers["X-Cache"] == "MISS"
    assert engine.closed == 1
    assert redis.values == {}
    assert semantic_saves == []
    assert logs[0][6] == 502


@pytest.mark.asyncio
async def test_provider_stream_error_is_not_cached_and_closes_provider(monkeypatch):
    redis, engine, logs, semantic_saves = install_fakes(monkeypatch)

    def failing_stream():
        async def chunks():
            yield provider_events()[0]
            raise RuntimeError("provider stream failed")

        return chunks()

    async def failing_chat_completion_stream(request):
        engine.stream_calls += 1
        stream = failing_stream()

        async def close():
            engine.closed += 1

        return RoutedStream(
            ProviderStream(chunks=stream, close=close),
            provider="groq",
            model=request.model,
        )

    engine.chat_completion_stream = failing_chat_completion_stream
    response = await call_endpoint()
    with pytest.raises(RuntimeError, match="provider stream failed"):
        await consume(response)

    assert redis.values == {}
    assert semantic_saves == []
    assert engine.closed == 1
    assert logs[0][6] == 502


@pytest.mark.asyncio
async def test_cancellation_closes_provider_without_cache_write(monkeypatch):
    redis, engine, logs, semantic_saves = install_fakes(
        monkeypatch,
        stream_factory=provider_events,
    )
    response = await call_endpoint()
    iterator = response.body_iterator

    assert await iterator.__anext__() == provider_events()[0]
    await iterator.aclose()

    assert redis.values == {}
    assert semantic_saves == []
    assert engine.closed == 1
    assert logs[0][6] == 499

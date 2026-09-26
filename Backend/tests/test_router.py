import os

os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("GROQ_API_KEY", "test-groq-key")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")

import pytest
from fastapi import BackgroundTasks, HTTPException

import app.api.v1.chat as chat_api
from app.providers.gemini import GeminiProvider
from app.providers.base import ProviderStream
from app.providers.groq import GroqProvider
from app.providers.openrouter import OpenRouterProvider
from app.providers.router import RouterEngine, RoutedStream
from app.schemas.chat import ChatCompletionRequest


def request(model: str, stream: bool = False) -> ChatCompletionRequest:
    return ChatCompletionRequest(
        model=model,
        messages=[{"role": "user", "content": "Hello"}],
        stream=stream,
    )


@pytest.mark.parametrize(
    ("model", "provider_type"),
    [
        ("auto", GroqProvider),
        ("openai/gpt-oss-20b", GroqProvider),
        ("gemini-3.6-flash", GeminiProvider),
        ("qwen/qwen-2.5-72b-instruct", OpenRouterProvider),
        ("google/gemma-3-27b-it:free", OpenRouterProvider),
    ],
)
def test_model_routing(model, provider_type):
    engine = RouterEngine()

    assert isinstance(engine.resolve_provider(model), provider_type)


def test_auto_resolves_to_groq_model():
    provider, model = RouterEngine().resolve("auto")

    assert isinstance(provider, GroqProvider)
    assert model == "openai/gpt-oss-20b"


def test_unknown_model_has_clear_error():
    with pytest.raises(HTTPException, match="Unknown model 'not-a-model'"):
        RouterEngine().resolve_provider("not-a-model")


class FakeProvider:
    def __init__(self, response=None, error=None, stream_error=None):
        self.response = response or {"id": "ok"}
        self.error = error
        self.stream_error = stream_error
        self.models = []
        self.stream_requests = []

    async def chat_completion(self, request):
        self.models.append(request.model)
        if self.error:
            raise self.error
        return self.response

    async def chat_completion_stream(self, request):
        self.stream_requests.append(request)
        if self.stream_error:
            raise self.stream_error

        async def chunks():
            yield b"data: {\"model\":\"test-model\"}\n\n"
            yield b"data: [DONE]\n\n"

        async def close():
            return None

        return ProviderStream(chunks=chunks(), close=close)


@pytest.mark.asyncio
async def test_fallback_from_groq_to_gemini():
    groq = FakeProvider(error=HTTPException(status_code=503, detail="down"))
    gemini = FakeProvider(response={"id": "gemini"})
    engine = RouterEngine(
        {"groq": groq, "gemini": gemini, "openrouter": FakeProvider()}
    )

    result = await engine.chat_completion(request("auto"))

    assert result.response == {"id": "gemini"}
    assert result.provider == "gemini"
    assert groq.models == ["openai/gpt-oss-20b"]
    assert gemini.models == ["gemini-3.6-flash"]


@pytest.mark.asyncio
async def test_fallback_from_gemini_to_openrouter():
    gemini = FakeProvider(error=HTTPException(status_code=500, detail="down"))
    openrouter = FakeProvider(response={"id": "openrouter"})
    engine = RouterEngine(
        {
            "groq": FakeProvider(),
            "gemini": gemini,
            "openrouter": openrouter,
        }
    )

    result = await engine.chat_completion(request("gemini-3.6-flash"))

    assert result.response == {"id": "openrouter"}
    assert result.provider == "openrouter"
    assert openrouter.models == ["qwen/qwen-2.5-72b-instruct"]


@pytest.mark.asyncio
async def test_client_errors_do_not_fallback():
    groq = FakeProvider(error=HTTPException(status_code=401, detail="invalid"))
    gemini = FakeProvider()
    engine = RouterEngine(
        {"groq": groq, "gemini": gemini, "openrouter": FakeProvider()}
    )

    with pytest.raises(HTTPException) as error:
        await engine.chat_completion(request("auto"))

    assert error.value.status_code == 401
    assert gemini.models == []


@pytest.mark.asyncio
async def test_stream_falls_back_before_streaming_starts():
    groq = FakeProvider(stream_error=HTTPException(status_code=503, detail="down"))
    gemini = FakeProvider()
    engine = RouterEngine(
        {"groq": groq, "gemini": gemini, "openrouter": FakeProvider()}
    )

    result = await engine.chat_completion_stream(
        request("openai/gpt-oss-20b")
    )

    assert result.provider == "gemini"
    assert result.model == "gemini-3.6-flash"
    assert groq.stream_requests[0].stream is True
    assert gemini.stream_requests[0].model == "gemini-3.6-flash"


@pytest.mark.asyncio
async def test_openrouter_stream_uses_requested_model():
    openrouter = FakeProvider()
    engine = RouterEngine(
        {
            "groq": FakeProvider(),
            "gemini": FakeProvider(),
            "openrouter": openrouter,
        }
    )

    result = await engine.chat_completion_stream(
        request("google/gemma-3-27b-it:free")
    )

    assert result.provider == "openrouter"
    assert result.model == "google/gemma-3-27b-it:free"
    assert openrouter.stream_requests[0].stream is True


@pytest.mark.asyncio
async def test_auto_stream_resolves_model_before_provider_call():
    groq = FakeProvider()
    engine = RouterEngine(
        {"groq": groq, "gemini": FakeProvider(), "openrouter": FakeProvider()}
    )

    result = await engine.chat_completion_stream(request("auto"))

    assert result.provider == "groq"
    assert result.model == "openai/gpt-oss-20b"
    assert groq.stream_requests[0].model == "openai/gpt-oss-20b"


@pytest.mark.asyncio
async def test_stream_forwards_chunks_and_logs_usage_after_completion():
    closed = False

    async def chunks():
        yield b'data: {"model":"served-model","usage":{"prompt_tokens":3,'
        yield b'"completion_tokens":2}}\n\ndata: [DONE]\n\n'

    async def close():
        nonlocal closed
        closed = True

    tasks = BackgroundTasks()
    routed_stream = RoutedStream(
        stream=ProviderStream(chunks=chunks(), close=close),
        provider="groq",
        model="openai/gpt-oss-20b",
    )
    received = [
        chunk
        async for chunk in chat_api.stream_with_logging(
            routed_stream, tasks, "key-id", 0
        )
    ]

    assert received == [
        b'data: {"model":"served-model","usage":{"prompt_tokens":3,',
        b'"completion_tokens":2}}\n\ndata: [DONE]\n\n',
    ]
    assert closed
    assert len(tasks.tasks) == 1
    assert tasks.tasks[0].args[1:] == (
        "groq",
        "served-model",
        3,
        2,
        tasks.tasks[0].args[5],
        200,
    )


@pytest.mark.parametrize(
    ("provider_type", "module_path", "setting_name", "model"),
    [
        (GroqProvider, "app.providers.groq", "groq_api_key", "openai/gpt-oss-20b"),
        (
            OpenRouterProvider,
            "app.providers.openrouter",
            "openrouter_api_key",
            "qwen/qwen-2.5-72b-instruct",
        ),
    ],
)
@pytest.mark.asyncio
async def test_provider_stream_opens_sse_without_buffering(
    monkeypatch, provider_type, module_path, setting_name, model
):
    contexts = []

    class FakeResponse:
        encoding = "utf-8"

        def raise_for_status(self):
            return None

        async def aiter_bytes(self):
            yield b"data: first\n\n"
            yield b"data: second\n\n"

    class FakeStreamContext:
        def __init__(self, client):
            self.client = client
            self.response = FakeResponse()
            self.closed = False

        async def __aenter__(self):
            return self.response

        async def __aexit__(self, exc_type, exc, traceback):
            self.closed = True

    class FakeClient:
        def __init__(self, **kwargs):
            self.closed = False

        def stream(self, method, url, **kwargs):
            context = FakeStreamContext(self)
            context.method = method
            context.url = url
            context.kwargs = kwargs
            contexts.append(context)
            return context

        async def aclose(self):
            self.closed = True

    monkeypatch.setattr(f"app.config.settings.{setting_name}", "test-key")
    monkeypatch.setattr(f"{module_path}.httpx.AsyncClient", FakeClient)
    provider = provider_type()

    result = await provider.chat_completion_stream(request(model))
    chunks = [chunk async for chunk in result.chunks]
    await result.close()

    assert contexts[0].method == "POST"
    assert contexts[0].kwargs["json"]["stream"] is True
    assert contexts[0].kwargs["headers"]["Authorization"] == "Bearer test-key"
    assert chunks == [b"data: first\n\n", b"data: second\n\n"]
    assert contexts[0].closed
    assert contexts[0].client.closed


@pytest.mark.asyncio
async def test_non_streaming_endpoint_keeps_json_response(monkeypatch):
    engine = RouterEngine(
        {"groq": FakeProvider(), "gemini": FakeProvider(), "openrouter": FakeProvider()}
    )
    monkeypatch.setattr(chat_api, "router_engine", engine)
    monkeypatch.setattr(chat_api, "save_request_log", lambda *args: None)

    result = await chat_api.chat_completions(
        request("auto"),
        BackgroundTasks(),
        type("APIKeyStub", (), {"id": "key-id"})(),
    )

    assert result == {"id": "ok"}


@pytest.mark.asyncio
async def test_streaming_endpoint_returns_sse_response(monkeypatch):
    engine = RouterEngine(
        {"groq": FakeProvider(), "gemini": FakeProvider(), "openrouter": FakeProvider()}
    )
    monkeypatch.setattr(chat_api, "router_engine", engine)
    monkeypatch.setattr(chat_api, "save_request_log", lambda *args: None)
    background_tasks = BackgroundTasks()

    response = await chat_api.chat_completions(
        request("openai/gpt-oss-20b", stream=True),
        background_tasks,
        type("APIKeyStub", (), {"id": "key-id"})(),
    )
    body = [chunk async for chunk in response.body_iterator]
    await response.background()

    assert response.media_type == "text/event-stream"
    assert body == [
        b'data: {"model":"test-model"}\n\n',
        b"data: [DONE]\n\n",
    ]

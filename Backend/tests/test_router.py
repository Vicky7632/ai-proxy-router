import os

os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("GROQ_API_KEY", "test-groq-key")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")

import pytest
from fastapi import HTTPException

from app.providers.gemini import GeminiProvider
from app.providers.groq import GroqProvider
from app.providers.openrouter import OpenRouterProvider
from app.providers.router import RouterEngine
from app.schemas.chat import ChatCompletionRequest


def request(model: str) -> ChatCompletionRequest:
    return ChatCompletionRequest(
        model=model,
        messages=[{"role": "user", "content": "Hello"}],
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
    def __init__(self, response=None, error=None):
        self.response = response or {"id": "ok"}
        self.error = error
        self.models = []

    async def chat_completion(self, request):
        self.models.append(request.model)
        if self.error:
            raise self.error
        return self.response


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

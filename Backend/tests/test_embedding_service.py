import os

os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("GROQ_API_KEY", "test-groq-key")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")

import httpx
import pytest
from fastapi import HTTPException

from app.config import settings
from app.services import embedding_service


class FakeResponse:
    def __init__(self, body, status_code=200):
        self.body = body
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            request = httpx.Request("POST", embedding_service.embedding_service.url)
            response = httpx.Response(
                self.status_code,
                request=request,
                text="request failed",
            )
            raise httpx.HTTPStatusError(
                "request failed",
                request=request,
                response=response,
            )

    def json(self):
        if isinstance(self.body, Exception):
            raise self.body
        return self.body


class FakeClient:
    def __init__(self, response=None, request_error=None):
        self.response = response
        self.request_error = request_error
        self.request = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        return None

    async def post(self, url, **kwargs):
        self.request = {"url": url, **kwargs}
        if self.request_error:
            raise self.request_error
        return self.response


def install_client(monkeypatch, client):
    monkeypatch.setattr(
        embedding_service.httpx,
        "AsyncClient",
        lambda timeout: client,
    )
    monkeypatch.setattr(settings, "gemini_api_key", "test-gemini-key")


@pytest.mark.asyncio
async def test_generate_embedding_returns_768_dimensions(monkeypatch):
    values = [index / 768 for index in range(768)]
    client = FakeClient(FakeResponse({"embedding": {"values": values}}))
    install_client(monkeypatch, client)

    result = await embedding_service.generate_embedding("hello")

    assert result == values
    assert len(result) == 768
    assert client.request["url"].endswith(
        "gemini-embedding-2-preview:embedContent"
    )
    assert client.request["params"] == {"key": "test-gemini-key"}
    assert client.request["json"] == {
        "model": "models/gemini-embedding-2-preview",
        "content": {"parts": [{"text": "hello"}]},
        "outputDimensionality": 768,
    }


@pytest.mark.asyncio
async def test_generate_embedding_rejects_empty_input():
    with pytest.raises(HTTPException) as error:
        await embedding_service.generate_embedding(" \t\n")

    assert error.value.status_code == 400
    assert error.value.detail == "Embedding input must not be empty"


@pytest.mark.asyncio
async def test_generate_embedding_handles_api_error_without_exposing_key(
    monkeypatch,
):
    client = FakeClient(FakeResponse({}, status_code=401))
    install_client(monkeypatch, client)

    with pytest.raises(HTTPException) as error:
        await embedding_service.generate_embedding("hello")

    assert error.value.status_code == 401
    assert "test-gemini-key" not in str(error.value)


@pytest.mark.asyncio
async def test_generate_embedding_handles_network_error_without_exposing_key(
    monkeypatch,
):
    request = httpx.Request(
        "POST",
        f"{embedding_service.embedding_service.url}?key=test-gemini-key",
    )
    client = FakeClient(
        request_error=httpx.ConnectError("connection failed", request=request)
    )
    install_client(monkeypatch, client)

    with pytest.raises(HTTPException) as error:
        await embedding_service.generate_embedding("hello")

    assert error.value.status_code == 502
    assert "test-gemini-key" not in str(error.value)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "body",
    [
        {},
        {"embedding": {}},
        {"embedding": {"values": [0.1]}},
        {"embedding": {"values": [float("nan")] * 768}},
    ],
)
async def test_generate_embedding_rejects_malformed_response(monkeypatch, body):
    client = FakeClient(FakeResponse(body))
    install_client(monkeypatch, client)

    with pytest.raises(HTTPException) as error:
        await embedding_service.generate_embedding("hello")

    assert error.value.status_code == 502
    assert error.value.detail == "Gemini returned an invalid embedding response"


@pytest.mark.asyncio
async def test_generate_embedding_rejects_invalid_json(monkeypatch):
    client = FakeClient(FakeResponse(ValueError("invalid JSON")))
    install_client(monkeypatch, client)

    with pytest.raises(HTTPException) as error:
        await embedding_service.generate_embedding("hello")

    assert error.value.status_code == 502

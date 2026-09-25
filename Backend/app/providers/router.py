from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException
import httpx

from app.providers.base import ProviderAdapter
from app.providers.gemini import GeminiProvider
from app.providers.groq import GroqProvider
from app.providers.openrouter import OpenRouterProvider
from app.schemas.chat import ChatCompletionRequest


MODEL_PROVIDERS = {
    "openai/gpt-oss-20b": "groq",
    "gemini-3.6-flash": "gemini",
    "qwen/qwen-2.5-72b-instruct": "openrouter",
    "google/gemma-3-27b-it:free": "openrouter",
}

PROVIDER_ORDER = ("groq", "gemini", "openrouter")
PROVIDER_MODELS = {
    "groq": "openai/gpt-oss-20b",
    "gemini": "gemini-3.6-flash",
    "openrouter": "qwen/qwen-2.5-72b-instruct",
}


@dataclass(frozen=True)
class RoutedCompletion:
    response: dict[str, Any]
    provider: str


class RouterEngine:
    """Resolve models and execute completions with provider fallback."""

    def __init__(
        self,
        providers: dict[str, ProviderAdapter] | None = None,
    ) -> None:
        self.providers = providers or {
            "groq": GroqProvider(),
            "gemini": GeminiProvider(),
            "openrouter": OpenRouterProvider(),
        }

    def provider_name(self, model: str) -> str:
        if model == "auto":
            return PROVIDER_ORDER[0]
        try:
            return MODEL_PROVIDERS[model]
        except KeyError as error:
            supported = ", ".join(["auto", *MODEL_PROVIDERS])
            raise HTTPException(
                status_code=400,
                detail=f"Unknown model '{model}'. Supported models: {supported}",
            ) from error

    def resolve(self, model: str) -> tuple[ProviderAdapter, str]:
        provider_name = self.provider_name(model)
        resolved_model = (
            PROVIDER_MODELS[provider_name] if model == "auto" else model
        )
        return self.providers[provider_name], resolved_model

    def resolve_provider(self, model: str) -> ProviderAdapter:
        provider, _ = self.resolve(model)
        return provider

    async def chat_completion(
        self, request: ChatCompletionRequest
    ) -> RoutedCompletion:
        initial_provider = self.provider_name(request.model)
        start_index = PROVIDER_ORDER.index(initial_provider)
        providers_to_try = PROVIDER_ORDER[start_index:]
        last_error: HTTPException | None = None

        for provider_name in providers_to_try:
            provider = self.providers[provider_name]
            resolved_model = (
                PROVIDER_MODELS[provider_name]
                if request.model == "auto"
                or provider_name != initial_provider
                else request.model
            )
            provider_request = request.model_copy(
                update={"model": resolved_model}
            )
            try:
                response = await provider.chat_completion(provider_request)
                return RoutedCompletion(response=response, provider=provider_name)
            except (HTTPException, httpx.TimeoutException, httpx.RequestError) as error:
                if not self._is_retryable(error):
                    raise
                last_error = self._as_http_exception(error)

        if last_error is not None:
            raise last_error
        raise HTTPException(status_code=502, detail="All providers failed")

    @staticmethod
    def _is_retryable(error: Exception) -> bool:
        if isinstance(error, HTTPException):
            return error.status_code == 429 or error.status_code >= 500
        return isinstance(error, (httpx.TimeoutException, httpx.RequestError))

    @staticmethod
    def _as_http_exception(error: Exception) -> HTTPException:
        if isinstance(error, HTTPException):
            return error
        return HTTPException(status_code=502, detail=f"Provider request failed: {error}")

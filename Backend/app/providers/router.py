from dataclasses import dataclass
import logging
from typing import Any

from fastapi import HTTPException
import httpx

from app.providers.base import ProviderAdapter, ProviderStream
from app.providers.gemini import GeminiProvider
from app.providers.groq import GroqProvider
from app.providers.openrouter import OpenRouterProvider
from app.schemas.chat import ChatCompletionRequest
from app.services.provider_health_service import (
    ProviderHealthService,
    provider_health_service,
)

logger = logging.getLogger(__name__)

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


@dataclass(frozen=True)
class RoutedStream:
    stream: ProviderStream
    provider: str
    model: str


class RouterEngine:
    """Resolve models and execute completions with provider fallback."""

    def __init__(
        self,
        providers: dict[str, ProviderAdapter] | None = None,
        health_service: ProviderHealthService | None = None,
    ) -> None:
        self.providers = providers or {
            "groq": GroqProvider(),
            "gemini": GeminiProvider(),
            "openrouter": OpenRouterProvider(),
        }
        self.health_service = health_service or provider_health_service

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
        providers_to_try = await self._providers_to_try(
            request.model,
            initial_provider,
        )
        last_error: HTTPException | None = None

        for provider_name in providers_to_try:
            if (
                request.model != "auto"
                and not await self._is_provider_healthy(provider_name)
            ):
                continue
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
                await self._record_provider_health(provider_name, success=True)
                return RoutedCompletion(response=response, provider=provider_name)
            except (HTTPException, httpx.TimeoutException, httpx.RequestError) as error:
                await self._record_provider_health(provider_name, success=False)
                if not self._is_retryable(error):
                    raise
                last_error = self._as_http_exception(error)

        if last_error is not None:
            raise last_error
        raise HTTPException(status_code=502, detail="All providers failed")

    async def chat_completion_stream(
        self, request: ChatCompletionRequest
    ) -> RoutedStream:
        initial_provider = self.provider_name(request.model)
        providers_to_try = await self._providers_to_try(
            request.model,
            initial_provider,
        )
        last_error: HTTPException | None = None

        for provider_name in providers_to_try:
            if (
                request.model != "auto"
                and not await self._is_provider_healthy(provider_name)
            ):
                continue
            provider = self.providers[provider_name]
            resolved_model = (
                PROVIDER_MODELS[provider_name]
                if request.model == "auto" or provider_name != initial_provider
                else request.model
            )
            provider_request = request.model_copy(
                update={"model": resolved_model, "stream": True}
            )
            try:
                stream = await provider.chat_completion_stream(provider_request)
                await self._record_provider_health(provider_name, success=True)
                return RoutedStream(
                    stream=stream,
                    provider=provider_name,
                    model=resolved_model,
                )
            except (HTTPException, httpx.TimeoutException, httpx.RequestError) as error:
                await self._record_provider_health(provider_name, success=False)
                if not self._is_retryable(error):
                    raise
                last_error = self._as_http_exception(error)

        if last_error is not None:
            raise last_error
        raise HTTPException(status_code=502, detail="All providers failed")

    async def _providers_to_try(
        self,
        model: str,
        initial_provider: str,
    ) -> tuple[str, ...]:
        if model != "auto":
            start_index = PROVIDER_ORDER.index(initial_provider)
            return PROVIDER_ORDER[start_index:]

        ranked_providers = []
        for order, provider_name in enumerate(PROVIDER_ORDER):
            if not await self._is_provider_healthy(provider_name):
                continue
            try:
                health = await self.health_service.get_health(provider_name)
                consecutive_failures = health.consecutive_failures
            except Exception:
                logger.exception(
                    "Provider health details unavailable provider=%s; "
                    "continuing routing",
                    provider_name,
                )
                consecutive_failures = 0
            ranked_providers.append(
                (consecutive_failures, order, provider_name)
            )

        ranked_providers.sort()
        return tuple(provider_name for _, _, provider_name in ranked_providers)

    async def _is_provider_healthy(self, provider_name: str) -> bool:
        try:
            return await self.health_service.is_provider_healthy(provider_name)
        except Exception:
            logger.exception(
                "Provider health check failed provider=%s; continuing routing",
                provider_name,
            )
            return True

    async def _record_provider_health(
        self,
        provider_name: str,
        *,
        success: bool,
    ) -> None:
        try:
            if success:
                await self.health_service.record_success(provider_name)
            else:
                await self.health_service.record_failure(provider_name)
        except RuntimeError:
            logger.exception(
                "Provider health update failed provider=%s success=%s",
                provider_name,
                success,
            )

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

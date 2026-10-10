from dataclasses import dataclass
import logging
from typing import Any, Callable

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
        self,
        request: ChatCompletionRequest,
        on_provider_attempt: Callable[[str, str], None] | None = None,
    ) -> RoutedCompletion:
        initial_provider = self.provider_name(request.model)
        providers_to_try = await self._providers_to_try(
            request.model,
            initial_provider,
        )
        last_error: HTTPException | None = None
        attempted_count = 0
        pending_fallback: tuple[str, str] | None = None

        for provider_name in providers_to_try:
            if (
                request.model != "auto"
                and not await self._is_provider_healthy(provider_name)
            ):
                logger.warning(
                    "Provider routing event=provider_skipped provider=%s "
                    "reason=unhealthy_cooldown routing_mode=explicit",
                    provider_name,
                )
                continue
            if pending_fallback is not None:
                failed_provider, error_category = pending_fallback
                logger.info(
                    "Provider routing event=provider_fallback "
                    "failed_provider=%s error_category=%s next_provider=%s",
                    failed_provider,
                    error_category,
                    provider_name,
                )
                pending_fallback = None
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
            attempt_type = "initial" if attempted_count == 0 else "fallback"
            attempted_count += 1
            logger.info(
                "Provider routing event=provider_attempt provider=%s "
                "resolved_model=%s attempt_type=%s routing_mode=%s",
                provider_name,
                resolved_model,
                attempt_type,
                "auto" if request.model == "auto" else "explicit",
            )
            try:
                if on_provider_attempt is not None:
                    on_provider_attempt(provider_name, resolved_model)
                response = await provider.chat_completion(provider_request)
                await self._record_provider_health(provider_name, success=True)
                logger.info(
                    "Provider routing event=provider_success provider=%s "
                    "resolved_model=%s attempt_type=%s routing_mode=%s",
                    provider_name,
                    resolved_model,
                    attempt_type,
                    "auto" if request.model == "auto" else "explicit",
                )
                return RoutedCompletion(response=response, provider=provider_name)
            except (HTTPException, httpx.TimeoutException, httpx.RequestError) as error:
                await self._record_provider_health(provider_name, success=False)
                if not self._is_retryable(error):
                    logger.error(
                        "Provider routing event=routing_failed provider=%s "
                        "reason=non_retryable error_category=%s",
                        provider_name,
                        self._error_category(error),
                    )
                    raise
                last_error = self._as_http_exception(error)
                pending_fallback = (
                    provider_name,
                    self._error_category(error),
                )

        if last_error is not None:
            logger.error(
                "Provider routing event=routing_failed "
                "reason=all_candidates_failed error_category=%s",
                self._error_category(last_error),
            )
            raise last_error
        logger.error(
            "Provider routing event=routing_failed "
            "reason=no_healthy_providers routing_mode=%s",
            "auto" if request.model == "auto" else "explicit",
        )
        raise HTTPException(status_code=502, detail="All providers failed")

    async def chat_completion_stream(
        self,
        request: ChatCompletionRequest,
        on_provider_attempt: Callable[[str, str], None] | None = None,
    ) -> RoutedStream:
        initial_provider = self.provider_name(request.model)
        providers_to_try = await self._providers_to_try(
            request.model,
            initial_provider,
        )
        last_error: HTTPException | None = None
        attempted_count = 0
        pending_fallback: tuple[str, str] | None = None

        for provider_name in providers_to_try:
            if (
                request.model != "auto"
                and not await self._is_provider_healthy(provider_name)
            ):
                logger.warning(
                    "Provider routing event=provider_skipped provider=%s "
                    "reason=unhealthy_cooldown routing_mode=explicit stream=true",
                    provider_name,
                )
                continue
            if pending_fallback is not None:
                failed_provider, error_category = pending_fallback
                logger.info(
                    "Provider routing event=provider_fallback "
                    "failed_provider=%s error_category=%s next_provider=%s "
                    "stream=true",
                    failed_provider,
                    error_category,
                    provider_name,
                )
                pending_fallback = None
            provider = self.providers[provider_name]
            resolved_model = (
                PROVIDER_MODELS[provider_name]
                if request.model == "auto" or provider_name != initial_provider
                else request.model
            )
            provider_request = request.model_copy(
                update={"model": resolved_model, "stream": True}
            )
            attempt_type = "initial" if attempted_count == 0 else "fallback"
            attempted_count += 1
            logger.info(
                "Provider routing event=provider_attempt provider=%s "
                "resolved_model=%s attempt_type=%s routing_mode=%s stream=true",
                provider_name,
                resolved_model,
                attempt_type,
                "auto" if request.model == "auto" else "explicit",
            )
            try:
                if on_provider_attempt is not None:
                    on_provider_attempt(provider_name, resolved_model)
                stream = await provider.chat_completion_stream(provider_request)
                await self._record_provider_health(provider_name, success=True)
                logger.info(
                    "Provider routing event=provider_success provider=%s "
                    "resolved_model=%s attempt_type=%s routing_mode=%s stream=true",
                    provider_name,
                    resolved_model,
                    attempt_type,
                    "auto" if request.model == "auto" else "explicit",
                )
                return RoutedStream(
                    stream=stream,
                    provider=provider_name,
                    model=resolved_model,
                )
            except (HTTPException, httpx.TimeoutException, httpx.RequestError) as error:
                await self._record_provider_health(provider_name, success=False)
                if not self._is_retryable(error):
                    logger.error(
                        "Provider routing event=routing_failed provider=%s "
                        "reason=non_retryable error_category=%s stream=true",
                        provider_name,
                        self._error_category(error),
                    )
                    raise
                last_error = self._as_http_exception(error)
                pending_fallback = (
                    provider_name,
                    self._error_category(error),
                )

        if last_error is not None:
            logger.error(
                "Provider routing event=routing_failed "
                "reason=all_candidates_failed error_category=%s stream=true",
                self._error_category(last_error),
            )
            raise last_error
        logger.error(
            "Provider routing event=routing_failed "
            "reason=no_healthy_providers routing_mode=%s stream=true",
            "auto" if request.model == "auto" else "explicit",
        )
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
                logger.warning(
                    "Provider routing event=provider_skipped provider=%s "
                    "reason=unhealthy_cooldown routing_mode=auto",
                    provider_name,
                )
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
        if ranked_providers:
            selected_failures, _, selected_provider = ranked_providers[0]
            logger.info(
                "Provider routing event=auto_selection routing_mode=auto "
                "selected_provider=%s consecutive_failures=%s candidates=%s",
                selected_provider,
                selected_failures,
                [
                    (provider_name, failures)
                    for failures, _, provider_name in ranked_providers
                ],
            )
        else:
            logger.info(
                "Provider routing event=auto_selection routing_mode=auto "
                "selected_provider=none candidates=[]"
            )
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

    @staticmethod
    def _error_category(error: Exception) -> str:
        if isinstance(error, HTTPException):
            if error.status_code == 429:
                return "http_429"
            if error.status_code >= 500:
                return "http_5xx"
            return "http_non_retryable"
        if isinstance(error, httpx.TimeoutException):
            return "timeout"
        if isinstance(error, httpx.RequestError):
            return "request_error"
        return "unknown"

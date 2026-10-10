import asyncio
import json
import logging
import time
from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from starlette.responses import Response, StreamingResponse
from fastapi.responses import JSONResponse
from app.services import cache_service

from app.db.models.api_key import APIKey
from app.db.models.provider import Provider
from app.db.models.request_log import RequestLog
from app.db.session import SessionLocal
from app.providers.router import RoutedStream, RouterEngine
from app.schemas.chat import ChatCompletionRequest
from app.services import budget_service
from app.services.api_key_service import get_api_key
from app.services.rate_limiter import rate_limiter
from app.services import semantic_cache_service

router = APIRouter()
logger = logging.getLogger(__name__)
router_engine = RouterEngine()


def save_request_log(
    api_key_id,
    provider_name: str | None,
    model: str,
    prompt_tokens: int | None,
    completion_tokens: int | None,
    latency_ms: int,
    status: int,
    redis_cache_status: str | None = None,
    semantic_cache_status: str | None = None,
    provider_called: bool | None = None,
) -> None:
    logger.info(
        "Request log background task started api_key_id=%s status=%s",
        api_key_id,
        status,
    )
    db = SessionLocal()
    request_log_id = None
    provider_configured = False
    try:
        provider = (
            db.query(Provider)
            .filter(Provider.name == provider_name)
            .first()
        )
        provider_id = provider.id if provider is not None else None
        provider_configured = provider is not None
        if provider is None:
            logger.warning(
                "Provider %s is not configured; saving request log with provider_id=NULL",
                provider_name,
            )

        logger.info(
            "Saving request log api_key_id=%s provider_id=%s status=%s database=%s host=%s",
            api_key_id,
            provider_id,
            status,
            db.bind.url.database if db.bind is not None else None,
            db.bind.url.host if db.bind is not None else None,
        )
        request_log = RequestLog(
            api_key_id=api_key_id,
            provider_id=provider_id,
            model=model,
            input_tokens=prompt_tokens or 0,
            output_tokens=completion_tokens or 0,
            latency_ms=latency_ms,
            status=str(status),
            redis_cache_status=redis_cache_status,
            semantic_cache_status=semantic_cache_status,
            provider_called=provider_called,
        )
        db.add(request_log)
        db.flush()
        request_log_id = request_log.id
        db.commit()
        logger.info("Request log saved api_key_id=%s status=%s", api_key_id, status)
    except Exception:
        db.rollback()
        logger.exception("Failed to save request log")
    finally:
        db.close()

    if (
        provider_configured
        and request_log_id is not None
        and status == 200
        and prompt_tokens is not None
        and completion_tokens is not None
    ):
        try:
            cost = budget_service.update_spend(
                api_key_id,
                provider_name,
                prompt_tokens,
                completion_tokens,
                request_log_id=request_log_id,
            )
            logger.info(
                "Request spend updated api_key_id=%s request_log_id=%s cost=%s",
                api_key_id,
                request_log_id,
                cost,
            )
        except Exception:
            logger.exception(
                "Failed to update spend api_key_id=%s request_log_id=%s",
                api_key_id,
                request_log_id,
            )


def format_budget_header(remaining_budget: float) -> str:
    return f"{remaining_budget:.8f}".rstrip("0").rstrip(".")


class _StreamCompletionAssembler:
    def __init__(self) -> None:
        self.pending = b""
        self.id: str | None = None
        self.model: str | None = None
        self.created: int | None = None
        self.usage: dict[str, Any] | None = None
        self.metadata: dict[str, Any] = {}
        self.choices: dict[int, dict[str, Any]] = {}
        self.done = False
        self.has_error = False

    def feed(self, chunk: bytes) -> None:
        self.pending += chunk
        normalized = self.pending.replace(b"\r\n", b"\n")
        frames = normalized.split(b"\n\n")
        self.pending = frames.pop()
        for frame in frames:
            self._consume_frame(frame)

    def finish(self) -> None:
        if self.pending:
            self._consume_frame(self.pending.replace(b"\r\n", b"\n"))
            self.pending = b""

    def _consume_frame(self, frame: bytes) -> None:
        data_lines = [
            line[5:].strip()
            for line in frame.split(b"\n")
            if line.startswith(b"data:")
        ]
        if not data_lines:
            return
        payload = b"\n".join(data_lines).strip()
        if payload == b"[DONE]":
            self.done = True
            return
        try:
            event = json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError):
            self.has_error = True
            return
        if not isinstance(event, dict):
            self.has_error = True
            return
        if event.get("error") is not None:
            self.has_error = True
            return

        self.id = event.get("id") or self.id
        self.model = event.get("model") or self.model
        self.created = event.get("created") or self.created
        usage = event.get("usage")
        if isinstance(usage, dict):
            self.usage = usage
        for key, value in event.items():
            if key not in {"id", "object", "created", "model", "choices", "usage"}:
                self.metadata[key] = value

        choices = event.get("choices")
        if not isinstance(choices, list):
            return
        for choice in choices:
            if not isinstance(choice, dict):
                continue
            index = choice.get("index", 0)
            if not isinstance(index, int):
                continue
            state = self.choices.setdefault(
                index,
                {
                    "message": {"role": "assistant"},
                    "tool_calls": {},
                    "finish_reason": None,
                },
            )
            delta = choice.get("delta")
            if isinstance(delta, dict):
                self._merge_delta(state, delta)
            for key, value in choice.items():
                if key not in {"index", "delta", "finish_reason"}:
                    state[key] = value
            if choice.get("finish_reason") is not None:
                state["finish_reason"] = choice["finish_reason"]

    @staticmethod
    def _append_string(target: dict[str, Any], key: str, value: Any) -> None:
        if not isinstance(value, str):
            target[key] = value
            return
        previous = target.get(key)
        target[key] = (previous if isinstance(previous, str) else "") + value

    @classmethod
    def _merge_function(
        cls,
        target: dict[str, Any],
        incoming: dict[str, Any],
    ) -> None:
        for key, value in incoming.items():
            if key in {"name", "arguments"} and isinstance(value, str):
                cls._append_string(target, key, value)
            else:
                target[key] = value

    @classmethod
    def _merge_delta(
        cls,
        state: dict[str, Any],
        delta: dict[str, Any],
    ) -> None:
        message = state["message"]
        for key, value in delta.items():
            if key == "tool_calls" and isinstance(value, list):
                for position, tool_call in enumerate(value):
                    if not isinstance(tool_call, dict):
                        continue
                    call_index = tool_call.get("index", position)
                    if not isinstance(call_index, int) or isinstance(
                        call_index, bool
                    ):
                        continue
                    call = state["tool_calls"].setdefault(call_index, {})
                    for call_key, call_value in tool_call.items():
                        if call_key == "index":
                            continue
                        if call_key == "function" and isinstance(call_value, dict):
                            function = call.setdefault("function", {})
                            cls._merge_function(function, call_value)
                        else:
                            call[call_key] = call_value
            elif key == "function_call" and isinstance(value, dict):
                function_call = message.setdefault("function_call", {})
                cls._merge_function(function_call, value)
            elif key == "content" or key == "refusal":
                cls._append_string(message, key, value)
            elif key in {"reasoning", "reasoning_content"}:
                cls._append_string(message, key, value)
            else:
                message[key] = value

    def completion(self) -> dict[str, Any] | None:
        if (
            not self.done
            or self.has_error
            or not self.choices
            or any(state["finish_reason"] is None for state in self.choices.values())
        ):
            return None
        choices = []
        for index, state in sorted(self.choices.items()):
            message = dict(state["message"])
            if state["tool_calls"]:
                message["tool_calls"] = [
                    call
                    for _, call in sorted(state["tool_calls"].items())
                ]
            choice = {
                key: value
                for key, value in state.items()
                if key not in {"message", "tool_calls"}
            }
            choice.update(
                {
                    "index": index,
                    "message": message,
                    "finish_reason": state["finish_reason"],
                }
            )
            choices.append(choice)
        response = {
            "id": self.id or f"chatcmpl-{uuid4().hex}",
            "object": "chat.completion",
            "created": self.created or int(time.time()),
            "model": self.model or "",
            "choices": choices,
        }
        response.update(self.metadata)
        if self.usage is not None:
            response["usage"] = self.usage
        return response


def _cached_sse_chunks(response_data: dict[str, Any]) -> list[bytes]:
    completion_id = response_data.get("id") or f"chatcmpl-{uuid4().hex}"
    created = response_data.get("created") or int(time.time())
    model = response_data.get("model") or ""
    base = {
        key: value
        for key, value in response_data.items()
        if key not in {"id", "object", "created", "model", "choices", "usage"}
    }

    def encode(
        choices: list[dict[str, Any]],
        usage: dict[str, Any] | None = None,
    ) -> bytes:
        event = {
            **base,
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": choices,
        }
        if usage is not None:
            event["usage"] = usage
        return b"data: " + json.dumps(
            event, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8") + b"\n\n"

    chunks = []
    has_choice = False
    choices = response_data.get("choices")
    if isinstance(choices, list):
        for choice in choices:
            if not isinstance(choice, dict):
                continue
            has_choice = True
            message = choice.get("message")
            delta = dict(message) if isinstance(message, dict) else {}
            chunks.append(
                encode(
                    [
                        {
                            "index": choice.get("index", 0),
                            "delta": delta,
                            "finish_reason": None,
                        }
                    ]
                )
            )
            chunks.append(
                encode(
                    [
                        {
                            **{
                                key: value
                                for key, value in choice.items()
                                if key
                                not in {"index", "message", "finish_reason"}
                            },
                            "index": choice.get("index", 0),
                            "delta": {},
                            "finish_reason": choice.get("finish_reason") or "stop",
                        }
                    ]
                )
            )
    if not has_choice:
        chunks.extend(
            [
                encode(
                    [
                        {
                            "index": 0,
                            "delta": {"role": "assistant"},
                            "finish_reason": None,
                        }
                    ]
                ),
                encode(
                    [{"index": 0, "delta": {}, "finish_reason": "stop"}]
                ),
            ]
        )
    usage = response_data.get("usage")
    if isinstance(usage, dict):
        chunks.append(encode([], usage))
    chunks.append(b"data: [DONE]\n\n")
    return chunks


async def stream_cached_response(
    response_data: dict[str, Any],
    background_tasks: BackgroundTasks,
    api_key_id,
    started_at: float,
    redis_cache_status: str,
    semantic_cache_status: str | None,
) -> AsyncIterator[bytes]:
    status = 200
    try:
        for chunk in _cached_sse_chunks(response_data):
            yield chunk
    except asyncio.CancelledError:
        status = 499
        raise
    except GeneratorExit:
        status = 499
        raise
    finally:
        log_args = (
            api_key_id,
            "cache",
            response_data.get("model", ""),
            None,
            None,
            round((time.perf_counter() - started_at) * 1000),
            status,
            redis_cache_status,
            semantic_cache_status,
            False,
        )
        if status == 200:
            background_tasks.add_task(save_request_log, *log_args)
        else:
            await asyncio.to_thread(save_request_log, *log_args)


async def stream_with_logging(
    routed_stream: RoutedStream,
    background_tasks: BackgroundTasks,
    api_key_id,
    started_at: float,
    redis_cache_status: str | None = None,
    semantic_cache_status: str | None = None,
    cache_key: str | None = None,
    semantic_lookup: semantic_cache_service.SemanticCacheLookup | None = None,
    cache_request: ChatCompletionRequest | None = None,
    provider_called: bool = False,
) -> AsyncIterator[bytes]:
    assembler = _StreamCompletionAssembler()
    status = 200
    stream_closed = False

    try:
        async for chunk in routed_stream.stream.chunks:
            assembler.feed(chunk)
            yield chunk
        assembler.finish()
        status = 502 if not assembler.done or assembler.has_error else 200
        stream_closed = True
        await routed_stream.stream.close()
        response_data = assembler.completion()
        if status == 200 and response_data is not None:
            if cache_key is not None and cache_request is not None:
                cache_saved = await cache_service.save_cached_response(
                    request=cache_request,
                    response=response_data,
                    cache_key=cache_key,
                )
                if cache_saved:
                    logger.info(
                        "event=stream_cache_save cache_type=redis "
                        "outcome=saved model=%s provider=%s",
                        cache_request.model,
                        routed_stream.provider,
                    )
            if semantic_lookup is not None:
                await semantic_cache_service.save_semantic_cache(
                    semantic_lookup,
                    response_data,
                    cache_request.model
                    if cache_request is not None
                    else routed_stream.model,
                    routed_stream.provider,
                )
    except HTTPException as error:
        status = error.status_code
        raise
    except asyncio.CancelledError:
        status = 499
        raise
    except GeneratorExit:
        status = 499
        raise
    except Exception:
        status = 502
        raise
    finally:
        try:
            if not stream_closed:
                stream_closed = True
                try:
                    await routed_stream.stream.close()
                except Exception:
                    status = 502
                    raise
        finally:
            log_args = (
                api_key_id,
                routed_stream.provider,
                assembler.model or routed_stream.model,
                (assembler.usage or {}).get("prompt_tokens"),
                (assembler.usage or {}).get("completion_tokens"),
                round((time.perf_counter() - started_at) * 1000),
                status,
                redis_cache_status,
                semantic_cache_status,
                provider_called,
            )
            if status == 200:
                background_tasks.add_task(save_request_log, *log_args)
            else:
                await asyncio.to_thread(save_request_log, *log_args)


@router.post("/v1/chat/completions")
async def chat_completions(
    request: ChatCompletionRequest,
    background_tasks: BackgroundTasks,
    response: Response,
    api_key: APIKey = Depends(get_api_key),
):
    started_at = time.perf_counter()
    remaining_budget = None
    cache_key = None
    redis_cache_status = None
    semantic_cache_status = None
    provider_called = False
    request_log_provider = None

    def mark_provider_called(provider_name: str, model: str) -> None:
        nonlocal provider_called, request_log_provider
        provider_called = True
        request_log_provider = provider_name
        if request.stream:
            logger.info(
                "event=provider_invocation request_mode=stream "
                "provider=%s model=%s",
                provider_name,
                model,
            )

    try:
        # Existing auth/rate-limit/budget flow
        await rate_limiter.check_limit(api_key.id)
        remaining_budget = await budget_service.check_budget(api_key)

        # Resolve model before caching so identical routed requests hash the same
        _, resolved_model = router_engine.resolve(request.model)
        request = request.model_copy(update={"model": resolved_model})

        cache_key = cache_service.get_cache_key(request)
        cache_lookup = await cache_service.lookup_cached_response(
            request=request,
            cache_key=cache_key,
        )
        cached_response = cache_lookup.response
        redis_cache_status = cache_lookup.status

        if cached_response is not None:
            logger.info(
                "event=cache_lookup outcome=redis_hit cache_type=redis "
                "request_mode=%s model=%s",
                "stream" if request.stream else "non_stream",
                request.model,
            )
            headers = {"X-Cache": "HIT"}
            if remaining_budget is not None:
                headers["X-Remaining-Budget"] = format_budget_header(
                    remaining_budget
                )
            if request.stream:
                return StreamingResponse(
                    stream_cached_response(
                        cached_response,
                        background_tasks,
                        api_key.id,
                        started_at,
                        redis_cache_status,
                        semantic_cache_status,
                    ),
                    media_type="text/event-stream",
                    background=background_tasks,
                    headers=headers,
                )
            background_tasks.add_task(
                save_request_log,
                api_key.id,
                "cache",
                request.model,
                None,
                None,
                round((time.perf_counter() - started_at) * 1000),
                200,
                redis_cache_status,
                semantic_cache_status,
                provider_called,
            )
            return JSONResponse(
                content=cached_response,
                headers=headers,
                background=background_tasks,
            )

        logger.info(
            "event=cache_lookup outcome=redis_%s cache_type=redis "
            "request_mode=%s model=%s",
            redis_cache_status,
            "stream" if request.stream else "non_stream",
            request.model,
        )
        semantic_prompt = json.dumps(
            [
                {"role": message.role, "content": message.content}
                for message in request.messages
            ],
            ensure_ascii=False,
            separators=(",", ":"),
        )
        semantic_lookup = await semantic_cache_service.lookup_semantic_cache(
            semantic_prompt,
            request.model,
            request.temperature,
        )
        semantic_cache_status = (
            "hit"
            if semantic_lookup.hit is not None
            else semantic_lookup.status
        )
        logger.info(
            "event=cache_lookup outcome=%s cache_type=semantic "
            "request_mode=%s model=%s",
            f"semantic_{semantic_cache_status}",
            "stream" if request.stream else "non_stream",
            request.model,
        )
        if semantic_lookup.hit is not None:
            headers = {"X-Cache": "HIT"}
            if remaining_budget is not None:
                headers["X-Remaining-Budget"] = format_budget_header(
                    remaining_budget
                )
            if request.stream:
                return StreamingResponse(
                    stream_cached_response(
                        semantic_lookup.hit.response,
                        background_tasks,
                        api_key.id,
                        started_at,
                        redis_cache_status,
                        semantic_cache_status,
                    ),
                    media_type="text/event-stream",
                    background=background_tasks,
                    headers=headers,
                )
            background_tasks.add_task(
                save_request_log,
                api_key.id,
                "cache",
                request.model,
                None,
                None,
                round((time.perf_counter() - started_at) * 1000),
                200,
                redis_cache_status,
                semantic_cache_status,
                provider_called,
            )
            return JSONResponse(
                content=semantic_lookup.hit.response,
                headers=headers,
                background=background_tasks,
            )

        if request.stream:
            routed_stream = await router_engine.chat_completion_stream(
                request,
                on_provider_attempt=mark_provider_called,
            )

            headers = {"X-Cache": "MISS"}
            if remaining_budget is not None:
                headers["X-Remaining-Budget"] = format_budget_header(
                    remaining_budget
                )

            return StreamingResponse(
                stream_with_logging(
                    routed_stream,
                    background_tasks,
                    api_key.id,
                    started_at,
                    redis_cache_status,
                    semantic_cache_status,
                    cache_key,
                    semantic_lookup,
                    request,
                    provider_called,
                ),
                media_type="text/event-stream",
                background=background_tasks,
                headers=headers,
            )

        # ---------- PROVIDER CALL ----------
        routed_completion = await router_engine.chat_completion(
            request,
            on_provider_attempt=mark_provider_called,
        )
        response_data = routed_completion.response
        serving_provider = routed_completion.provider

        # ---------- CACHE SAVE ----------
        if cache_key is not None:
            await cache_service.save_cached_response(
                request=request,
                response=response_data,
                cache_key=cache_key,
            )
        if semantic_lookup is not None:
            await semantic_cache_service.save_semantic_cache(
                semantic_lookup,
                response_data,
                request.model,
                serving_provider,
            )

    except HTTPException as error:
        background_tasks.add_task(
            save_request_log,
            api_key.id,
            request_log_provider,
            request.model,
            None,
            None,
            round((time.perf_counter() - started_at) * 1000),
            error.status_code,
            redis_cache_status,
            semantic_cache_status,
            provider_called,
        )
        raise

    # Existing logging
    usage = response_data.get("usage") or {}
    response_model = response_data.get("model") or request.model

    background_tasks.add_task(
        save_request_log,
        api_key.id,
        serving_provider,
        response_model,
        usage.get("prompt_tokens"),
        usage.get("completion_tokens"),
        round((time.perf_counter() - started_at) * 1000),
        200,
        redis_cache_status,
        semantic_cache_status,
        provider_called,
    )

    # ---------- FINAL RESPONSE ----------
    headers = {"X-Cache": "MISS"}

    if remaining_budget is not None:
        headers["X-Remaining-Budget"] = format_budget_header(
            remaining_budget
        )

    return JSONResponse(
        content=response_data,
        headers=headers,
        background=background_tasks,
    )
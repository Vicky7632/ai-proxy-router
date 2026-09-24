import time
from typing import Any
from uuid import uuid4

import httpx
from fastapi import HTTPException

from app.config import settings
from app.providers.base import ProviderAdapter
from app.schemas.chat import ChatCompletionRequest


class GeminiProvider(ProviderAdapter):
    url = "https://generativelanguage.googleapis.com/v1beta/models"

    async def chat_completion(
        self, request: ChatCompletionRequest
    ) -> dict[str, Any]:
        if not settings.gemini_api_key:
            raise HTTPException(
                status_code=500,
                detail="GEMINI_API_KEY is not configured",
            )

        contents: list[dict[str, Any]] = []
        system_parts: list[dict[str, str]] = []
        for message in request.messages:
            part = {"text": message.content}
            if message.role == "system":
                system_parts.append(part)
            else:
                role = "model" if message.role == "assistant" else "user"
                contents.append({"role": role, "parts": [part]})

        payload: dict[str, Any] = {
            "contents": contents,
            "generationConfig": {"temperature": request.temperature},
        }
        if system_parts:
            payload["systemInstruction"] = {"parts": system_parts}

        endpoint = f"{self.url}/{request.model}:generateContent"
        headers = {"Content-Type": "application/json"}

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(
                    endpoint,
                    params={"key": settings.gemini_api_key},
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()
            except httpx.HTTPStatusError as error:
                raise HTTPException(
                    status_code=error.response.status_code,
                    detail=error.response.text,
                ) from error
            except httpx.RequestError as error:
                raise HTTPException(
                    status_code=502,
                    detail=f"Provider request failed: {str(error)}",
                ) from error

        return self._normalize_response(response.json(), request.model)

    @staticmethod
    def _normalize_response(
        response: dict[str, Any], model: str
    ) -> dict[str, Any]:
        candidates = response.get("candidates") or []
        candidate = candidates[0] if candidates else {}
        parts = (candidate.get("content") or {}).get("parts") or []
        content = "".join(
            part.get("text", "") for part in parts if isinstance(part, dict)
        )
        usage = response.get("usageMetadata") or {}
        finish_reason = candidate.get("finishReason")
        finish_reason_map = {
            "STOP": "stop",
            "MAX_TOKENS": "length",
        }

        return {
            "id": f"gemini-{uuid4().hex}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": content},
                    "finish_reason": finish_reason_map.get(
                        finish_reason, finish_reason
                    ),
                }
            ],
            "usage": {
                "prompt_tokens": usage.get("promptTokenCount", 0),
                "completion_tokens": usage.get("candidatesTokenCount", 0),
                "total_tokens": usage.get("totalTokenCount", 0),
            },
        }
from typing import Any

import httpx
from fastapi import HTTPException

from app.config import settings
from app.providers.base import ProviderAdapter
from app.schemas.chat import ChatCompletionRequest


class GroqProvider(ProviderAdapter):
    url = "https://api.groq.com/openai/v1/chat/completions"

    async def chat_completion(
        self, request: ChatCompletionRequest
    ) -> dict[str, Any]:
        if not settings.groq_api_key:
            raise HTTPException(
                status_code=500,
                detail="GROQ_API_KEY is not configured",
            )

        headers = {
            "Authorization": f"Bearer {settings.groq_api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(
                    self.url,
                    json=request.model_dump(),
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

        return response.json()
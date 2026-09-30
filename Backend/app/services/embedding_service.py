import math
from typing import Any

import httpx
from fastapi import HTTPException

from app.config import settings


class GeminiEmbeddingService:
    model = "models/gemini-embedding-2-preview"
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        "gemini-embedding-2-preview:embedContent"
    )
    output_dimensions = 768

    async def generate_embedding(self, text: str) -> list[float]:
        if not text or not text.strip():
            raise HTTPException(
                status_code=400,
                detail="Embedding input must not be empty",
            )
        if not settings.gemini_api_key:
            raise HTTPException(
                status_code=500,
                detail="GEMINI_API_KEY is not configured",
            )

        payload = {
            "model": self.model,
            "content": {"parts": [{"text": text}]},
            "outputDimensionality": self.output_dimensions,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(
                    self.url,
                    params={"key": settings.gemini_api_key},
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
                response.raise_for_status()
            except httpx.HTTPStatusError as error:
                raise HTTPException(
                    status_code=error.response.status_code,
                    detail="Gemini embedding request failed",
                ) from None
            except httpx.RequestError:
                raise HTTPException(
                    status_code=502,
                    detail="Gemini embedding request failed",
                ) from None

        try:
            result: Any = response.json()
        except ValueError:
            raise HTTPException(
                status_code=502,
                detail="Gemini returned an invalid embedding response",
            ) from None

        values = (
            result.get("embedding", {}).get("values")
            if isinstance(result, dict)
            and isinstance(result.get("embedding"), dict)
            else None
        )
        if not self._is_valid_embedding(values):
            raise HTTPException(
                status_code=502,
                detail="Gemini returned an invalid embedding response",
            )

        return [float(value) for value in values]

    def _is_valid_embedding(self, values: Any) -> bool:
        if not isinstance(values, list) or len(values) != self.output_dimensions:
            return False
        for value in values:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                return False
            try:
                if not math.isfinite(float(value)):
                    return False
            except OverflowError:
                return False
        return True


embedding_service = GeminiEmbeddingService()


async def generate_embedding(text: str) -> list[float]:
    return await embedding_service.generate_embedding(text)

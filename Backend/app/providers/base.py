from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException

from app.schemas.chat import ChatCompletionRequest


@dataclass
class ProviderStream:
    chunks: AsyncIterator[bytes]
    close: Callable[[], Awaitable[None]]


class ProviderAdapter(ABC):
    @abstractmethod
    async def chat_completion(
        self, request: ChatCompletionRequest
    ) -> dict[str, Any]:
        """Create a chat completion using the provider."""
        raise NotImplementedError

    async def chat_completion_stream(
        self, request: ChatCompletionRequest
    ) -> ProviderStream:
        raise HTTPException(
            status_code=501,
            detail=f"{self.__class__.__name__} does not support streaming",
        )
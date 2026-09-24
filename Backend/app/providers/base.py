from abc import ABC, abstractmethod
from typing import Any

from app.schemas.chat import ChatCompletionRequest


class ProviderAdapter(ABC):
    @abstractmethod
    async def chat_completion(
        self, request: ChatCompletionRequest
    ) -> dict[str, Any]:
        """Create a chat completion using the provider."""
        raise NotImplementedError
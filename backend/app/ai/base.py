"""Abstract base class for AI providers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import AsyncIterator


@dataclass
class GenerationParams:
    temperature: float = 0.7
    max_tokens: int = 4096
    top_p: float = 1.0
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0
    extra: dict = field(default_factory=dict)


@dataclass
class ModelResponse:
    content: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    model: str = ""


class BaseProvider(ABC):
    """Abstract AI provider interface."""

    def __init__(self, api_key: str, model: str, api_base: str | None = None):
        self.api_key = api_key
        self.model = model
        self.api_base = api_base

    @abstractmethod
    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        params: GenerationParams | None = None,
    ) -> ModelResponse:
        """Generate a complete response (non-streaming)."""
        ...

    @abstractmethod
    async def stream_generate(
        self,
        system_prompt: str,
        user_prompt: str,
        params: GenerationParams | None = None,
    ) -> AsyncIterator[str]:
        """Generate response as a stream of text chunks."""
        ...

    @abstractmethod
    async def validate_connection(self) -> tuple[bool, str]:
        """Test that the API connection works. Returns (success, message)."""
        ...

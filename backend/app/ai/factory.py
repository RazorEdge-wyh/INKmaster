"""Provider factory — registry + factory for AI providers."""

from app.ai.base import BaseProvider
from app.ai.openai_provider import OpenAIProvider
from app.ai.anthropic_provider import AnthropicProvider


class ProviderFactory:
    _registry: dict[str, type[BaseProvider]] = {
        "openai": OpenAIProvider,
        "deepseek": OpenAIProvider,
        "ollama": OpenAIProvider,
        "anthropic": AnthropicProvider,
    }

    @classmethod
    def register(cls, name: str, provider_cls: type[BaseProvider]) -> None:
        cls._registry[name] = provider_cls

    @classmethod
    def create(
        cls,
        provider: str,
        api_key: str,
        model: str,
        api_base: str | None = None,
    ) -> BaseProvider:
        provider_cls = cls._registry.get(provider)
        if not provider_cls:
            raise ValueError(f"Unknown provider: {provider}. Available: {list(cls._registry.keys())}")
        return provider_cls(api_key=api_key, model=model, api_base=api_base)

    @classmethod
    def list_providers(cls) -> list[str]:
        return list(cls._registry.keys())

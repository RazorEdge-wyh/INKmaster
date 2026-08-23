"""Anthropic Claude provider."""

import asyncio
from typing import AsyncIterator
from anthropic import AsyncAnthropic
from app.ai.base import BaseProvider, GenerationParams, ModelResponse


class AnthropicProvider(BaseProvider):
    """Provider for Anthropic Claude models."""

    def __init__(self, api_key: str, model: str, api_base: str | None = None):
        super().__init__(api_key, model, api_base)
        self.client = AsyncAnthropic(
            api_key=api_key,
            base_url=api_base or None,
            timeout=300.0,
            max_retries=2,
        )

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        params: GenerationParams | None = None,
    ) -> ModelResponse:
        p = params or GenerationParams()

        for attempt in range(3):
            try:
                response = await self.client.messages.create(
                    model=self.model,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_prompt}],
                    temperature=p.temperature,
                    max_tokens=p.max_tokens,
                )
                text = ""
                for block in response.content:
                    if block.type == "text":
                        text += block.text
                return ModelResponse(
                    content=text,
                    prompt_tokens=response.usage.input_tokens if response.usage else 0,
                    completion_tokens=response.usage.output_tokens if response.usage else 0,
                    model=response.model,
                )
            except Exception as e:
                if attempt >= 2:
                    raise
                await asyncio.sleep(2 ** attempt)
        else:
            raise RuntimeError("Unexpected: all retries exhausted")

    async def stream_generate(
        self,
        system_prompt: str,
        user_prompt: str,
        params: GenerationParams | None = None,
    ) -> AsyncIterator[str]:
        p = params or GenerationParams()

        for attempt in range(3):
            try:
                async with self.client.messages.stream(
                    model=self.model,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_prompt}],
                    temperature=p.temperature,
                    max_tokens=p.max_tokens,
                ) as stream:
                    async for text in stream.text_stream:
                        yield text
                return
            except Exception as e:
                if attempt >= 2:
                    raise
                await asyncio.sleep(2 ** attempt)

    async def validate_connection(self) -> tuple[bool, str]:
        try:
            response = await self.generate("Say hello.", "Hi!", GenerationParams(max_tokens=10))
            return True, f"连接成功 (模型: {response.model})"
        except Exception as e:
            return False, str(e)

    async def close(self):
        """Close the underlying HTTP client."""
        await self.client.close()

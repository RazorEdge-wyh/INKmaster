"""OpenAI-compatible provider (OpenAI, DeepSeek, Ollama)."""

import asyncio
from typing import AsyncIterator
from openai import AsyncOpenAI
from app.ai.base import BaseProvider, GenerationParams, ModelResponse


class OpenAIProvider(BaseProvider):
    """Provider for OpenAI and OpenAI-compatible APIs (DeepSeek, Ollama, etc.)."""

    def __init__(self, api_key: str, model: str, api_base: str | None = None):
        super().__init__(api_key, model, api_base)
        self.client = AsyncOpenAI(
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
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        for attempt in range(3):
            try:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=p.temperature,
                    max_tokens=p.max_tokens,
                    top_p=p.top_p,
                    frequency_penalty=p.frequency_penalty,
                )
                choice = response.choices[0]
                return ModelResponse(
                    content=choice.message.content or "",
                    prompt_tokens=response.usage.prompt_tokens if response.usage else 0,
                    completion_tokens=response.usage.completion_tokens if response.usage else 0,
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
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        for attempt in range(3):
            try:
                stream = await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=p.temperature,
                    max_tokens=p.max_tokens,
                    top_p=p.top_p,
                    frequency_penalty=p.frequency_penalty,
                    stream=True,
                )
                async for chunk in stream:
                    if chunk.choices and chunk.choices[0].delta.content:
                        yield chunk.choices[0].delta.content
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

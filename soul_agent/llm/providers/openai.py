"""OpenAI兼容API提供商"""

import json

from openai import AsyncOpenAI

from soul_agent.config.settings import LLMConfig
from soul_agent.utils.logger import logger


class LLMResponse:
    def __init__(self, content="", tool_calls=None, usage=None):
        self.content = content
        self.tool_calls = tool_calls or []
        self.usage = usage

    @property
    def has_tool_calls(self):
        return len(self.tool_calls) > 0


class OpenAIProvider:
    def __init__(self, config: LLMConfig):
        self.config = config
        self.client = AsyncOpenAI(
            api_key=config.api_key or "sk-placeholder",
            base_url=config.base_url,
        )
        self.model = config.model

    async def chat(self, messages, tools=None, stream=True) -> LLMResponse:
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        if stream and not tools:
            return await self._stream_chat(**kwargs)
        else:
            return await self._normal_chat(**kwargs)

    async def _normal_chat(self, **kwargs) -> LLMResponse:
        response = await self.client.chat.completions.create(**kwargs)
        choice = response.choices[0]
        return LLMResponse(
            content=choice.message.content or "",
            tool_calls=self._parse_tool_calls(choice.message.tool_calls),
            usage=response.usage,
        )

    async def _stream_chat(self, **kwargs) -> LLMResponse:
        kwargs["stream"] = True
        chunks = []
        async for chunk in await self.client.chat.completions.create(**kwargs):
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta and delta.content:
                chunks.append(delta.content)

        return LLMResponse(content="".join(chunks))

    def _parse_tool_calls(self, tool_calls):
        if not tool_calls:
            return []
        result = []
        for tc in tool_calls:
            result.append({
                "id": tc.id,
                "name": tc.function.name,
                "arguments": json.loads(tc.function.arguments),
            })
        return result

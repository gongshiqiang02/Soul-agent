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

    async def chat(self, messages, tools=None, stream=True, on_delta=None) -> LLMResponse:
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        if stream:
            return await self._stream_chat(on_delta=on_delta, **kwargs)
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

    async def _stream_chat(self, on_delta=None, **kwargs) -> LLMResponse:
        """流式聊天,支持tools和usage获取"""
        kwargs["stream"] = True

        # 尝试获取usage
        try:
            kwargs["stream_options"] = {"include_usage": True}
        except Exception:
            pass

        content_chunks = []
        tool_calls_dict = {}  # {index: {"id": ..., "name": ..., "arguments": ""}}
        usage = None

        try:
            async for chunk in await self.client.chat.completions.create(**kwargs):
                # 处理usage
                if hasattr(chunk, "usage") and chunk.usage:
                    usage = chunk.usage

                if not chunk.choices:
                    continue

                delta = chunk.choices[0].delta

                # 处理content
                if delta.content:
                    content_chunks.append(delta.content)
                    if on_delta:
                        on_delta(delta.content)

                # 处理tool_calls
                if delta.tool_calls:
                    for tc_delta in delta.tool_calls:
                        idx = tc_delta.index
                        if idx not in tool_calls_dict:
                            tool_calls_dict[idx] = {
                                "id": tc_delta.id or "",
                                "name": tc_delta.function.name if tc_delta.function else "",
                                "arguments": "",
                            }
                        if tc_delta.id:
                            tool_calls_dict[idx]["id"] = tc_delta.id
                        if tc_delta.function:
                            if tc_delta.function.name:
                                tool_calls_dict[idx]["name"] = tc_delta.function.name
                            if tc_delta.function.arguments:
                                tool_calls_dict[idx]["arguments"] += tc_delta.function.arguments

        except Exception as e:
            # 若stream_options不支持,重试不带usage
            if "stream_options" in str(e) and "stream_options" in kwargs:
                logger.warning("后端不支持stream_options,重试不获取usage")
                del kwargs["stream_options"]
                return await self._stream_chat(on_delta=on_delta, **kwargs)
            raise

        # 解析tool_calls的arguments
        tool_calls = []
        for idx in sorted(tool_calls_dict.keys()):
            tc = tool_calls_dict[idx]
            try:
                tc["arguments"] = json.loads(tc["arguments"]) if tc["arguments"] else {}
            except json.JSONDecodeError:
                logger.error(f"tool_call arguments JSON解析失败: {tc['arguments']}")
                tc["arguments"] = {}
            tool_calls.append(tc)

        return LLMResponse(
            content="".join(content_chunks),
            tool_calls=tool_calls,
            usage=usage,
        )

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

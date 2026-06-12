"""统一LLM客户端"""

from soul_agent.config.settings import LLMConfig
from soul_agent.llm.providers.local import LocalProvider
from soul_agent.llm.providers.openai import LLMResponse, OpenAIProvider
from soul_agent.utils.logger import logger


class LLMClient:
    def __init__(self, config: LLMConfig):
        self.config = config
        self.provider = self._init_provider(config)

    def _init_provider(self, config: LLMConfig):
        providers = {
            "openai": OpenAIProvider,
            "local": LocalProvider,
        }
        provider_cls = providers.get(config.provider, OpenAIProvider)
        return provider_cls(config)

    async def chat(self, messages, tools=None, stream=False, on_delta=None) -> LLMResponse:
        try:
            return await self.provider.chat(messages, tools=tools, stream=stream, on_delta=on_delta)
        except Exception as e:
            logger.error(f"LLM调用失败: {e}")
            raise

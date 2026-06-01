"""本地模型提供商 (Ollama等)"""

from soul_agent.config.settings import LLMConfig
from soul_agent.llm.providers.openai import OpenAIProvider


class LocalProvider(OpenAIProvider):
    """通过Ollama等本地服务提供LLM能力，使用OpenAI兼容API"""

    def __init__(self, config: LLMConfig):
        if not config.base_url:
            config = config.model_copy(update={"base_url": "http://localhost:11434/v1"})
        super().__init__(config)

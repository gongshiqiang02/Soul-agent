"""自定义异常"""


class SoulAgentError(Exception):
    """基础异常"""
    pass


class ConfigError(SoulAgentError):
    """配置错误"""
    pass


class LLMError(SoulAgentError):
    """LLM调用错误"""
    pass


class ToolError(SoulAgentError):
    """工具执行错误"""
    pass


class MemoryError(SoulAgentError):
    """记忆系统错误"""
    pass

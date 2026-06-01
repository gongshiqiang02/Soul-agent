"""工具注册中心"""
from soul_agent.tools.base import Tool
from soul_agent.utils.logger import logger


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool):
        self._tools[tool.name] = tool
        logger.debug(f"注册工具: {tool.name}")

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    @property
    def schemas(self) -> list[dict]:
        return [tool.to_schema() for tool in self._tools.values()]

    @property
    def names(self) -> list[str]:
        return list(self._tools.keys())

    def get_descriptions(self) -> str:
        lines = []
        for tool in self._tools.values():
            lines.append(f"- {tool.name}: {tool.description}")
        return "\n".join(lines)

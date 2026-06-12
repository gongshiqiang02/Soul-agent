"""工具执行器"""
from soul_agent.tools.base import ToolResult
from soul_agent.tools.registry import ToolRegistry
from soul_agent.utils.logger import logger


class ToolExecutor:
    def __init__(self, registry: ToolRegistry):
        self.registry = registry

    async def execute(self, tool_call: dict) -> dict:
        """Execute a single tool call, return message dict for LLM"""
        name = tool_call["name"]
        arguments = tool_call["arguments"]
        call_id = tool_call.get("id", "")

        tool = self.registry.get(name)
        if not tool:
            result = ToolResult(success=False, output="", error=f"未知工具: {name}")
        else:
            try:
                result = await tool.execute(**arguments)
            except Exception as e:
                logger.error(f"工具执行失败 {name}: {e}")
                result = ToolResult(success=False, output="", error=str(e))

        output = result.output if result.success else f"错误: {result.error}"

        return {
            "role": "tool",
            "tool_call_id": call_id,
            "content": output,
        }

    async def execute_batch(self, tool_calls: list[dict]) -> list[dict]:
        """Execute multiple tool calls"""
        results = []
        for tc in tool_calls:
            result = await self.execute(tc)
            results.append(result)
        return results

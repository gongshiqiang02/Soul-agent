"""任务规划器"""

import json
from soul_agent.utils.logger import logger


PLANNER_PROMPT = """你是一个任务规划专家。分析用户任务，判断是否需要分步执行。

1. 如果任务简单（单轮对话即可完成），设置 "complexity": "simple"，steps 为单步
2. 如果任务需要多步或使用工具，拆解为具体步骤，设置 "complexity": "complex"

每个步骤包含：
- id: 步骤序号
- description: 步骤描述（中文）
- tool: 需要使用的工具名称，不需要则为 null
- depends_on: 依赖的前置步骤 id 列表

输出格式（只输出JSON，不要markdown代码块）：
{"task": "任务概述", "complexity": "simple|complex", "steps": [{"id": 1, "description": "...", "tool": "工具名或null", "depends_on": []}]}"""


class TaskPlanner:
    """将复杂任务拆解为可执行步骤"""

    def __init__(self, llm_client):
        self.llm = llm_client

    async def plan(self, task: str, available_tools: list[str]) -> dict:
        """为任务生成执行计划"""
        tools_str = ", ".join(available_tools)
        messages = [
            {"role": "system", "content": PLANNER_PROMPT},
            {
                "role": "user",
                "content": f"可用工具: {tools_str}\n\n任务: {task}",
            },
        ]

        try:
            response = await self.llm.chat(messages, stream=False)
            content = response.content.strip()
            # 尝试从markdown代码块中提取JSON
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            return json.loads(content)
        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"任务规划解析失败: {e}")
            return {
                "task": task,
                "complexity": "simple",
                "steps": [{"id": 1, "description": task, "tool": None, "depends_on": []}],
            }

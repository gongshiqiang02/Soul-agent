"""任务规划器"""

import json
from soul_agent.utils.logger import logger


PLANNER_PROMPT = """你是一个任务规划专家。请将用户的复杂任务拆解为具体的执行步骤。

每个步骤应该包含：
1. 步骤描述
2. 需要使用的工具（如果有）
3. 依赖的前置步骤

输出JSON格式：
{
  "task": "任务描述",
  "steps": [
    {
      "id": 1,
      "description": "步骤描述",
      "tool": "工具名称或null",
      "depends_on": []
    }
  ]
}

只输出JSON。"""


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
                "steps": [{"id": 1, "description": task, "tool": None, "depends_on": []}],
            }

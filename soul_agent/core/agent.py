"""Agent主循环 - ReAct模式"""

import json
from soul_agent.core.conversation import Conversation
from soul_agent.core.context import ContextManager
from soul_agent.core.planner import TaskPlanner
from soul_agent.llm.prompts import SYSTEM_PROMPT
from soul_agent.utils.logger import logger


class Agent:
    """Agent主循环，协调各模块完成用户任务"""

    def __init__(self, config, llm_client, memory_manager, tool_registry, tool_executor):
        self.config = config
        self.llm = llm_client
        self.memory = memory_manager
        self.tools = tool_registry
        self.executor = tool_executor
        self.conversation = Conversation()
        self.context_mgr = ContextManager(max_tokens=config.llm.max_tokens)
        self.planner = TaskPlanner(llm_client)
        self._on_tool_call = None  # callback for UI
        self._on_stream = None  # callback for streaming

    def set_callbacks(self, on_tool_call=None, on_stream=None):
        """设置UI回调"""
        self._on_tool_call = on_tool_call
        self._on_stream = on_stream

    async def run(self, user_input: str) -> str:
        """处理一次用户输入，返回最终响应"""
        # 1. 检索相关记忆
        relevant_memories = []
        if self.memory:
            try:
                relevant_memories = await self.memory.retrieve(user_input)
            except Exception as e:
                logger.warning(f"记忆检索失败: {e}")

        # 2. 构建系统提示词
        system_prompt = SYSTEM_PROMPT.replace(
            "{tool_descriptions}", self.tools.get_descriptions()
        )

        # 3. 构建消息
        messages = self.conversation.build_messages(
            user_input=user_input,
            system_prompt=system_prompt,
            memories=relevant_memories,
        )

        # 4. Agent循环（ReAct）
        max_iter = self.config.agent.max_iterations
        final_content = ""

        for i in range(max_iter):
            response = await self.llm.chat(
                messages,
                tools=self.tools.schemas if self.tools.schemas else None,
                stream=False,
            )

            if response.has_tool_calls:
                # 通知UI正在执行工具
                if self._on_tool_call:
                    for tc in response.tool_calls:
                        self._on_tool_call(tc["name"], tc["arguments"])

                # 将assistant的tool_calls消息加入
                assistant_msg = {"role": "assistant", "content": response.content or ""}
                assistant_msg["tool_calls"] = [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {
                            "name": tc["name"],
                            "arguments": json.dumps(tc["arguments"], ensure_ascii=False),
                        },
                    }
                    for tc in response.tool_calls
                ]
                messages.append(assistant_msg)

                # 执行工具
                results = await self.executor.execute_batch(response.tool_calls)
                messages.extend(results)
            else:
                final_content = response.content
                break
        else:
            final_content = response.content if response else "达到最大迭代次数，任务未完成。"

        # 5. 更新记忆
        if self.memory:
            try:
                await self.memory.process_turn(user_input, final_content)
            except Exception as e:
                logger.warning(f"记忆更新失败: {e}")

        # 6. 更新对话历史
        self.conversation.add_turn(user_input, final_content)

        return final_content

    def reset(self):
        """重置对话"""
        self.conversation.clear()

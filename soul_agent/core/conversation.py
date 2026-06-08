"""对话管理"""

import json
import uuid
import asyncio


class Conversation:
    """管理对话历史和消息构建"""

    def __init__(self):
        self.messages: list[dict] = []
        self.conversation_id: str = str(uuid.uuid4())
        self._on_persist_message = None  # async callable(cid, role, content, tool_calls)

    def build_messages(
        self,
        user_input: str,
        system_prompt: str,
        memories: list | None = None,
        plan_context: str = "",
    ) -> list[dict]:
        """构建发送给LLM的完整消息列表"""
        messages = []

        # 系统提示词
        memory_context = ""
        if memories:
            memory_lines = []
            for m in memories:
                memory_lines.append(f"- [{m.memory_type}] {m.content}")
            memory_context = "已知的用户信息：\n" + "\n".join(memory_lines)

        formatted_prompt = system_prompt.format(
            memory_context=memory_context or "暂无历史记忆",
            plan_context=plan_context or "",
            tool_descriptions="{tool_descriptions}",
        )
        messages.append({"role": "system", "content": formatted_prompt})

        # 历史消息
        messages.extend(self.messages)

        # 当前用户输入
        messages.append({"role": "user", "content": user_input})

        return messages

    def add_turn(self, user_input: str, assistant_reply: str):
        """添加一轮对话"""
        self.messages.append({"role": "user", "content": user_input})
        self.messages.append({"role": "assistant", "content": assistant_reply})

        # 持久化本轮消息
        self._schedule_persist("user", user_input)
        self._schedule_persist("assistant", assistant_reply)

        # 保留最近的对话（防止上下文过长）
        max_turns = 20
        max_messages = max_turns * 2
        if len(self.messages) > max_messages:
            self.messages = self.messages[-max_messages:]

    def add_message(self, message: dict):
        """添加任意消息（如工具调用结果）"""
        self.messages.append(message)
        # 持久化工具消息
        tc_str = json.dumps(message.get("tool_calls")) if message.get("tool_calls") else None
        self._schedule_persist(
            message.get("role", "tool"), message.get("content", ""), tc_str
        )

    def clear(self):
        self.messages.clear()

    def set_persist_callback(self, callback):
        """设置消息持久化回调。callback 签名为 async def(cid, role, content, tool_calls)"""
        self._on_persist_message = callback

    def _schedule_persist(self, role: str, content: str, tool_calls: str | None = None):
        """调度异步持久化任务（fire-and-forget）"""
        if not self._on_persist_message:
            return
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(
                    self._on_persist_message(self.conversation_id, role, content, tool_calls)
                )
        except RuntimeError:
            pass

"""对话管理"""

from dataclasses import dataclass, field


class Conversation:
    """管理对话历史和消息构建"""

    def __init__(self):
        self.messages: list[dict] = []
        self.conversation_id: str = ""

    def build_messages(
        self,
        user_input: str,
        system_prompt: str,
        memories: list | None = None,
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

        # 保留最近的对话（防止上下文过长）
        max_turns = 20
        max_messages = max_turns * 2
        if len(self.messages) > max_messages:
            self.messages = self.messages[-max_messages:]

    def add_message(self, message: dict):
        """添加任意消息（如工具调用结果）"""
        self.messages.append(message)

    def clear(self):
        self.messages.clear()

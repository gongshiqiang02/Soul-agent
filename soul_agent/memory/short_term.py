"""短期记忆 - 会话内对话历史"""
from dataclasses import dataclass, field


@dataclass
class ShortTermMemory:
    """管理当前会话的对话历史"""
    messages: list[dict] = field(default_factory=list)
    max_messages: int = 50

    def add(self, role: str, content: str):
        self.messages.append({"role": role, "content": content})
        # Trim if exceeds max
        if len(self.messages) > self.max_messages:
            # Keep system message + recent messages
            self.messages = self.messages[:1] + self.messages[-(self.max_messages-1):]

    def get_messages(self) -> list[dict]:
        return list(self.messages)

    def clear(self):
        self.messages.clear()

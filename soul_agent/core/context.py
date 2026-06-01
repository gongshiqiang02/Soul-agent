"""上下文窗口管理"""


class ContextManager:
    """管理上下文窗口，确保不超过模型限制"""

    def __init__(self, max_tokens: int = 4096):
        self.max_tokens = max_tokens

    def estimate_tokens(self, text: str) -> int:
        """粗略估算token数（中文约1.5字/token，英文约4字符/token）"""
        chinese_chars = sum(1 for c in text if '一' <= c <= '鿿')
        other_chars = len(text) - chinese_chars
        return int(chinese_chars * 1.5 + other_chars / 4)

    def trim_messages(self, messages: list[dict], max_tokens: int | None = None) -> list[dict]:
        """裁剪消息列表以适应上下文窗口"""
        limit = max_tokens or self.max_tokens
        if not messages:
            return messages

        # 始终保留系统消息和最后的用户消息
        system_msgs = [m for m in messages if m["role"] == "system"]
        last_user = messages[-1] if messages[-1]["role"] == "user" else None
        middle = [m for m in messages if m["role"] != "system"]
        if last_user and middle and middle[-1] is last_user:
            middle = middle[:-1]

        total_tokens = sum(self.estimate_tokens(m.get("content", "")) for m in system_msgs)
        if last_user:
            total_tokens += self.estimate_tokens(last_user.get("content", ""))

        # 从最新的消息开始保留
        kept = []
        for msg in reversed(middle):
            msg_tokens = self.estimate_tokens(msg.get("content", ""))
            if total_tokens + msg_tokens > limit:
                break
            kept.insert(0, msg)
            total_tokens += msg_tokens

        result = system_msgs + kept
        if last_user:
            result.append(last_user)
        return result

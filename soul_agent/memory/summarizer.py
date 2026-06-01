"""对话摘要器 - 使用LLM生成对话摘要"""
from soul_agent.utils.logger import logger

SUMMARIZE_PROMPT = """请对以下对话内容生成一个简洁的摘要，包含关键信息和结论。
用中文回答，控制在200字以内。

对话内容：
{conversation}

摘要："""


class ConversationSummarizer:
    """使用LLM生成对话摘要"""

    def __init__(self, llm_client=None):
        self._llm_client = llm_client

    async def summarize(self, messages: list[dict]) -> str:
        """Summarize a list of messages into a concise text.

        Args:
            messages: List of {"role": ..., "content": ...} dicts.

        Returns:
            A summary string. Falls back to simple truncation if LLM is unavailable.
        """
        if not messages:
            return ""

        conversation_text = self._format_messages(messages)

        if self._llm_client is None:
            logger.warning("No LLM client available for summarization, using simple extraction")
            return self._simple_summary(messages)

        try:
            response = await self._llm_client.chat(
                messages=[
                    {"role": "user", "content": SUMMARIZE_PROMPT.format(conversation=conversation_text)}
                ],
                stream=False,
            )
            return response.content.strip()
        except Exception as e:
            logger.warning(f"LLM summarization failed: {e}, using simple extraction")
            return self._simple_summary(messages)

    @staticmethod
    def _format_messages(messages: list[dict]) -> str:
        lines = []
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            if role == "system":
                continue
            label = "用户" if role == "user" else "助手"
            lines.append(f"{label}: {content}")
        return "\n".join(lines)

    @staticmethod
    def _simple_summary(messages: list[dict]) -> str:
        """Fallback: extract key points without LLM."""
        user_messages = [m["content"] for m in messages if m.get("role") == "user" and m.get("content")]
        if not user_messages:
            return "（空对话）"

        topics = user_messages[:5]  # Take first 5 user messages as topic indicators
        summary = "对话主题: " + "; ".join(
            msg[:50] + ("..." if len(msg) > 50 else "") for msg in topics
        )
        return summary

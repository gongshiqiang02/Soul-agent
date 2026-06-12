"""记忆管理器 - 统一入口"""
import json

from soul_agent.config.settings import MemoryConfig
from soul_agent.utils.logger import logger
from soul_agent.memory.short_term import ShortTermMemory
from soul_agent.memory.long_term import LongTermMemory, MemoryEntry
from soul_agent.memory.retriever import MemoryRetriever
from soul_agent.memory.summarizer import ConversationSummarizer

EXTRACT_MEMORIES_PROMPT = """分析以下对话，提取需要长期记住的信息。

提取规则：
1. 用户的个人信息（姓名、职业、偏好等）→ type: fact
2. 用户表达的偏好（喜欢/不喜欢）→ type: preference
3. 重要事件或决定 → type: event
4. 不提取临时性、无长期价值的信息

## 过滤条件（以下内容返回空数组 []，不要记忆）
- 助手的操作过程、工具调用结果、代码片段、文件路径、命令输出
- 通用知识问答内容（如"什么是Python"的回答）
- 临时性任务信息（如"帮我读一下这个文件"的结果）
- 对话的元信息（寒暄、客套）

判断标准：这条信息能否帮助你在未来的对话中更好地理解或服务该用户？

用户: {user_input}
助手: {assistant_reply}

输出格式（纯JSON数组，不要markdown）:
[{{"content": "...", "memory_type": "fact", "importance": 0.7}}]

如果没有值得记忆的信息，返回空数组 []。"""


class MemoryManager:
    """统一管理短期、长期记忆和检索"""

    def __init__(self, config: MemoryConfig, llm_client=None):
        self.config = config
        self._llm_client = llm_client
        self.short_term = ShortTermMemory()
        self.long_term = LongTermMemory(db_path=config.db_path)
        self.retriever = MemoryRetriever(
            long_term=self.long_term,
            vector_db_path=config.vector_db_path if config.enabled else None,
        )
        self.summarizer = ConversationSummarizer(llm_client=llm_client)

    async def initialize(self):
        """Initialize database tables."""
        await self.long_term.initialize()
        logger.info("Memory system initialized")

    async def retrieve(self, query: str, top_k: int = 5) -> list[MemoryEntry]:
        """Retrieve relevant memories for a query."""
        if not self.config.enabled:
            return []
        top_k = min(top_k, self.config.max_memories_per_query)
        return await self.retriever.retrieve(query, top_k=top_k)

    async def process_turn(self, user_input: str, assistant_reply: str):
        """Process a conversation turn: add to short-term and optionally extract long-term memories."""
        self.short_term.add("user", user_input)
        self.short_term.add("assistant", assistant_reply)

        if not self.config.enabled or self._llm_client is None:
            return

        try:
            response = await self._llm_client.chat(
                messages=[
                    {"role": "user", "content": EXTRACT_MEMORIES_PROMPT.format(
                        user_input=user_input, assistant_reply=assistant_reply
                    )}
                ],
                stream=False,
            )
            raw = response.content.strip()

            # Strip markdown code fences if present
            if raw.startswith("```"):
                lines = raw.split("\n")
                raw = "\n".join(lines[1:-1]) if len(lines) > 2 else "[]"

            memories = json.loads(raw)
            if not isinstance(memories, list):
                return

            for mem in memories:
                importance = float(mem.get("importance", 0.5))
                if importance < self.config.importance_threshold:
                    continue
                await self.store(
                    content=mem["content"],
                    memory_type=mem.get("memory_type", "fact"),
                    importance=importance,
                )
        except (json.JSONDecodeError, KeyError) as e:
            logger.debug(f"Memory extraction parse error: {e}")
        except Exception as e:
            logger.warning(f"Memory extraction failed: {e}")

    async def store(self, content: str, memory_type: str, importance: float = 0.5,
                    metadata: dict | None = None) -> str:
        """存储记忆，含去重（精确哈希 + 向量相似度）。"""
        # 向量相似度近似去重
        is_dup, existing_id = self.retriever.check_duplicate(content)
        if is_dup and existing_id:
            logger.debug(f"检测到近似重复，跳过: {content[:50]}...")
            return existing_id

        # 存储（LongTermMemory.store 内部处理精确哈希去重）
        memory_id = await self.long_term.store(
            content=content,
            memory_type=memory_type,
            importance=importance,
            metadata=metadata,
        )
        # 同时写入向量数据库
        await self.retriever.add_embedding(
            memory_id, content, metadata={"memory_type": memory_type}
        )
        logger.debug(f"已存储记忆 {memory_id}: {content[:50]}...")
        return memory_id

    async def forget(self, memory_id: str):
        """Delete a memory from both stores."""
        await self.long_term.delete(memory_id)
        await self.retriever.delete_embedding(memory_id)
        logger.debug(f"Deleted memory {memory_id}")

    async def list_all(self, memory_type: str | None = None) -> list[MemoryEntry]:
        """List all memories, optionally filtered by type."""
        return await self.long_term.get_all(memory_type=memory_type)

    async def summarize_conversation(self) -> str:
        """Summarize the current short-term conversation."""
        messages = self.short_term.get_messages()
        return await self.summarizer.summarize(messages)

    # ── Conversation persistence bridge ─────────────────────────────

    async def create_conversation(self, title: str = "") -> str:
        """Create a new persisted conversation."""
        return await self.long_term.create_conversation(title)

    async def create_conversation_with_id(self, conversation_id: str,
                                          title: str = ""):
        """Create a conversation with a pre-generated ID."""
        return await self.long_term.create_conversation_with_id(
            conversation_id, title
        )

    async def save_conversation_turn(self, conversation_id: str,
                                     user_input: str, assistant_reply: str):
        """Persist a user-assistant message pair."""
        await self.long_term.save_message(conversation_id, "user", user_input)
        await self.long_term.save_message(conversation_id, "assistant", assistant_reply)

    async def list_conversations(self, limit: int = 50):
        """List recent conversations."""
        return await self.long_term.list_conversations(limit)

    async def get_conversation_messages(self, conversation_id: str) -> list[dict]:
        """Load all messages from a conversation."""
        return await self.long_term.get_conversation_messages(conversation_id)

    async def update_conversation_title(self, conversation_id: str, title: str):
        """Rename a conversation."""
        await self.long_term.update_conversation_title(conversation_id, title)

"""记忆管理器 - 统一入口"""
import json

from soul_agent.config.settings import MemoryConfig
from soul_agent.utils.logger import logger
from soul_agent.memory.short_term import ShortTermMemory
from soul_agent.memory.long_term import LongTermMemory, MemoryEntry
from soul_agent.memory.retriever import MemoryRetriever
from soul_agent.memory.summarizer import ConversationSummarizer

EXTRACT_MEMORIES_PROMPT = """分析以下对话，提取需要长期记住的信息。
每条记忆用JSON格式输出，包含 content, memory_type(fact/preference/event), importance(0-1)。
如果没有需要记住的信息，返回空数组 []。

用户: {user_input}
助手: {assistant_reply}

输出格式（纯JSON数组，不要markdown）:
[{{"content": "...", "memory_type": "fact", "importance": 0.7}}]"""


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
        """Store a memory in both SQLite and ChromaDB."""
        memory_id = await self.long_term.store(
            content=content,
            memory_type=memory_type,
            importance=importance,
            metadata=metadata,
        )
        # Also index in vector DB
        self.retriever.add_embedding(memory_id, content, metadata={"memory_type": memory_type})
        logger.debug(f"Stored memory {memory_id}: {content[:50]}...")
        return memory_id

    async def forget(self, memory_id: str):
        """Delete a memory from both stores."""
        await self.long_term.delete(memory_id)
        self.retriever.delete_embedding(memory_id)
        logger.debug(f"Deleted memory {memory_id}")

    async def list_all(self, memory_type: str | None = None) -> list[MemoryEntry]:
        """List all memories, optionally filtered by type."""
        return await self.long_term.get_all(memory_type=memory_type)

    async def summarize_conversation(self) -> str:
        """Summarize the current short-term conversation."""
        messages = self.short_term.get_messages()
        return await self.summarizer.summarize(messages)

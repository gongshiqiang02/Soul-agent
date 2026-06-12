"""记忆系统测试"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock

from soul_agent.memory.short_term import ShortTermMemory
from soul_agent.memory.long_term import LongTermMemory
from soul_agent.memory.manager import MemoryManager


class TestShortTermMemory:
    def test_add_message(self):
        stm = ShortTermMemory()
        stm.add("user", "你好")
        assert len(stm.messages) == 1
        assert stm.messages[0]["role"] == "user"

    def test_get_messages(self):
        stm = ShortTermMemory()
        stm.add("user", "问题")
        stm.add("assistant", "回答")
        msgs = stm.get_messages()
        assert len(msgs) == 2

    def test_max_messages_trim(self):
        stm = ShortTermMemory(max_messages=5)
        for i in range(10):
            stm.add("user", f"消息{i}")
        assert len(stm.messages) <= 5

    def test_clear(self):
        stm = ShortTermMemory()
        stm.add("user", "test")
        stm.clear()
        assert len(stm.messages) == 0


class TestLongTermMemory:
    @pytest.fixture
    def db_path(self, tmp_path):
        return str(tmp_path / "test_memory.db")

    @pytest.mark.asyncio
    async def test_initialize(self, db_path):
        ltm = LongTermMemory(db_path)
        await ltm.initialize()
        assert Path(db_path).exists()

    @pytest.mark.asyncio
    async def test_store_and_get_all(self, db_path):
        ltm = LongTermMemory(db_path)
        await ltm.initialize()

        await ltm.store("用户是程序员", "fact", importance=0.8)
        await ltm.store("喜欢Python", "preference", importance=0.7)

        all_memories = await ltm.get_all()
        assert len(all_memories) == 2

    @pytest.mark.asyncio
    async def test_store_and_get_by_type(self, db_path):
        ltm = LongTermMemory(db_path)
        await ltm.initialize()

        await ltm.store("用户是程序员", "fact", importance=0.8)
        await ltm.store("喜欢Python", "preference", importance=0.7)

        facts = await ltm.get_all(memory_type="fact")
        assert len(facts) == 1
        assert facts[0].content == "用户是程序员"

    @pytest.mark.asyncio
    async def test_search_by_keyword(self, db_path):
        ltm = LongTermMemory(db_path)
        await ltm.initialize()

        await ltm.store("用户是Python程序员", "fact")
        await ltm.store("喜欢喝咖啡", "preference")

        results = await ltm.search_by_keyword("Python")
        assert len(results) == 1
        assert "Python" in results[0].content

    @pytest.mark.asyncio
    async def test_delete(self, db_path):
        ltm = LongTermMemory(db_path)
        await ltm.initialize()

        memory_id = await ltm.store("临时记忆", "fact")
        all_before = await ltm.get_all()
        assert len(all_before) == 1

        await ltm.delete(memory_id)
        all_after = await ltm.get_all()
        assert len(all_after) == 0

    @pytest.mark.asyncio
    async def test_update_access(self, db_path):
        ltm = LongTermMemory(db_path)
        await ltm.initialize()

        memory_id = await ltm.store("测试记忆", "fact")
        await ltm.update_access(memory_id)

        memories = await ltm.get_all()
        assert memories[0].access_count == 1


class TestMemoryManager:
    @pytest.fixture
    def mock_config(self, tmp_path):
        config = MagicMock()
        config.db_path = str(tmp_path / "test.db")
        config.vector_db_path = str(tmp_path / "chroma")
        config.max_memories_per_query = 5
        config.importance_threshold = 0.3
        config.embedding_model = "text-embedding-3-small"
        config.enabled = True
        return config

    @pytest.mark.asyncio
    async def test_initialize(self, mock_config):
        mm = MemoryManager(mock_config)
        await mm.initialize()

    @pytest.mark.asyncio
    async def test_store_and_list(self, mock_config):
        mm = MemoryManager(mock_config)
        await mm.initialize()

        await mm.store("测试记忆", "fact", 0.8)
        memories = await mm.list_all()
        assert len(memories) == 1
        assert memories[0].content == "测试记忆"

    @pytest.mark.asyncio
    async def test_forget(self, mock_config):
        mm = MemoryManager(mock_config)
        await mm.initialize()

        await mm.store("要忘记的", "fact", 0.5)
        memories = await mm.list_all()
        assert len(memories) == 1

        await mm.forget(memories[0].id)
        memories_after = await mm.list_all()
        assert len(memories_after) == 0

    @pytest.mark.asyncio
    async def test_retrieve(self, mock_config):
        mm = MemoryManager(mock_config)
        await mm.initialize()

        await mm.store("用户喜欢Python编程", "preference", 0.8)
        await mm.store("用户住在北京", "fact", 0.7)

        results = await mm.retrieve("Python")
        assert len(results) >= 1

"""记忆系统测试"""

import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from soul_agent.memory.short_term import ShortTermMemory
from soul_agent.memory.long_term import LongTermMemory, MemoryEntry
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


def test_extraction_prompt_has_relevance_rules():
    """提取提示词必须包含明确的过滤规则。"""
    from soul_agent.memory.manager import EXTRACT_MEMORIES_PROMPT
    # 必须包含负面过滤条件
    assert "过滤条件" in EXTRACT_MEMORIES_PROMPT or "不提取" in EXTRACT_MEMORIES_PROMPT
    # 必须过滤掉工具/代码/命令输出
    assert "工具" in EXTRACT_MEMORIES_PROMPT
    assert "代码" in EXTRACT_MEMORIES_PROMPT
    # 必须包含判断标准
    assert "判断标准" in EXTRACT_MEMORIES_PROMPT


@pytest.mark.asyncio
async def test_store_duplicate_content_rejected(tmp_path):
    """相同内容存储两次不应产生两条记录。"""
    from soul_agent.memory.long_term import LongTermMemory

    db = LongTermMemory(db_path=str(tmp_path / "test.db"))
    await db.initialize()

    id1 = await db.store("用户喜欢Python", "preference", 0.8)
    await db.store("用户喜欢Python", "preference", 0.8)

    all_mems = await db.get_all()
    assert len(all_mems) == 1, f"预期 1 条记忆，实际 {len(all_mems)} 条: {[m.content for m in all_mems]}"
    assert all_mems[0].id == id1  # 返回已有记录的 ID


@pytest.mark.asyncio
async def test_store_near_duplicate_detected(tmp_path):
    """语义相似的内容不应重复存储（需要 ChromaDB）。"""
    pytest.importorskip("chromadb")

    from soul_agent.memory.long_term import LongTermMemory
    from soul_agent.memory.retriever import MemoryRetriever

    db = LongTermMemory(db_path=str(tmp_path / "test.db"))
    await db.initialize()
    retriever = MemoryRetriever(long_term=db, vector_db_path=str(tmp_path / "chroma"))

    # 存储原始记忆
    id1 = await db.store("用户喜欢Python编程", "preference", 0.8)
    retriever.add_embedding(id1, "用户喜欢Python编程", metadata={"memory_type": "preference"})

    # 检查近似重复
    is_dup, existing_id = retriever.check_duplicate("用户喜欢用Python写代码", threshold=0.75)
    assert is_dup is True
    assert existing_id == id1


def test_default_importance_threshold_is_05():
    """默认重要性阈值应为 0.5，过滤低价值记忆。"""
    from soul_agent.config.defaults import DEFAULT_CONFIG
    assert DEFAULT_CONFIG["memory"]["importance_threshold"] == 0.5


@pytest.mark.asyncio
async def test_cleanup_duplicates(tmp_path):
    """cleanup_duplicates 应删除重复记录，保留重要性最高的。"""
    from soul_agent.memory.long_term import LongTermMemory
    import aiosqlite
    import hashlib
    import uuid
    from datetime import datetime

    db = LongTermMemory(db_path=str(tmp_path / "test.db"))
    await db.initialize()

    content = "用户喜欢Python"
    content_hash = hashlib.sha256(content.strip().lower().encode("utf-8")).hexdigest()

    id_low = str(uuid.uuid4())
    id_high = str(uuid.uuid4())
    async with aiosqlite.connect(db.db_path) as conn:
        now = datetime.now().isoformat()
        # 临时删除 UNIQUE 紦束，以便插入重复哈希数据模拟历史脏数据
        await conn.execute("DROP INDEX IF EXISTS idx_memories_content_hash")
        await conn.execute(
            "INSERT INTO memories (id, content, memory_type, importance, created_at, last_accessed, access_count, metadata, content_hash) VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?)",
            (id_low, content, "preference", 0.6, now, now, "{}", content_hash),
        )
        await conn.execute(
            "INSERT INTO memories (id, content, memory_type, importance, created_at, last_accessed, access_count, metadata, content_hash) VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?)",
            (id_high, content, "preference", 0.9, now, now, "{}", content_hash),
        )
        await conn.commit()

    removed = await db.cleanup_duplicates()
    assert removed == 1

    remaining = await db.get_all()
    assert len(remaining) == 1
    assert remaining[0].importance == 0.9  # 保留了重要性更高的那条


@pytest.mark.asyncio
async def test_process_turn_respects_relevance_and_dedup(tmp_path):
    """端到端测试：process_turn 不应存储无关或重复记忆。"""
    from soul_agent.memory.manager import MemoryManager
    from soul_agent.config.settings import MemoryConfig

    config = MemoryConfig(
        enabled=True,
        db_path=str(tmp_path / "test.db"),
        vector_db_path=str(tmp_path / "chroma"),
        importance_threshold=0.5,
    )

    # Mock LLM：第一次返回空（无关内容），第二次返回有效记忆，第三次返回相同记忆
    call_count = 0
    async def mock_chat(messages, stream=False):
        nonlocal call_count
        call_count += 1
        mock_resp = MagicMock()
        if call_count == 1:
            # 无关内容的对话 → LLM 判定无需记忆
            mock_resp.content = "[]"
        elif call_count == 2:
            # 用户表达了偏好 → LLM 提取记忆
            mock_resp.content = '[{"content": "用户喜欢Python", "memory_type": "preference", "importance": 0.8}]'
        else:
            # 用户再次表达相似偏好 → LLM 可能提取相同内容，去重应拦截
            mock_resp.content = '[{"content": "用户喜欢Python", "memory_type": "preference", "importance": 0.8}]'
        return mock_resp

    mock_llm = MagicMock()
    mock_llm.chat = AsyncMock(side_effect=mock_chat)

    manager = MemoryManager(config=config, llm_client=mock_llm)
    await manager.initialize()

    # 第一轮：无关内容 → 不存储
    await manager.process_turn("帮我读一下config.yaml", "文件内容如下：key: value")
    mems = await manager.list_all()
    assert len(mems) == 0, "不应存储无关记忆"

    # 第二轮：相关内容 → 存储
    await manager.process_turn("我喜欢用Python写代码", "好的，我记住了")
    mems = await manager.list_all()
    assert len(mems) == 1
    assert mems[0].content == "用户喜欢Python"

    # 第三轮：内容哈希相同 → 去重拦截，不新增记录
    await manager.process_turn("我真的很喜欢Python", "Python确实是很好的语言")
    mems = await manager.list_all()
    assert len(mems) == 1, f"去重失败：预期 1 条，实际 {len(mems)} 条"

"""对话持久化测试"""
import asyncio

import pytest

from soul_agent.memory.long_term import LongTermMemory


class TestConversationPersistence:
    @pytest.fixture
    def db_path(self, tmp_path):
        return str(tmp_path / "test_conv.db")

    @pytest.mark.asyncio
    async def test_create_conversation(self, db_path):
        ltm = LongTermMemory(db_path)
        await ltm.initialize()
        conv_id = await ltm.create_conversation()
        assert conv_id
        assert len(conv_id) == 36  # UUID4

    @pytest.mark.asyncio
    async def test_create_conversation_with_title(self, db_path):
        ltm = LongTermMemory(db_path)
        await ltm.initialize()
        await ltm.create_conversation(title="测试会话")
        conversations = await ltm.list_conversations()
        assert conversations[0].title == "测试会话"

    @pytest.mark.asyncio
    async def test_save_and_retrieve_messages(self, db_path):
        ltm = LongTermMemory(db_path)
        await ltm.initialize()
        conv_id = await ltm.create_conversation(title="对话测试")

        await ltm.save_message(conv_id, "user", "你好")
        await ltm.save_message(conv_id, "assistant", "你好！有什么可以帮你的？")

        messages = await ltm.get_conversation_messages(conv_id)
        assert len(messages) == 2
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "你好"
        assert messages[1]["role"] == "assistant"

    @pytest.mark.asyncio
    async def test_list_conversations_ordered_by_update(self, db_path):
        ltm = LongTermMemory(db_path)
        await ltm.initialize()

        await ltm.create_conversation(title="旧会话")
        await asyncio.sleep(0.01)  # Ensure different timestamps
        c2 = await ltm.create_conversation(title="新会话")
        await ltm.save_message(c2, "user", "hello")  # updates c2's updated_at

        conversations = await ltm.list_conversations()
        assert conversations[0].title == "新会话"  # 最新更新的在前
        assert conversations[1].title == "旧会话"

    @pytest.mark.asyncio
    async def test_message_count(self, db_path):
        ltm = LongTermMemory(db_path)
        await ltm.initialize()

        conv_id = await ltm.create_conversation(title="计数测试")
        await ltm.save_message(conv_id, "user", "消息1")
        await ltm.save_message(conv_id, "assistant", "回复1")
        await ltm.save_message(conv_id, "user", "消息2")

        conversations = await ltm.list_conversations()
        assert conversations[0].message_count == 3

    @pytest.mark.asyncio
    async def test_rename_conversation(self, db_path):
        ltm = LongTermMemory(db_path)
        await ltm.initialize()

        conv_id = await ltm.create_conversation(title="原名")
        await ltm.update_conversation_title(conv_id, "新名字")

        conversations = await ltm.list_conversations()
        assert conversations[0].title == "新名字"

    @pytest.mark.asyncio
    async def test_create_conversation_with_id(self, db_path):
        ltm = LongTermMemory(db_path)
        await ltm.initialize()

        conv_id = "my-custom-uuid-123456789012"
        result = await ltm.create_conversation_with_id(conv_id, title="指定ID")
        assert result == conv_id

        messages = await ltm.get_conversation_messages(conv_id)
        assert messages == []

    @pytest.mark.asyncio
    async def test_empty_conversation_no_messages(self, db_path):
        ltm = LongTermMemory(db_path)
        await ltm.initialize()

        conv_id = await ltm.create_conversation()
        messages = await ltm.get_conversation_messages(conv_id)
        assert messages == []

    @pytest.mark.asyncio
    async def test_no_conversations(self, db_path):
        ltm = LongTermMemory(db_path)
        await ltm.initialize()

        conversations = await ltm.list_conversations()
        assert conversations == []

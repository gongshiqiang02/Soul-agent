"""Agent核心测试"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from soul_agent.core.agent import Agent
from soul_agent.core.conversation import Conversation
from soul_agent.core.context import ContextManager
from soul_agent.core.planner import TaskPlanner


class TestConversation:
    def test_build_messages(self):
        conv = Conversation()
        messages = conv.build_messages(
            user_input="你好",
            system_prompt="你是助手。\n{memory_context}\n{tool_descriptions}",
        )
        assert len(messages) == 2  # system + user
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "你好"

    def test_add_turn(self):
        conv = Conversation()
        conv.add_turn("你好", "你好！有什么可以帮你的？")
        assert len(conv.messages) == 2
        assert conv.messages[0]["role"] == "user"
        assert conv.messages[1]["role"] == "assistant"

    def test_build_messages_with_history(self):
        conv = Conversation()
        conv.add_turn("问题1", "回答1")
        messages = conv.build_messages(
            user_input="问题2",
            system_prompt="系统提示\n{memory_context}\n{tool_descriptions}",
        )
        # system + 2 history + user
        assert len(messages) == 4
        assert messages[-1]["content"] == "问题2"

    def test_build_messages_with_memories(self):
        conv = Conversation()
        mock_memory = MagicMock()
        mock_memory.memory_type = "fact"
        mock_memory.content = "用户是程序员"

        messages = conv.build_messages(
            user_input="你好",
            system_prompt="你是助手。\n{memory_context}\n{tool_descriptions}",
            memories=[mock_memory],
        )
        assert "用户是程序员" in messages[0]["content"]

    def test_clear(self):
        conv = Conversation()
        conv.add_turn("a", "b")
        conv.clear()
        assert len(conv.messages) == 0

    def test_max_turns_trimming(self):
        conv = Conversation()
        for i in range(30):
            conv.add_turn(f"q{i}", f"a{i}")
        # 20 turns * 2 = 40 messages max
        assert len(conv.messages) <= 40


class TestContextManager:
    def test_estimate_tokens_english(self):
        ctx = ContextManager()
        tokens = ctx.estimate_tokens("hello world")
        assert tokens > 0

    def test_estimate_tokens_chinese(self):
        ctx = ContextManager()
        tokens = ctx.estimate_tokens("你好世界")
        assert tokens > 0

    def test_trim_messages_preserves_system(self):
        ctx = ContextManager(max_tokens=100)
        messages = [
            {"role": "system", "content": "系统"},
            {"role": "user", "content": "问题1"},
            {"role": "assistant", "content": "回答1"},
            {"role": "user", "content": "问题2"},
        ]
        trimmed = ctx.trim_messages(messages)
        assert trimmed[0]["role"] == "system"
        assert trimmed[-1]["role"] == "user"


class TestAgent:
    @pytest.fixture
    def mock_config(self):
        config = MagicMock()
        config.llm.max_tokens = 4096
        config.agent.max_iterations = 3
        return config

    @pytest.fixture
    def mock_llm(self):
        llm = AsyncMock()
        response = MagicMock()
        response.content = "这是回复"
        response.has_tool_calls = False
        response.tool_calls = []
        llm.chat.return_value = response
        return llm

    @pytest.fixture
    def mock_memory(self):
        memory = AsyncMock()
        memory.retrieve.return_value = []
        return memory

    @pytest.fixture
    def mock_registry(self):
        registry = MagicMock()
        registry.schemas = []
        registry.get_descriptions.return_value = ""
        return registry

    @pytest.fixture
    def mock_executor(self):
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_agent_basic_chat(self, mock_config, mock_llm, mock_memory, mock_registry, mock_executor):
        agent = Agent(mock_config, mock_llm, mock_memory, mock_registry, mock_executor)
        result = await agent.run("你好")
        assert result == "这是回复"
        mock_llm.chat.assert_called_once()

    @pytest.mark.asyncio
    async def test_agent_with_tool_call(self, mock_config, mock_llm, mock_memory, mock_registry, mock_executor):
        # First call returns tool call, second call returns text
        tool_response = MagicMock()
        tool_response.content = ""
        tool_response.has_tool_calls = True
        tool_response.tool_calls = [
            {"id": "call_1", "name": "read_file", "arguments": {"path": "test.txt"}}
        ]

        text_response = MagicMock()
        text_response.content = "文件内容是..."
        text_response.has_tool_calls = False

        mock_llm.chat.side_effect = [tool_response, text_response]
        mock_executor.execute_batch.return_value = [
            {"role": "tool", "tool_call_id": "call_1", "content": "file content"}
        ]

        agent = Agent(mock_config, mock_llm, mock_memory, mock_registry, mock_executor)
        result = await agent.run("读取test.txt")
        assert result == "文件内容是..."
        assert mock_llm.chat.call_count == 2

    @pytest.mark.asyncio
    async def test_agent_reset(self, mock_config, mock_llm, mock_memory, mock_registry, mock_executor):
        agent = Agent(mock_config, mock_llm, mock_memory, mock_registry, mock_executor)
        await agent.run("你好")
        agent.reset()
        assert len(agent.conversation.messages) == 0

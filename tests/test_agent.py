"""Agent核心测试"""

import json
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
        config.agent.planning_enabled = False  # disable planner for basic tests
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


def _make_minimal_agent():
    """Create a minimal Agent for unit tests (no async deps)."""
    config = MagicMock()
    config.llm.max_tokens = 4096
    config.agent.max_iterations = 3
    config.agent.planning_enabled = True
    config.agent.planning_complexity_threshold = 2
    llm = AsyncMock()
    return Agent(config, llm, None, MagicMock(), AsyncMock())


class TestComplexityEstimation:
    """Test heuristic complexity scoring."""

    def test_simple_greeting_is_low_complexity(self):
        agent = _make_minimal_agent()
        score = agent._estimate_complexity("你好")
        assert score < 2

    def test_simple_ack_is_low_complexity(self):
        agent = _make_minimal_agent()
        score = agent._estimate_complexity("好的")
        assert score < 2

    def test_short_question_is_low_complexity(self):
        agent = _make_minimal_agent()
        score = agent._estimate_complexity("今天天气怎么样")
        assert score < 2

    def test_tool_mention_raises_complexity(self):
        agent = _make_minimal_agent()
        score = agent._estimate_complexity("帮我读取一下 config.yaml 文件")
        assert score >= 2  # includes "读取" and "文件"

    def test_multi_step_is_high_complexity(self):
        agent = _make_minimal_agent()
        score = agent._estimate_complexity(
            "查找所有 Python 文件，然后统计每个文件的行数，最后把结果写入 report.txt"
        )
        assert score >= 3

    def test_very_long_input_is_high_complexity(self):
        agent = _make_minimal_agent()
        long_msg = "请帮我详细分析一下这个项目的架构" + "，并给出改进建议" * 20
        score = agent._estimate_complexity(long_msg)
        assert score >= 3

    def test_threshold_config_is_respected(self):
        agent = _make_minimal_agent()
        agent.config.agent.planning_complexity_threshold = 5
        score = agent._estimate_complexity("读取 config.yaml")
        assert score < 5


class TestPlanContextFormatting:
    """Test plan-to-context-text formatting."""

    def test_simple_plan_no_tool_returns_empty(self):
        agent = _make_minimal_agent()
        plan = {
            "task": "打招呼", "complexity": "simple",
            "steps": [{"id": 1, "description": "回应", "tool": None, "depends_on": []}],
        }
        assert agent._format_plan_context(plan) == ""

    def test_single_step_with_tool_returns_context(self):
        agent = _make_minimal_agent()
        plan = {
            "task": "读取配置", "complexity": "simple",
            "steps": [{"id": 1, "description": "读取", "tool": "read_file", "depends_on": []}],
        }
        result = agent._format_plan_context(plan)
        assert "read_file" in result
        assert "执行计划" in result

    def test_multi_step_plan_returns_full_context(self):
        agent = _make_minimal_agent()
        plan = {
            "task": "代码统计", "complexity": "complex",
            "steps": [
                {"id": 1, "description": "查找文件", "tool": "search_files", "depends_on": []},
                {"id": 2, "description": "统计行数", "tool": "run_command", "depends_on": [1]},
                {"id": 3, "description": "写结果", "tool": "write_file", "depends_on": [2]},
            ],
        }
        result = agent._format_plan_context(plan)
        assert "search_files" in result
        assert "run_command" in result
        assert "write_file" in result
        assert "依赖步骤" in result

    def test_empty_steps_returns_empty(self):
        agent = _make_minimal_agent()
        plan = {"task": "空", "complexity": "simple", "steps": []}
        assert agent._format_plan_context(plan) == ""


@pytest.mark.asyncio
class TestAgentWithPlanning:
    """Integration tests for Agent with planning enabled."""

    @pytest.fixture
    def mock_config(self):
        config = MagicMock()
        config.llm.max_tokens = 4096
        config.agent.max_iterations = 3
        config.agent.planning_enabled = True
        config.agent.planning_complexity_threshold = 2
        return config

    @pytest.fixture
    def mock_llm(self):
        llm = AsyncMock()
        response = MagicMock()
        response.content = "Hello!"
        response.has_tool_calls = False
        response.tool_calls = []
        llm.chat.return_value = response
        return llm

    @pytest.fixture
    def mock_memory(self):
        return AsyncMock()

    @pytest.fixture
    def mock_registry(self):
        registry = MagicMock()
        registry.schemas = []
        registry.get_descriptions.return_value = ""
        registry.names = ["read_file", "write_file", "run_command"]
        return registry

    @pytest.fixture
    def mock_executor(self):
        return AsyncMock()

    async def test_simple_task_skips_planning(
        self, mock_config, mock_llm, mock_memory, mock_registry, mock_executor
    ):
        """Simple greeting: no planner call."""
        agent = Agent(mock_config, mock_llm, mock_memory, mock_registry, mock_executor)
        result = await agent.run("你好")
        assert result == "Hello!"
        assert mock_llm.chat.call_count == 1

    async def test_complex_task_triggers_planning(
        self, mock_config, mock_llm, mock_memory, mock_registry, mock_executor
    ):
        """Complex task: planner + ReAct both called."""
        plan_resp = MagicMock()
        plan_resp.content = json.dumps({
            "task": "分析并写入", "complexity": "complex",
            "steps": [
                {"id": 1, "description": "读文件", "tool": "read_file", "depends_on": []},
                {"id": 2, "description": "写结果", "tool": "write_file", "depends_on": [1]},
            ],
        })
        plan_resp.has_tool_calls = False
        plan_resp.tool_calls = []

        text_resp = MagicMock()
        text_resp.content = "分析完成"
        text_resp.has_tool_calls = False
        text_resp.tool_calls = []

        mock_llm.chat.side_effect = [plan_resp, text_resp]

        agent = Agent(mock_config, mock_llm, mock_memory, mock_registry, mock_executor)
        result = await agent.run("读取 README.md，分析内容，将结果写入 analysis.txt")
        assert result == "分析完成"
        assert mock_llm.chat.call_count >= 2

    async def test_planning_disabled_by_config(
        self, mock_config, mock_llm, mock_memory, mock_registry, mock_executor
    ):
        """With planning disabled, complex task still only calls ReAct once."""
        mock_config.agent.planning_enabled = False
        agent = Agent(mock_config, mock_llm, mock_memory, mock_registry, mock_executor)
        result = await agent.run("读取 README.md 然后写入结果到 analysis.txt")
        assert result == "Hello!"
        assert mock_llm.chat.call_count == 1

    async def test_plan_tracker_created_for_complex_task(
        self, mock_config, mock_llm, mock_memory, mock_registry, mock_executor
    ):
        """复杂任务：应创建 PlanTracker 并触发 on_plan_progress 回调"""
        plan_resp = MagicMock()
        plan_resp.content = json.dumps({
            "task": "多步任务", "complexity": "complex",
            "steps": [
                {"id": 1, "description": "搜索", "tool": "search_files", "depends_on": []},
                {"id": 2, "description": "统计", "tool": "run_command", "depends_on": [1]},
            ],
        })
        plan_resp.has_tool_calls = False
        plan_resp.tool_calls = []

        text_resp = MagicMock()
        text_resp.content = "完成"
        text_resp.has_tool_calls = False
        text_resp.tool_calls = []

        mock_llm.chat.side_effect = [plan_resp, text_resp]

        agent = Agent(mock_config, mock_llm, mock_memory, mock_registry, mock_executor)

        progress_calls = []
        agent.set_callbacks(on_plan_progress=lambda t: progress_calls.append(t))

        await agent.run("搜索所有 Python 文件然后统计行数")
        assert len(progress_calls) >= 1  # 至少初始渲染一次
        assert progress_calls[0].task == "多步任务"

    async def test_tool_call_updates_plan_tracker(
        self, mock_config, mock_llm, mock_memory, mock_registry, mock_executor
    ):
        """工具调用应更新 PlanTracker 步骤状态"""
        plan_resp = MagicMock()
        plan_resp.content = json.dumps({
            "task": "读取并写入", "complexity": "complex",
            "steps": [
                {"id": 1, "description": "读取", "tool": "read_file", "depends_on": []},
                {"id": 2, "description": "写入", "tool": "write_file", "depends_on": [1]},
            ],
        })
        plan_resp.has_tool_calls = False
        plan_resp.tool_calls = []

        tool_resp = MagicMock()
        tool_resp.content = ""
        tool_resp.has_tool_calls = True
        tool_resp.tool_calls = [
            {"id": "c1", "name": "read_file", "arguments": {"path": "test.txt"}}
        ]

        text_resp = MagicMock()
        text_resp.content = "完成"
        text_resp.has_tool_calls = False
        text_resp.tool_calls = []

        mock_llm.chat.side_effect = [plan_resp, tool_resp, text_resp]
        mock_executor.execute_batch.return_value = [
            {"role": "tool", "tool_call_id": "c1", "content": "file content"}
        ]

        agent = Agent(mock_config, mock_llm, mock_memory, mock_registry, mock_executor)

        progress_calls = []
        agent.set_callbacks(on_plan_progress=lambda t: progress_calls.append(t))

        await agent.run("读取 test.txt 然后写入 result.txt")

        # 最后回调应显示步骤 1 已完成
        assert len(progress_calls) >= 2  # 初始化 + 工具调用后更新
        last_tracker = progress_calls[-1]
        assert last_tracker.steps[0].status == "done"

    async def test_plan_tracker_cleared_on_reset(
        self, mock_config, mock_llm, mock_memory, mock_registry, mock_executor
    ):
        """reset() 应清除 PlanTracker"""
        plan_resp = MagicMock()
        plan_resp.content = json.dumps({
            "task": "搜索", "complexity": "complex",
            "steps": [{"id": 1, "description": "搜索", "tool": "search_files", "depends_on": []}],
        })
        plan_resp.has_tool_calls = False
        plan_resp.tool_calls = []

        text_resp = MagicMock()
        text_resp.content = "完成"
        text_resp.has_tool_calls = False
        text_resp.tool_calls = []

        mock_llm.chat.side_effect = [plan_resp, text_resp]

        agent = Agent(mock_config, mock_llm, mock_memory, mock_registry, mock_executor)

        await agent.run("搜索所有 .py 文件")
        assert agent._plan_tracker is not None

        agent.reset()
        assert agent._plan_tracker is None

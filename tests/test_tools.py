"""工具系统测试"""

import pytest
from unittest.mock import MagicMock

from soul_agent.tools.base import Tool, ToolResult
from soul_agent.tools.registry import ToolRegistry
from soul_agent.tools.executor import ToolExecutor
from soul_agent.tools.builtin.file_ops import ReadFileTool, WriteFileTool, ListDirectoryTool
from soul_agent.tools.builtin.search import SearchFilesTool


class TestToolResult:
    def test_success_result(self):
        result = ToolResult(success=True, output="hello")
        assert result.success
        assert result.output == "hello"
        assert result.error is None

    def test_error_result(self):
        result = ToolResult(success=False, output="", error="file not found")
        assert not result.success
        assert result.error == "file not found"


class TestToolRegistry:
    def test_register_and_get(self):
        registry = ToolRegistry()
        tool = MagicMock(spec=Tool)
        tool.name = "test_tool"
        tool.description = "A test tool"
        tool.to_schema.return_value = {"type": "function", "function": {"name": "test_tool"}}

        registry.register(tool)
        assert registry.get("test_tool") is tool
        assert "test_tool" in registry.names

    def test_schemas(self):
        registry = ToolRegistry()
        tool = MagicMock(spec=Tool)
        tool.name = "test_tool"
        tool.to_schema.return_value = {"type": "function", "function": {"name": "test_tool"}}

        registry.register(tool)
        schemas = registry.schemas
        assert len(schemas) == 1

    def test_get_nonexistent(self):
        registry = ToolRegistry()
        assert registry.get("nonexistent") is None


class TestToolExecutor:
    @pytest.mark.asyncio
    async def test_execute_unknown_tool(self):
        registry = ToolRegistry()
        executor = ToolExecutor(registry)

        result = await executor.execute({
            "id": "call_1",
            "name": "unknown_tool",
            "arguments": {},
        })

        assert "未知工具" in result["content"]

    @pytest.mark.asyncio
    async def test_execute_batch(self):
        registry = ToolRegistry()
        executor = ToolExecutor(registry)

        results = await executor.execute_batch([
            {"id": "call_1", "name": "unknown1", "arguments": {}},
            {"id": "call_2", "name": "unknown2", "arguments": {}},
        ])

        assert len(results) == 2


class TestReadFileTool:
    @pytest.mark.asyncio
    async def test_read_existing_file(self, tmp_path):
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello world", encoding="utf-8")

        tool = ReadFileTool()
        result = await tool.execute(path=str(test_file))
        assert result.success
        assert result.output == "hello world"

    @pytest.mark.asyncio
    async def test_read_nonexistent_file(self):
        tool = ReadFileTool()
        result = await tool.execute(path="/nonexistent/file.txt")
        assert not result.success
        assert result.error is not None

    def test_schema(self):
        tool = ReadFileTool()
        schema = tool.to_schema()
        assert schema["function"]["name"] == "read_file"
        assert "path" in schema["function"]["parameters"]["properties"]


class TestWriteFileTool:
    @pytest.mark.asyncio
    async def test_write_file(self, tmp_path):
        test_file = tmp_path / "output.txt"

        tool = WriteFileTool()
        result = await tool.execute(path=str(test_file), content="test content")
        assert result.success
        assert test_file.read_text(encoding="utf-8") == "test content"

    @pytest.mark.asyncio
    async def test_write_creates_parent_dirs(self, tmp_path):
        test_file = tmp_path / "subdir" / "deep" / "output.txt"

        tool = WriteFileTool()
        result = await tool.execute(path=str(test_file), content="nested")
        assert result.success
        assert test_file.exists()


class TestListDirectoryTool:
    @pytest.mark.asyncio
    async def test_list_directory(self, tmp_path):
        (tmp_path / "file1.txt").write_text("a")
        (tmp_path / "file2.py").write_text("b")

        tool = ListDirectoryTool()
        result = await tool.execute(path=str(tmp_path))
        assert result.success
        assert "file1.txt" in result.output
        assert "file2.py" in result.output

    @pytest.mark.asyncio
    async def test_list_nonexistent_dir(self):
        tool = ListDirectoryTool()
        result = await tool.execute(path="/nonexistent/dir")
        assert not result.success


class TestSearchFilesTool:
    @pytest.mark.asyncio
    async def test_search_files(self, tmp_path):
        (tmp_path / "test.py").write_text("def hello():\n    print('hello')\n")
        (tmp_path / "other.txt").write_text("nothing here")

        tool = SearchFilesTool()
        result = await tool.execute(pattern="hello", path=str(tmp_path))
        assert result.success
        assert "test.py" in result.output

    @pytest.mark.asyncio
    async def test_search_no_match(self, tmp_path):
        (tmp_path / "test.txt").write_text("nothing")

        tool = SearchFilesTool()
        result = await tool.execute(pattern="xyz123", path=str(tmp_path))
        assert result.success
        assert "未找到" in result.output or result.output.strip() == ""

"""文件操作工具"""
from pathlib import Path

from soul_agent.tools.base import Tool, ToolResult

MAX_READ_SIZE = 100 * 1024  # 100KB


class ReadFileTool(Tool):
    name = "read_file"
    description = "读取指定路径的文件内容"
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "文件路径",
            },
            "encoding": {
                "type": "string",
                "description": "文件编码，默认 utf-8",
                "default": "utf-8",
            },
        },
        "required": ["path"],
    }

    async def execute(self, **kwargs) -> ToolResult:
        path = kwargs["path"]
        encoding = kwargs.get("encoding", "utf-8")

        file_path = Path(path)
        if not file_path.exists():
            return ToolResult(success=False, output="", error=f"文件不存在: {path}")
        if not file_path.is_file():
            return ToolResult(success=False, output="", error=f"不是文件: {path}")
        if file_path.stat().st_size > MAX_READ_SIZE:
            return ToolResult(
                success=False, output="", error=f"文件过大 (>{MAX_READ_SIZE // 1024}KB): {path}"
            )

        try:
            content = file_path.read_text(encoding=encoding)
            return ToolResult(success=True, output=content)
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))


class WriteFileTool(Tool):
    name = "write_file"
    description = "将内容写入指定路径的文件，自动创建父目录"
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "文件路径",
            },
            "content": {
                "type": "string",
                "description": "要写入的内容",
            },
            "encoding": {
                "type": "string",
                "description": "文件编码，默认 utf-8",
                "default": "utf-8",
            },
        },
        "required": ["path", "content"],
    }

    async def execute(self, **kwargs) -> ToolResult:
        path = kwargs["path"]
        content = kwargs["content"]
        encoding = kwargs.get("encoding", "utf-8")

        try:
            file_path = Path(path)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding=encoding)
            return ToolResult(success=True, output=f"已写入文件: {path}")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))


class ListDirectoryTool(Tool):
    name = "list_directory"
    description = "列出目录内容"
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "目录路径",
            },
            "recursive": {
                "type": "boolean",
                "description": "是否递归列出子目录，默认 false",
                "default": False,
            },
        },
        "required": ["path"],
    }

    async def execute(self, **kwargs) -> ToolResult:
        path = kwargs["path"]
        recursive = kwargs.get("recursive", False)

        dir_path = Path(path)
        if not dir_path.exists():
            return ToolResult(success=False, output="", error=f"目录不存在: {path}")
        if not dir_path.is_dir():
            return ToolResult(success=False, output="", error=f"不是目录: {path}")

        try:
            entries = []
            if recursive:
                for item in sorted(dir_path.rglob("*")):
                    rel = item.relative_to(dir_path)
                    prefix = "[目录]" if item.is_dir() else "[文件]"
                    entries.append(f"{prefix} {rel}")
            else:
                for item in sorted(dir_path.iterdir()):
                    prefix = "[目录]" if item.is_dir() else "[文件]"
                    entries.append(f"{prefix} {item.name}")

            if not entries:
                return ToolResult(success=True, output="(空目录)")

            return ToolResult(success=True, output="\n".join(entries))
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))

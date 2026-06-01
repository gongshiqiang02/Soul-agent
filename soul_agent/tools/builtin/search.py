"""文件搜索工具"""
from pathlib import Path

from soul_agent.tools.base import Tool, ToolResult

MAX_RESULTS = 100


class SearchFilesTool(Tool):
    name = "search_files"
    description = "在目录中搜索文件内容，返回匹配的文件和行号"
    parameters = {
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "要搜索的文本模式",
            },
            "path": {
                "type": "string",
                "description": "搜索的目录路径，默认当前目录",
                "default": ".",
            },
            "file_pattern": {
                "type": "string",
                "description": "文件名glob模式，如 '*.py'，默认搜索所有文件",
                "default": "*",
            },
        },
        "required": ["pattern"],
    }

    async def execute(self, **kwargs) -> ToolResult:
        pattern = kwargs["pattern"]
        path = kwargs.get("path", ".")
        file_pattern = kwargs.get("file_pattern", "*")

        dir_path = Path(path)
        if not dir_path.exists():
            return ToolResult(success=False, output="", error=f"目录不存在: {path}")
        if not dir_path.is_dir():
            return ToolResult(success=False, output="", error=f"不是目录: {path}")

        matches = []
        try:
            for file_path in sorted(dir_path.rglob(file_pattern)):
                if not file_path.is_file():
                    continue
                try:
                    text = file_path.read_text(encoding="utf-8", errors="ignore")
                except (PermissionError, OSError):
                    continue

                for line_num, line in enumerate(text.splitlines(), start=1):
                    if pattern in line:
                        rel_path = file_path.relative_to(dir_path)
                        matches.append(f"{rel_path}:{line_num}: {line.strip()}")
                        if len(matches) >= MAX_RESULTS:
                            break
                if len(matches) >= MAX_RESULTS:
                    break
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))

        if not matches:
            return ToolResult(success=True, output=f"未找到匹配 '{pattern}' 的内容")

        result = "\n".join(matches)
        if len(matches) >= MAX_RESULTS:
            result += f"\n...(结果已截断，最多显示 {MAX_RESULTS} 条)"

        return ToolResult(success=True, output=result)

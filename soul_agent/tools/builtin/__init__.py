"""内置工具"""
from soul_agent.tools.builtin.file_ops import ReadFileTool, WriteFileTool, ListDirectoryTool
from soul_agent.tools.builtin.shell import RunCommandTool
from soul_agent.tools.builtin.web import WebRequestTool
from soul_agent.tools.builtin.search import SearchFilesTool


def register_builtin_tools(registry, config):
    """注册所有内置工具"""
    enabled = config.tools.enabled
    all_tools = {
        "read_file": ReadFileTool(),
        "write_file": WriteFileTool(),
        "list_directory": ListDirectoryTool(),
        "run_command": RunCommandTool(config.tools.shell),
        "web_request": WebRequestTool(),
        "search_files": SearchFilesTool(),
    }
    for name, tool in all_tools.items():
        if name in enabled:
            registry.register(tool)

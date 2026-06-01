"""Shell命令工具"""
import asyncio

from soul_agent.tools.base import Tool, ToolResult

MAX_OUTPUT_LENGTH = 10000


class RunCommandTool(Tool):
    name = "run_command"
    description = "在系统shell中执行命令"
    parameters = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "要执行的shell命令",
            },
            "timeout": {
                "type": "integer",
                "description": "超时时间（秒），默认使用配置值",
            },
        },
        "required": ["command"],
    }

    def __init__(self, shell_config=None):
        if shell_config:
            self._timeout = shell_config.timeout
            self._blocked = shell_config.blocked_commands
        else:
            self._timeout = 30
            self._blocked = ["rm -rf /", "format"]

    async def execute(self, **kwargs) -> ToolResult:
        command = kwargs["command"]
        timeout = kwargs.get("timeout", self._timeout)

        # 检查是否包含被阻止的命令
        for blocked in self._blocked:
            if blocked in command:
                return ToolResult(
                    success=False, output="", error=f"命令被阻止 (包含 '{blocked}')"
                )

        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=timeout
            )

            stdout_text = stdout.decode("utf-8", errors="replace")
            stderr_text = stderr.decode("utf-8", errors="replace")

            output_parts = []
            if stdout_text:
                output_parts.append(stdout_text)
            if stderr_text:
                output_parts.append(f"[stderr]\n{stderr_text}")

            output = "\n".join(output_parts)
            if len(output) > MAX_OUTPUT_LENGTH:
                output = output[:MAX_OUTPUT_LENGTH] + "\n...(输出被截断)"

            if process.returncode == 0:
                return ToolResult(success=True, output=output or "(无输出)")
            else:
                return ToolResult(
                    success=False,
                    output=output,
                    error=f"命令退出码: {process.returncode}",
                )
        except asyncio.TimeoutError:
            process.kill()
            return ToolResult(success=False, output="", error=f"命令超时 ({timeout}秒)")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))

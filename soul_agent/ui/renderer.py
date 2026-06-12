"""Rich终端渲染器"""

import os
from rich.console import Console, Group
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.spinner import Spinner
from rich.text import Text
from rich.table import Table

from soul_agent.ui.themes import get_theme


class Renderer:
    """终端渲染器"""

    def __init__(self, theme_name: str = "monokai"):
        self.console = Console()
        self.theme = get_theme(theme_name)
        self._live: Live | None = None  # 统一的底部Live区域
        self._plan_tracker = None  # 当前计划
        self._status_text: str = ""  # spinner状态文本
        self._stream_buffer: str = ""  # 流式回复缓冲
        self._stream_active: bool = False  # 本轮是否有流式输出

    def render_welcome(self, config=None, tool_count=0, memory_enabled=False):
        """渲染欢迎界面"""
        welcome = Text()
        welcome.append("🤖 Soul-agent", style="bold bright_cyan")
        welcome.append(" — 更懂你的通用Agent\n\n", style="dim")

        if config:
            welcome.append("模型: ", style="dim")
            welcome.append(f"{config.llm.model}\n", style="bright_cyan")
            welcome.append("Provider: ", style="dim")
            welcome.append(f"{config.llm.provider}\n", style="cyan")
            welcome.append("工作目录: ", style="dim")
            welcome.append(f"{os.getcwd()}\n", style="cyan")
            welcome.append("已启用工具: ", style="dim")
            welcome.append(f"{tool_count} 个\n", style="green")
            welcome.append("记忆系统: ", style="dim")
            welcome.append(f"{'启用' if memory_enabled else '禁用'}\n\n", style="green" if memory_enabled else "yellow")

        welcome.append("输入你的问题开始对话，输入 ", style="dim")
        welcome.append("/help", style="bold yellow")
        welcome.append(" 查看帮助，", style="dim")
        welcome.append("/quit", style="bold yellow")
        welcome.append(" 退出\n", style="dim")

        self.console.print(Panel(welcome, border_style=self.theme["border_color"]))

    def render_user_input(self, text: str):
        """渲染用户输入"""
        self.console.print(f"\n[{self.theme['user_color']}]👤 You:[/] {text}")

    def render_assistant(self, text: str):
        """渲染助手回复（支持Markdown）"""
        self.console.print(f"\n[{self.theme['assistant_color']}]🤖 Soul-agent:[/]")
        if not text or not text.strip():
            self.console.print("  [dim](Agent 无输出)[/]")
            return
        try:
            md = Markdown(text)
            self.console.print(md)
        except Exception:
            self.console.print(text)

    def render_tool_call(self, tool_name: str, args: dict):
        """渲染工具调用 - Claude Code紧凑风格"""
        # 流式回复中若有缓冲,先输出它
        if self._stream_buffer:
            self._flush_stream_buffer()

        # 格式化参数摘要
        param_str = self._format_tool_params(tool_name, args)
        line = f"⏺ [{self.theme['tool_color']}]{tool_name}[/]({param_str})"
        if len(line) > 120:
            line = line[:117] + "..."
        self.console.print(line)

    def _format_tool_params(self, tool_name: str, args: dict) -> str:
        """格式化工具参数摘要"""
        if tool_name == "read_file":
            return args.get("path", "?")
        elif tool_name == "write_file":
            path = args.get("path", "?")
            content = args.get("content", "")
            size_kb = len(content) / 1024
            if size_kb >= 1:
                return f"{path}, {size_kb:.1f}KB"
            else:
                return f"{path}, {len(content)}B"
        elif tool_name == "list_directory":
            path = args.get("path", ".")
            recursive = args.get("recursive", False)
            return f"{path}, recursive" if recursive else path
        elif tool_name == "run_command":
            return args.get("command", "?")
        elif tool_name == "web_request":
            method = args.get("method", "GET")
            url = args.get("url", "?")
            return f"{method} {url}"
        elif tool_name == "search_files":
            pattern = args.get("pattern", "?")
            path = args.get("path", ".")
            return f'"{pattern}", path: {path}' if path != "." else f'"{pattern}"'
        else:
            # 未知工具 fallback
            parts = []
            for k, v in args.items():
                v_str = str(v)
                if len(v_str) > 60:
                    v_str = v_str[:57] + "..."
                parts.append(f"{k}={v_str}")
            return ", ".join(parts) if parts else ""

    def _flush_stream_buffer(self):
        """输出流式缓冲区内容"""
        if self._stream_buffer:
            self.console.print(f"\n[{self.theme['assistant_color']}]🤖 Soul-agent:[/]")
            self.console.print(Markdown(self._stream_buffer))
            self._stream_buffer = ""

    def render_tool_result(self, tool_name: str, success: bool, output: str, error: str | None = None):
        """渲染工具执行结果 - 连接符风格"""
        connector = f"[{self.theme['connector_color']}]  ⎿[/] "

        if not success:
            self.console.print(f"{connector}[{self.theme['error_color']}]错误: {error or output}[/]")
            return

        # 成功结果 - 特殊处理read_file
        if tool_name == "read_file":
            lines = output.count("\n") + 1
            self.console.print(f"{connector}读取 {lines} 行")
            return

        # 其他工具 - 显示前3行
        lines = output.split("\n")
        for i, line in enumerate(lines[:3]):
            if i == 0:
                self.console.print(f"{connector}{line}")
            else:
                self.console.print(f"    {line}")

        if len(lines) > 3:
            extra = len(lines) - 3
            self.console.print(f"    [{self.theme['stats_color']}]… +{extra} 行[/]")


    def render_error(self, message: str):
        """渲染错误信息"""
        self.console.print(f"[{self.theme['error_color']}]❌ {message}[/]")

    def render_info(self, message: str):
        """渲染提示信息"""
        self.console.print(f"[{self.theme['info_color']}]{message}[/]")

    def render_memory_list(self, memories: list):
        """渲染记忆列表"""
        if not memories:
            self.console.print("[dim]暂无记忆[/]")
            return

        table = Table(title="📝 记忆列表", show_header=True, header_style="bold bright_cyan")
        table.add_column("类型", style="yellow", width=12)
        table.add_column("内容", style="white")
        table.add_column("重要性", style="green", width=8)

        for m in memories:
            table.add_row(
                m.memory_type,
                m.content[:60] + ("..." if len(m.content) > 60 else ""),
                f"{m.importance:.1f}",
            )

        self.console.print(table)

    def render_conversation_list(self, conversations: list):
        """渲染历史会话列表"""
        if not conversations:
            self.console.print("[dim]暂无历史会话[/]")
            return

        table = Table(title="📜 历史会话", show_header=True, header_style="bold bright_cyan")
        table.add_column("#", style="dim", width=5)
        table.add_column("标题", style="white", max_width=40)
        table.add_column("消息数", style="green", width=8, justify="right")
        table.add_column("更新时间", style="yellow", width=20)

        for i, conv in enumerate(conversations, 1):
            updated = conv.updated_at.strftime("%m-%d %H:%M") if hasattr(conv, "updated_at") else "?"
            title = conv.title or "未命名"
            if len(title) > 40:
                title = title[:37] + "..."
            table.add_row(str(i), title, str(conv.message_count), updated)

        self.console.print(table)

    def _build_plan_panel(self, tracker) -> Panel:
        """构建计划面板（不输出）"""
        lines = [f"任务: {tracker.task}  ({tracker.done_count}/{tracker.total_count})"]
        lines.append("")
        for step in tracker.steps:
            icon = "☑" if step.status == "done" else "☐"
            tool_str = f" [dim]{step.tool}[/]" if step.tool else ""
            lines.append(f"  {icon} {step.id}. {step.description}{tool_str}")
        return Panel("\n".join(lines), title="📋 执行计划", border_style="bright_cyan")

    def _build_live_content(self):
        """构建统一Live区域的内容"""
        parts = []

        # 计划面板(如果有)
        if self._plan_tracker and self._plan_tracker.steps:
            parts.append(self._build_plan_panel(self._plan_tracker))

        # Spinner状态行或流式Markdown
        if self._stream_buffer:
            # 流式回复显示
            parts.append(Markdown(self._stream_buffer + " ▌"))
        elif self._status_text:
            # Spinner状态
            spinner = Spinner("dots", text=self._status_text, style=self.theme["info_color"])
            parts.append(spinner)

        return Group(*parts) if parts else Text("")

    def begin_turn(self):
        """开始新的对话轮次,启动Live"""
        self._stream_buffer = ""
        self._stream_active = False
        if self._live is None:
            self._live = Live(
                self._build_live_content(),
                console=self.console,
                auto_refresh=True,
                transient=True,
                screen=False,
            )
            self._live.start()
        else:
            self._live.update(self._build_live_content())

    def update_status(self, text: str):
        """更新状态文本(spinner)"""
        self._status_text = text
        if self._live:
            self._live.update(self._build_live_content())

    def on_stream_chunk(self, chunk: str):
        """接收流式回复块"""
        self._stream_buffer += chunk
        self._stream_active = True
        if self._live:
            self._live.update(self._build_live_content())

    def end_turn(self, stats: dict | None = None, final_text: str = ""):
        """结束对话轮次,停止Live并输出最终内容"""
        # 停止Live
        if self._live:
            self._live.stop()
            self._live = None

        # 输出最终回复
        if self._stream_active and final_text:
            # 流式模式已经逐步显示,直接输出完整版
            self.render_assistant(final_text)
        elif final_text:
            # 非流式fallback
            self.render_assistant(final_text)

        # 输出统计行
        if stats:
            parts = [f"[{self.theme['success_color']}]✓ 完成[/]"]
            if stats.get("tool_calls", 0) > 0:
                parts.append(f"{stats['tool_calls']} 次工具调用")
            if stats.get("elapsed"):
                parts.append(f"{stats['elapsed']:.1f}s")
            if stats.get("tokens"):
                tokens = stats["tokens"]
                if tokens >= 1000:
                    parts.append(f"{tokens/1000:.1f}k tokens")
                else:
                    parts.append(f"{tokens} tokens")
            self.console.print(f"[{self.theme['stats_color']}]{' · '.join(parts)}[/]\n")

        # 清空状态
        self._status_text = ""
        self._stream_buffer = ""
        self._stream_active = False

    def render_plan_steps(self, tracker):
        """更新计划面板"""
        self._plan_tracker = tracker
        if self._live:
            self._live.update(self._build_live_content())

    def clear_plan_live(self):
        """清除Live区域(兼容方法)"""
        if self._live:
            self._live.stop()
            self._live = None
        self._plan_tracker = None
        self._status_text = ""
        self._stream_buffer = ""


    def render_help(self):
        """渲染帮助信息"""
        help_text = """
[bold]可用命令:[/]
  [yellow]/help[/]     显示帮助信息
  [yellow]/memory[/]   查看记忆列表
  [yellow]/history[/]  查看历史会话
  [yellow]/name[/]     为当前会话命名，如 /name 技术讨论
  [yellow]/clear[/]    清除对话历史（新会话）
  [yellow]/config[/]   显示当前配置
  [yellow]/quit[/]     退出程序

[bold]使用方式:[/]
  直接输入问题即可与 Soul-agent 对话
  Agent 会自动使用工具完成任务
"""
        self.console.print(Panel(help_text.strip(), title="帮助", border_style="bright_blue"))

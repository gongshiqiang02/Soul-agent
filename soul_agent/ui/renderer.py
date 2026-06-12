"""Rich终端渲染器"""

import os
import time

from rich.console import Console, Group
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.spinner import Spinner
from rich.text import Text
from rich.table import Table

from soul_agent.ui.themes import get_theme


class _BlinkingToolLines:
    """执行中的工具调用行：圆点随Live自动刷新明暗交替，模拟闪烁"""

    def __init__(self, pending: list, interval: float = 0.5):
        self._pending = pending
        self._interval = interval

    def __rich_console__(self, console, options):
        bright = int(time.monotonic() / self._interval) % 2 == 0
        dot_style = "white" if bright else "dim"
        for _name, body in self._pending:
            line = Text()
            line.append("● ", style=dot_style)
            line.append_text(body)
            yield line


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
        self._pending_tools: list[tuple[str, Text]] = []  # 执行中的工具调用 (名称, 行正文)

    def render_welcome(self, config=None, tool_count=0, memory_enabled=False):
        """渲染欢迎界面"""
        welcome = Text()
        welcome.append("soul-agent", style="bold bright_cyan")
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

    def _with_marker(self, renderable):
        """将内容与 ● 标记并排：圆点与首行同行，后续行缩进 2 格对齐"""
        grid = Table.grid(expand=True)
        grid.add_column(width=2)
        grid.add_column(ratio=1, overflow="fold")
        grid.add_row(f"[{self.theme['assistant_color']}]●[/]", renderable)
        return grid

    def render_assistant(self, text: str):
        """渲染助手回复（支持Markdown），圆点与正文首行同行"""
        self.console.print()
        if not text or not text.strip():
            self.console.print(f"[{self.theme['assistant_color']}]●[/] [dim](Agent 无输出)[/]")
            return
        try:
            self.console.print(self._with_marker(Markdown(text)))
        except Exception:
            self.console.print(self._with_marker(Text(text)))

    def render_tool_call(self, tool_name: str, args: dict):
        """渲染工具调用 - 执行中在Live区闪烁圆点，结果返回后定色输出"""
        # 流式回复中若有缓冲,先输出它
        if self._stream_buffer:
            self._flush_stream_buffer()

        self._pending_tools.append((tool_name, self._format_tool_line(tool_name, args)))
        if self._live:
            self._live.update(self._build_live_content())

    def _format_tool_line(self, tool_name: str, args: dict) -> Text:
        """构建工具调用行正文（不含圆点）: tool_name(参数摘要)"""
        param_str = self._format_tool_params(tool_name, args)
        max_param = 120 - len(tool_name) - 4
        if len(param_str) > max_param:
            param_str = param_str[: max_param - 3] + "..."
        body = Text()
        body.append(tool_name, style=self.theme["tool_color"])
        body.append(f"({param_str})")
        return body

    def _pop_pending_tool(self, tool_name: str) -> Text | None:
        """按名称取出执行中的工具行，找不到时按FIFO兜底"""
        for i, (name, _body) in enumerate(self._pending_tools):
            if name == tool_name:
                return self._pending_tools.pop(i)[1]
        if self._pending_tools:
            return self._pending_tools.pop(0)[1]
        return None

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
            self.console.print()
            self.console.print(self._with_marker(Markdown(self._stream_buffer)))
            self._stream_buffer = ""

    def render_tool_result(self, tool_name: str, success: bool, output: str, error: str | None = None):
        """渲染工具执行结果 - 圆点定色(绿=成功/红=失败) + 连接符摘要"""
        dot_color = self.theme["success_color"] if success else self.theme["error_color"]
        line = Text()
        line.append("● ", style=dot_color)
        body = self._pop_pending_tool(tool_name)
        if body is not None:
            line.append_text(body)
        else:
            line.append(tool_name, style=self.theme["tool_color"])
        self.console.print()
        self.console.print(line)
        if self._live:
            self._live.update(self._build_live_content())

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
        self.console.print(f"[{self.theme['error_color']}]✗ {message}[/]")

    def render_info(self, message: str):
        """渲染提示信息"""
        self.console.print(f"[{self.theme['info_color']}]{message}[/]")

    def render_memory_list(self, memories: list):
        """渲染记忆列表"""
        if not memories:
            self.console.print("[dim]暂无记忆[/]")
            return

        table = Table(title="记忆列表", show_header=True, header_style="bold bright_cyan")
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

        table = Table(title="历史会话", show_header=True, header_style="bold bright_cyan")
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
            icon = "✓" if step.status == "done" else "·"
            tool_str = f" [dim]{step.tool}[/]" if step.tool else ""
            lines.append(f"  {icon} {step.id}. {step.description}{tool_str}")
        return Panel("\n".join(lines), title="执行计划", border_style="bright_cyan")

    def _build_live_content(self):
        """构建统一Live区域的内容"""
        parts = []

        # 计划面板(如果有)
        if self._plan_tracker and self._plan_tracker.steps:
            parts.append(self._build_plan_panel(self._plan_tracker))

        # 执行中的工具调用(圆点闪烁)
        if self._pending_tools:
            parts.append(_BlinkingToolLines(self._pending_tools))

        # Spinner状态行或流式Markdown
        if self._stream_buffer:
            # 流式回复显示
            parts.append(self._with_marker(Markdown(self._stream_buffer + " ▌")))
        elif self._status_text:
            # Spinner状态
            spinner = Spinner("dots", text=self._status_text, style=self.theme["info_color"])
            parts.append(spinner)

        # 顶部留一行空行，与上方已输出内容隔开
        return Group(Text(""), *parts) if parts else Text("")

    def begin_turn(self):
        """开始新的对话轮次,启动Live"""
        self._stream_buffer = ""
        self._stream_active = False
        self._pending_tools = []
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

        # 异常中断时可能残留未返回结果的工具调用，以错误色定格输出
        for _name, body in self._pending_tools:
            line = Text()
            line.append("● ", style=self.theme["error_color"])
            line.append_text(body)
            self.console.print()
            self.console.print(line)
        self._pending_tools = []

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
            self.console.print(f"\n[{self.theme['stats_color']}]{' · '.join(parts)}[/]\n")

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
        self._pending_tools = []


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

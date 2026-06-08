"""Rich终端渲染器"""

from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text
from rich.table import Table

from soul_agent.ui.themes import get_theme


class Renderer:
    """终端渲染器"""

    def __init__(self, theme_name: str = "monokai"):
        self.console = Console()
        self.theme = get_theme(theme_name)
        self._plan_live: Live | None = None  # 固定在底部的计划面板

    def render_welcome(self):
        """渲染欢迎界面"""
        welcome = Text()
        welcome.append("🤖 Soul-agent", style="bold bright_cyan")
        welcome.append(" — 更懂你的通用Agent\n", style="dim")
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
        try:
            md = Markdown(text)
            self.console.print(md)
        except Exception:
            self.console.print(text)

    def render_tool_call(self, tool_name: str, args: dict):
        """渲染工具调用"""
        self.console.print(
            f"  [{self.theme['tool_color']}]🔧 调用工具: {tool_name}[/]",
            style="dim",
        )

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

    def render_plan_steps(self, tracker):
        """渲染计划步骤进度面板，固定在终端底部原地刷新"""
        if not tracker.steps:
            return

        panel = self._build_plan_panel(tracker)

        if self._plan_live is None:
            self._plan_live = Live(
                panel, console=self.console,
                auto_refresh=True, transient=True, screen=False,
            )
            self._plan_live.start()
        else:
            self._plan_live.update(panel)

    def clear_plan_live(self):
        """停止计划面板的 Live 显示，恢复终端正常滚动"""
        if self._plan_live:
            self._plan_live.stop()
            self._plan_live = None

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

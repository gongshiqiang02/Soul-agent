"""Rich终端渲染器"""

from rich.console import Console
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

    def render_help(self):
        """渲染帮助信息"""
        help_text = """
[bold]可用命令:[/]
  [yellow]/help[/]     显示帮助信息
  [yellow]/memory[/]   查看记忆列表
  [yellow]/clear[/]    清除对话历史
  [yellow]/config[/]   显示当前配置
  [yellow]/quit[/]     退出程序

[bold]使用方式:[/]
  直接输入问题即可与 Soul-agent 对话
  Agent 会自动使用工具完成任务
"""
        self.console.print(Panel(help_text.strip(), title="帮助", border_style="bright_blue"))

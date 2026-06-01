"""CLI命令定义"""

import asyncio
import click
from rich.console import Console

console = Console()


@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx):
    """Soul-agent: 更懂你的通用Agent"""
    if ctx.invoked_subcommand is None:
        # 默认启动交互式对话
        ctx.invoke(chat)


@cli.command()
def chat():
    """启动交互式对话"""
    from soul_agent.app import run_chat
    asyncio.run(run_chat())


@cli.command()
@click.argument("message")
def ask(message: str):
    """单次提问模式"""
    from soul_agent.app import run_ask
    asyncio.run(run_ask(message))


@cli.command()
def memory():
    """查看记忆列表"""
    from soul_agent.app import run_memory
    asyncio.run(run_memory())


@cli.command()
def config():
    """显示当前配置"""
    from soul_agent.config.settings import load_config

    cfg = load_config()
    console.print("[bold]当前配置:[/]")
    console.print(f"  模型: {cfg.llm.model}")
    console.print(f"  Provider: {cfg.llm.provider}")
    console.print(f"  Base URL: {cfg.llm.base_url or '默认'}")
    console.print(f"  记忆系统: {'启用' if cfg.memory.enabled else '禁用'}")
    console.print(f"  最大迭代: {cfg.agent.max_iterations}")
    console.print(f"  已启用工具: {', '.join(cfg.tools.enabled)}")

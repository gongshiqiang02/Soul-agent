"""应用逻辑 - 连接各模块"""

from soul_agent.config.settings import load_config
from soul_agent.llm.client import LLMClient
from soul_agent.memory.manager import MemoryManager
from soul_agent.tools.registry import ToolRegistry
from soul_agent.tools.executor import ToolExecutor
from soul_agent.tools.builtin import register_builtin_tools
from soul_agent.core.agent import Agent
from soul_agent.ui.renderer import Renderer
from soul_agent.ui.input import InputHandler
from soul_agent.utils.logger import logger


async def create_agent(config=None):
    """创建并初始化Agent实例"""
    if config is None:
        config = load_config()

    # LLM客户端
    llm_client = LLMClient(config.llm)

    # 记忆系统
    memory_manager = None
    if config.memory.enabled:
        memory_manager = MemoryManager(config.memory, llm_client)
        await memory_manager.initialize()

    # 工具系统
    tool_registry = ToolRegistry()
    register_builtin_tools(tool_registry, config)
    tool_executor = ToolExecutor(tool_registry)

    # Agent
    agent = Agent(config, llm_client, memory_manager, tool_registry, tool_executor)

    return agent


async def run_chat():
    """交互式对话主循环"""
    config = load_config()
    renderer = Renderer(config.ui.theme)
    input_handler = InputHandler()

    renderer.render_welcome()

    try:
        agent = await create_agent(config)
    except Exception as e:
        renderer.render_error(f"初始化失败: {e}")
        logger.error(f"初始化失败: {e}", exc_info=True)
        return

    # 设置工具调用回调
    agent.set_callbacks(
        on_tool_call=lambda name, args: renderer.render_tool_call(name, args),
    )

    while True:
        try:
            user_input = await input_handler.get_input()
        except Exception:
            break

        if not user_input:
            continue

        # 系统命令处理
        if user_input.startswith("/"):
            cmd = user_input.lower().strip()
            if cmd == "/quit" or cmd == "/exit":
                renderer.render_info("👋 再见！")
                break
            elif cmd == "/help":
                renderer.render_help()
                continue
            elif cmd == "/clear":
                agent.reset()
                renderer.render_info("✅ 对话历史已清除")
                continue
            elif cmd == "/memory":
                if agent.memory:
                    memories = await agent.memory.list_all()
                    renderer.render_memory_list(memories)
                else:
                    renderer.render_info("记忆系统未启用")
                continue
            elif cmd == "/config":
                from rich.pretty import pretty_repr
                renderer.render_info(f"模型: {config.llm.model}")
                renderer.render_info(f"Provider: {config.llm.provider}")
                continue
            else:
                renderer.render_error(f"未知命令: {cmd}，输入 /help 查看帮助")
                continue

        # 正常对话
        renderer.render_user_input(user_input)

        try:
            response = await agent.run(user_input)
            renderer.render_assistant(response)
        except Exception as e:
            renderer.render_error(f"处理失败: {e}")
            logger.error(f"Agent运行错误: {e}", exc_info=True)


async def run_ask(message: str):
    """单次提问"""
    config = load_config()
    renderer = Renderer(config.ui.theme)

    try:
        agent = await create_agent(config)
        response = await agent.run(message)
        renderer.render_assistant(response)
    except Exception as e:
        renderer.render_error(f"处理失败: {e}")


async def run_memory():
    """显示记忆列表"""
    config = load_config()
    renderer = Renderer(config.ui.theme)

    if not config.memory.enabled:
        renderer.render_info("记忆系统未启用")
        return

    memory_manager = MemoryManager(config.memory)
    await memory_manager.initialize()
    memories = await memory_manager.list_all()
    renderer.render_memory_list(memories)

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

    # 预创建首个会话（让 /history 可立即看到），同时注入持久化回调
    if memory_manager:
        await memory_manager.create_conversation_with_id(
            agent.conversation.conversation_id
        )
        agent._conversation_started = True
        agent.conversation.set_persist_callback(agent._persist_message)

    return agent


async def run_chat():
    """交互式对话主循环"""
    config = load_config()
    renderer = Renderer(config.ui.theme)

    try:
        agent = await create_agent(config)
    except Exception as e:
        renderer.render_error(f"初始化失败: {e}")
        logger.error(f"初始化失败: {e}", exc_info=True)
        return

    # 显示欢迎界面(在agent创建成功后)
    renderer.render_welcome(
        config=config,
        tool_count=len(agent.tools.names),
        memory_enabled=config.memory.enabled,
    )

    input_handler = InputHandler()

    try:
        await _chat_loop(agent, renderer, config, input_handler)
    finally:
        # 退出前等待后台记忆更新完成，避免最后一轮记忆丢失
        await agent.drain_background_tasks()


async def _chat_loop(agent, renderer, config, input_handler):
    """聊天循环主体，从 run_chat 拆出以便退出时统一收尾"""
    # 设置工具调用回调
    agent.set_callbacks(
        on_tool_call=lambda name, args: renderer.render_tool_call(name, args),
        on_plan_progress=lambda tracker: renderer.render_plan_steps(tracker),
        on_tool_result=lambda name, success, output, error: renderer.render_tool_result(name, success, output, error),
        on_stream=renderer.on_stream_chunk,
        on_status=renderer.update_status,
    )

    while True:
        try:
            user_input = await input_handler.get_input()
        except Exception:
            break

        if not user_input:
            continue

        # 清除上一轮的 Live 面板
        renderer.clear_plan_live()

        # 系统命令处理
        if user_input.startswith("/"):
            cmd = user_input.lower().strip()
            if cmd == "/quit" or cmd == "/exit":
                renderer.render_info("Goodbye!")
                break
            elif cmd == "/help":
                renderer.render_help()
                continue
            elif cmd == "/clear":
                agent.reset()
                renderer.render_info("✓ 对话历史已清除")
                continue
            elif cmd == "/memory":
                if agent.memory:
                    memories = await agent.memory.list_all()
                    renderer.render_memory_list(memories)
                else:
                    renderer.render_info("记忆系统未启用")
                continue
            elif cmd.startswith("/history"):
                if agent.memory:
                    conversations = await agent.memory.list_conversations()
                    renderer.render_conversation_list(conversations)
                else:
                    renderer.render_info("记忆系统未启用，无法查看历史会话")
                continue
            elif cmd.startswith("/name"):
                parts = user_input.strip().split(maxsplit=1)
                if len(parts) < 2:
                    renderer.render_error("用法: /name <会话名称>")
                else:
                    new_name = parts[1].strip()
                    await agent.rename_conversation(new_name)
                    renderer.render_info(f"✓ 会话已重命名为: {new_name}")
                continue
            elif cmd == "/config":
                renderer.render_info(f"模型: {config.llm.model}")
                renderer.render_info(f"Provider: {config.llm.provider}")
                continue
            else:
                renderer.render_error(f"未知命令: {cmd}，输入 /help 查看帮助")
                continue

        # 正常对话
        try:
            renderer.begin_turn()
            response = await agent.run(user_input)
            renderer.end_turn(agent.last_run_stats, response)
        except Exception as e:
            renderer.end_turn()  # 确保Live被停止
            renderer.render_error(f"处理失败: {e}")
            logger.error(f"Agent运行错误: {e}", exc_info=True)


async def run_ask(message: str):
    """单次提问"""
    config = load_config()
    renderer = Renderer(config.ui.theme)

    try:
        agent = await create_agent(config)

        # 设置回调,单次模式也显示工具调用
        agent.set_callbacks(
            on_tool_call=lambda name, args: renderer.render_tool_call(name, args),
            on_tool_result=lambda name, success, output, error: renderer.render_tool_result(name, success, output, error),
            on_stream=renderer.on_stream_chunk,
            on_status=renderer.update_status,
        )

        renderer.begin_turn()
        response = await agent.run(message)
        renderer.end_turn(agent.last_run_stats, response)
        # 单次模式下事件循环即将结束，必须等待后台记忆更新完成，否则任务被取消
        await agent.drain_background_tasks()
    except Exception as e:
        renderer.end_turn()  # 确保Live被停止
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

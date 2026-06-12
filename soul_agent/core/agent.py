"""Agent主循环 - ReAct模式"""

import asyncio
import json
import uuid
from soul_agent.core.conversation import Conversation
from soul_agent.core.context import ContextManager
from soul_agent.core.planner import TaskPlanner
from soul_agent.core.plan_tracker import PlanTracker
from soul_agent.llm.prompts import SYSTEM_PROMPT
from soul_agent.utils.logger import logger


class Agent:
    """Agent主循环，协调各模块完成用户任务"""

    # 复杂度指标词（启发式判断任务是否需要规划）
    _COMPLEXITY_INDICATORS = [
        "然后", "之后", "接着", "首先", "最后", "再",
        "并且", "同时", "还要", "另外", "以及",
        "分析", "查找", "搜索", "创建", "部署", "安装",
        "统计", "计算", "比较", "修改", "改写", "重构",
        "总结", "提取", "生成", "转换", "编译", "测试",
        "读取", "写入", "文件", "目录", "命令", "执行",
        "运行", "下载", "请求", "网页", "配置",
    ]

    def __init__(self, config, llm_client, memory_manager, tool_registry, tool_executor):
        self.config = config
        self.llm = llm_client
        self.memory = memory_manager
        self.tools = tool_registry
        self.executor = tool_executor
        self.conversation = Conversation()
        self._conversation_started = False  # 标记会话是否已入库
        self.context_mgr = ContextManager(max_tokens=config.llm.max_tokens)
        self.planner = TaskPlanner(llm_client)
        self._on_tool_call = None  # callback for UI
        self._on_stream = None  # callback for streaming
        self._plan_tracker = None  # 计划进度追踪器
        self._on_plan_progress = None  # callback for plan progress
        self._on_tool_result = None  # callback for tool results
        self._on_status = None  # callback for status updates
        self.last_run_stats = {}  # 最近一次运行的统计信息
        self._background_tasks: set[asyncio.Task] = set()

    def set_callbacks(self, on_tool_call=None, on_stream=None, on_plan_progress=None, on_tool_result=None, on_status=None):
        """设置UI回调"""
        self._on_tool_call = on_tool_call
        self._on_stream = on_stream
        self._on_plan_progress = on_plan_progress
        self._on_tool_result = on_tool_result
        self._on_status = on_status

    async def run(self, user_input: str) -> str:
        """处理一次用户输入，返回最终响应"""
        import time
        start_time = time.time()
        tool_calls_count = 0
        total_tokens = 0

        # 0. 确保会话已持久化
        await self._ensure_conversation_persisted()

        # 0.5. 自动判断是否需要任务规划
        plan_context = ""
        if self.config.agent.planning_enabled:
            complexity = self._estimate_complexity(user_input)
            threshold = self.config.agent.planning_complexity_threshold
            if complexity >= threshold:
                try:
                    plan = await self.planner.plan(user_input, self.tools.names)
                    plan_context = self._format_plan_context(plan)
                    # 创建进度追踪器（仅当计划有工具步骤时）
                    if plan_context:
                        self._plan_tracker = PlanTracker(plan)
                        if self._on_plan_progress:
                            self._on_plan_progress(self._plan_tracker)
                    if plan_context:
                        logger.debug(
                            "任务规划已生成: complexity=%d, steps=%d",
                            complexity, len(plan.get("steps", []))
                        )
                except Exception as e:
                    logger.warning("任务规划失败，跳过: %s", e)

        # 1. 检索相关记忆
        relevant_memories = []
        if self.memory:
            try:
                relevant_memories = await self.memory.retrieve(user_input)
            except Exception as e:
                logger.warning(f"记忆检索失败: {e}")

        # 2. 构建系统提示词
        system_prompt = SYSTEM_PROMPT.replace(
            "{tool_descriptions}", self.tools.get_descriptions()
        )

        # 3. 构建消息
        messages = self.conversation.build_messages(
            user_input=user_input,
            system_prompt=system_prompt,
            memories=relevant_memories,
            plan_context=plan_context,
        )

        # 3.5. 将用户消息持久化到对话历史（必须在工具消息之前）
        self.conversation.messages.append({"role": "user", "content": user_input})
        self.conversation._schedule_persist("user", user_input)

        # 4. Agent循环（ReAct）
        max_iter = self.config.agent.max_iterations
        final_content = ""

        for i in range(max_iter):
            # 更新状态
            if self._on_status:
                self._on_status(f"思考中… (第 {i+1} 轮)")

            response = await self.llm.chat(
                messages,
                tools=self.tools.schemas if self.tools.schemas else None,
                stream=True,
                on_delta=self._on_stream,
            )

            # 累积tokens
            if hasattr(response, "usage") and response.usage:
                usage_total = getattr(response.usage, "total_tokens", None)
                if isinstance(usage_total, int):
                    total_tokens += usage_total

            if response.has_tool_calls:
                tool_calls_count += len(response.tool_calls)

                # 通知UI正在执行工具
                if self._on_tool_call:
                    for tc in response.tool_calls:
                        self._on_tool_call(tc["name"], tc["arguments"])

                # 将assistant的tool_calls消息加入
                assistant_msg = {"role": "assistant", "content": response.content or ""}
                assistant_msg["tool_calls"] = [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {
                            "name": tc["name"],
                            "arguments": json.dumps(tc["arguments"], ensure_ascii=False),
                        },
                    }
                    for tc in response.tool_calls
                ]
                messages.append(assistant_msg)

                # 执行工具
                results = await self.executor.execute_batch(response.tool_calls)

                # 通知UI工具执行结果
                if self._on_tool_result:
                    for tc, result in zip(response.tool_calls, results):
                        name = tc["name"]
                        content = result.get("content", "")
                        is_error = content.startswith("错误:")
                        self._on_tool_result(
                            name, not is_error, content,
                            content[3:] if is_error else None,
                        )

                # 更新计划进度
                if self._plan_tracker:
                    for tc in response.tool_calls:
                        self._plan_tracker.mark_tool_done(tc["name"])
                    if self._on_plan_progress:
                        self._on_plan_progress(self._plan_tracker)

                messages.extend(results)

                # 持久化工具交互消息，确保"继续"时不丢失上下文
                self.conversation.add_message(assistant_msg)
                for r in results:
                    self.conversation.add_message(r)
            else:
                final_content = response.content
                break
        else:
            if response and response.content:
                final_content = response.content
            else:
                final_content = (
                    f"已达到最大工具调用次数（{max_iter}）。"
                    "任务尚未完成，可以输入 '继续' 来恢复执行。"
                )

        # 5. 添加助手最终回复到对话历史，并裁剪过长的历史
        self.conversation.messages.append({"role": "assistant", "content": final_content})
        self.conversation._schedule_persist("assistant", final_content)
        # 保留最近 20 轮对话（含工具消息），防止上下文过长
        max_msgs = self.config.agent.max_iterations * 2 + 40  # 留足余量
        if len(self.conversation.messages) > max_msgs:
            self.conversation.messages = self.conversation.messages[-max_msgs:]

        # 6. 记录统计信息。长期记忆提取在后台执行，不计入用户可见响应耗时。
        elapsed = time.time() - start_time
        self.last_run_stats = {
            "iterations": i + 1,
            "tool_calls": tool_calls_count,
            "elapsed": elapsed,
            "tokens": total_tokens if total_tokens > 0 else None,
        }

        # 7. 后台更新长期记忆，避免回复结束后继续阻塞下一次输入。
        self._schedule_memory_update(user_input, final_content)

        return final_content

    def _schedule_memory_update(self, user_input: str, final_content: str):
        """后台更新记忆，避免阻塞 Agent 响应收尾。"""
        if not self.memory:
            return
        try:
            task = asyncio.create_task(
                self._process_memory_update(user_input, final_content)
            )
        except RuntimeError:
            logger.warning("记忆更新调度失败：当前没有运行中的事件循环")
            return

        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
        task.add_done_callback(self._consume_background_task_result)

    async def _process_memory_update(self, user_input: str, final_content: str):
        try:
            await self.memory.process_turn(user_input, final_content)
        except Exception as e:
            logger.warning(f"记忆更新失败: {e}")

    @staticmethod
    def _consume_background_task_result(task: asyncio.Task):
        try:
            task.result()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.warning(f"后台任务失败: {e}")

    async def drain_background_tasks(self):
        """等待当前已调度的后台任务完成。主要用于测试或程序退出前收尾。"""
        if not self._background_tasks:
            return
        await asyncio.gather(*tuple(self._background_tasks), return_exceptions=True)

    def _estimate_complexity(self, user_input: str) -> int:
        """快速估算任务复杂度（0-10）。零 LLM 开销，纯启发式。"""
        text = user_input.lower()
        score = 0

        # 1. 长度因子
        length = len(text)
        if length > 80:
            score += 3
        elif length > 40:
            score += 2
        elif length > 15:
            score += 1

        # 2. 复杂度指标词密度
        indicator_count = sum(1 for ind in self._COMPLEXITY_INDICATORS if ind in text)
        score += min(indicator_count, 5)

        # 3. 多句 / 多段落
        if "。" in text or "\n" in text:
            score += 2
        elif "；" in text or "，" in text:
            score += 1

        return min(score, 10)

    def _format_plan_context(self, plan: dict) -> str:
        """将规划结果格式化为注入 system prompt 的文本。
        简单任务（无工具单步）返回空字符串。
        """
        steps = plan.get("steps", [])
        complexity = plan.get("complexity", "simple")
        has_tools = any(s.get("tool") for s in steps)

        # 不值得注入计划的情况
        if complexity == "simple" and not has_tools:
            return ""
        if len(steps) <= 1 and not has_tools:
            return ""

        lines = ["## 执行计划"]
        lines.append(f"任务: {plan.get('task', '未指定')}")
        lines.append("")
        for step in steps:
            step_id = step.get("id", "?")
            desc = step.get("description", "")
            tool = step.get("tool")
            deps = step.get("depends_on", [])
            tool_str = f" [工具: {tool}]" if tool else ""
            dep_str = f" (依赖步骤: {deps})" if deps else ""
            lines.append(f"  {step_id}. {desc}{tool_str}{dep_str}")
        lines.append("")
        lines.append("请按计划步骤执行，但可根据实际情况灵活调整。")
        return "\n".join(lines)

    def reset(self):
        """重置对话 — 创建新会话"""
        self.conversation.clear()
        self.conversation.conversation_id = str(uuid.uuid4())
        self._conversation_started = False
        self._plan_tracker = None

    async def rename_conversation(self, title: str):
        """重命名当前会话"""
        if self.memory:
            await self._ensure_conversation_persisted()
            await self.memory.update_conversation_title(
                self.conversation.conversation_id, title
            )

    async def _ensure_conversation_persisted(self):
        """确保当前会话已在数据库中创建"""
        if self._conversation_started:
            return
        if self.memory:
            await self.memory.create_conversation_with_id(
                self.conversation.conversation_id
            )
            # 注入持久化回调
            self.conversation.set_persist_callback(self._persist_message)
        self._conversation_started = True

    async def _persist_message(self, conversation_id, role, content, tool_calls):
        """持久化单条消息的回调"""
        if self.memory:
            await self.memory.long_term.save_message(
                conversation_id, role, content, tool_calls
            )

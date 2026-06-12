# Soul-Agent API 参考手册

> 本文档涵盖 Soul-Agent 所有公开模块、类、方法及数据结构的完整说明。

---

## 目录

- [soul\_agent.core — 核心模块](#soul_agentcore--核心模块)
  - [Agent](#agent)
  - [Conversation](#conversation)
  - [ContextManager](#contextmanager)
  - [TaskPlanner](#taskplanner)
  - [PlanTracker](#plantracker)
- [soul\_agent.memory — 记忆模块](#soul_agentmemory--记忆模块)
  - [MemoryManager](#memorymanager)
  - [ShortTermMemory](#shorttermmemory)
  - [MemoryEntry](#memoryentry)
  - [LongTermMemory](#longtermmemory)
  - [MemoryRetriever](#memoryretriever)
  - [ConversationSummarizer](#conversationsummarizer)
- [soul\_agent.tools — 工具模块](#soul_agenttools--工具模块)
  - [ToolResult](#toolresult)
  - [Tool（抽象基类）](#tool抽象基类)
  - [ToolRegistry](#toolregistry)
  - [ToolExecutor](#toolexecutor)
  - [内置工具](#内置工具)
- [soul\_agent.llm — 大语言模型模块](#soul_agentllm--大语言模型模块)
  - [LLMClient](#llmclient)
  - [LLMResponse](#llmresponse)
  - [OpenAIProvider](#openaiprovider)
  - [LocalProvider](#localprovider)
- [soul\_agent.config — 配置模块](#soul_agentconfig--配置模块)
  - [配置数据类](#配置数据类)
  - [load\_config](#load_config)
  - [辅助函数](#辅助函数)
- [soul\_agent.ui — 用户界面模块](#soul_agentui--用户界面模块)
  - [Renderer](#renderer)
  - [InputHandler](#inputhandler)
  - [主题系统](#主题系统)
- [soul\_agent.app — 应用入口](#soul_agentapp--应用入口)
- [soul\_agent.utils — 工具函数](#soul_agentutils--工具函数)
  - [日志](#日志)
  - [异常类](#异常类)

---

## soul_agent.core — 核心模块

### Agent

```
soul_agent.core.agent.Agent
```

Agent 是 Soul-Agent 的核心调度器，负责接收用户输入并通过 ReAct 循环协调 LLM、记忆与工具调用，最终产出回复。

#### `__init__(config, llm_client, memory_manager, tool_registry, tool_executor)`

构造 Agent 实例。

| 参数 | 类型 | 说明 |
|------|------|------|
| `config` | `AgentConfig` | Agent 配置对象 |
| `llm_client` | `LLMClient` | 大语言模型客户端 |
| `memory_manager` | `MemoryManager` | 记忆管理器 |
| `tool_registry` | `ToolRegistry` | 工具注册表 |
| `tool_executor` | `ToolExecutor` | 工具执行器 |

```python
from soul_agent.core.agent import Agent

agent = Agent(
    config=agent_config,
    llm_client=llm_client,
    memory_manager=memory_manager,
    tool_registry=tool_registry,
    tool_executor=tool_executor,
)
```

---

#### `set_callbacks(on_tool_call=None, on_stream=None, on_plan_progress=None, on_tool_result=None, on_status=None)`

注册 UI 回调函数，用于在工具调用、工具结果、计划进度、流式输出或状态更新时通知前端。

| 参数 | 类型 | 说明 |
|------|------|------|
| `on_tool_call` | `Callable \| None` | 工具调用时触发，参数 `(tool_name, args_dict)` |
| `on_tool_result` | `Callable \| None` | 工具执行后触发，参数 `(tool_name, success, output, error_or_None)` |
| `on_plan_progress` | `Callable \| None` | 计划进度更新时触发，参数 `(plan_tracker)` |
| `on_stream` | `Callable \| None` | 流式输出时触发的回调 |
| `on_status` | `Callable \| None` | 状态更新时触发，参数 `(status_text)` |

```python
agent.set_callbacks(
    on_tool_call=lambda name, args: print(f"调用工具: {name}"),
    on_tool_result=lambda name, success, output, err: print(f"✓ {name}" if success else f"✗ {name}: {err}"),
    on_plan_progress=lambda tracker: print(f"进度: {tracker.done_count}/{tracker.total_count}"),
    on_stream=lambda chunk: print(chunk, end=""),
    on_status=lambda text: print(text),
)
```

---

#### `async run(user_input: str) -> str`

主入口方法。接收一条用户输入，经过 ReAct（推理-行动）循环处理后返回最终回复文本。

流程：检索记忆 → 构建消息 → 调用 LLM → 判断是否需要工具调用 → 执行工具 → 再次调用 LLM → 记录统计 → 调度后台记忆更新 → 返回最终回复。

| 参数 | 类型 | 说明 |
|------|------|------|
| `user_input` | `str` | 用户输入的文本 |

**返回值：** `str` — 助手的最终回复文本。

长期记忆提取不阻塞该方法返回。`run()` 会在最终回复写入 `Conversation` 后调度后台任务执行 `MemoryManager.process_turn()`，因此 UI 可以在统计行输出后立即进入下一次输入。

```python
reply = await agent.run("帮我读取 config.yaml 文件的内容")
print(reply)
```

---

#### `async drain_background_tasks()`

等待当前 Agent 已调度的后台维护任务完成。主要用于测试或程序退出前收尾；正常交互中不需要每轮调用。应用入口的退出路径（`run_chat()` 聊天循环结束后、`run_ask()` 回复输出后）会自动调用该方法，确保最后一轮的记忆提取在事件循环关闭前完成。

```python
await agent.drain_background_tasks()
```

---

#### `reset()`

清空对话历史，创建新会话（新 UUID），旧会话保留在数据库中。

```python
agent.reset()
```

---

#### `async rename_conversation(title: str)`

重命名当前会话标题。

| 参数 | 类型 | 说明 |
|------|------|------|
| `title` | `str` | 新标题 |

```python
await agent.rename_conversation("关于微服务架构的讨论")
```

---

### Conversation

```
soul_agent.core.conversation.Conversation
```

管理对话历史，负责构建发送给 LLM 的消息列表。

#### `__init__()`

初始化空对话。自动生成唯一 UUID `conversation_id`，内部维护 `messages` 列表。

```python
from soul_agent.core.conversation import Conversation

conv = Conversation()
print(conv.conversation_id)  # 自动生成的 UUID 字符串
```

---

#### `build_messages(user_input, system_prompt, memories=None, plan_context="") -> list[dict]`

构建完整的消息列表，供 LLM 调用。

当提供 `memories` 时，会将记忆内容注入系统提示；当提供 `plan_context` 时，会将执行计划注入系统提示。

```
已知的用户信息：
- [memory_type] content
- [memory_type] content
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `user_input` | `str` | 当前用户输入 |
| `system_prompt` | `str` | 系统提示词 |
| `memories` | `list[MemoryEntry] \| None` | 检索到的相关记忆条目 |
| `plan_context` | `str` | 任务执行计划文本（由 `Agent._format_plan_context()` 格式化），默认空 |

**返回值：** `list[dict]` — 格式为 `[{"role": "system", "content": "..."}, ..., {"role": "user", "content": "..."}]`。

```python
messages = conv.build_messages(
    user_input="你好",
    system_prompt="你是一个有用的助手。",
    memories=retrieved_memories,
    plan_context="## 执行计划\n任务: 分析代码结构\n\n1. 读取文件 [工具: read_file]\n",
)
# [
#   {"role": "system", "content": "你是一个有用的助手。\n\n已知的用户信息：\n- [preference] 喜欢简洁的回答\n\n## 执行计划\n..."},
#   ... (历史消息，含工具调用) ...
#   {"role": "user", "content": "你好"}
# ]
```

---

#### `add_turn(user_input, assistant_reply)`

添加一轮完整对话（用户输入 + 助手回复）。自动裁剪历史，保留最多 **20 轮**（即 40 条消息）。

| 参数 | 类型 | 说明 |
|------|------|------|
| `user_input` | `str` | 用户输入 |
| `assistant_reply` | `str` | 助手回复 |

```python
conv.add_turn("今天天气如何？", "今天天气晴朗，气温 25°C。")
```

---

#### `add_message(message: dict)`

添加单条消息到对话历史。

| 参数 | 类型 | 说明 |
|------|------|------|
| `message` | `dict` | 消息字典，如 `{"role": "user", "content": "..."}` |

```python
conv.add_message({"role": "assistant", "content": "收到"})
```

---

#### `clear()`

清空所有对话历史。

```python
conv.clear()
```

---

#### `set_persist_callback(callback)`

注入消息持久化回调。`add_turn()` 和 `add_message()` 会自动通过此回调将消息写入数据库。

回调签名：`async def callback(conversation_id, role, content, tool_calls)`

```python
conv.set_persist_callback(agent._persist_message)
```

> `add_turn()` 和 `add_message()` 在调用此回调时采用 fire-and-forget 模式（`asyncio.ensure_future`），不阻塞主流程。

---

### ContextManager

```
soul_agent.core.context.ContextManager
```

管理上下文窗口，负责 token 估算与消息裁剪，防止超出模型限制。

#### `__init__(max_tokens=4096)`

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `max_tokens` | `int` | `4096` | 上下文窗口的最大 token 数 |

```python
from soul_agent.core.context import ContextManager

ctx = ContextManager(max_tokens=8192)
```

---

#### `estimate_tokens(text) -> int`

估算文本的 token 数量。采用启发式算法：中文约 **1.5 个字符对应 1 个 token**，英文约 **4 个字符对应 1 个 token**。

| 参数 | 类型 | 说明 |
|------|------|------|
| `text` | `str` | 待估算的文本 |

**返回值：** `int` — 估算的 token 数。

```python
tokens = ctx.estimate_tokens("你好，世界！Hello, World!")
```

---

#### `trim_messages(messages, max_tokens=None) -> list[dict]`

裁剪消息列表使其不超过 token 上限。**始终保留系统消息（第一条）和最后一条用户消息**，优先丢弃中间的历史消息。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `messages` | `list[dict]` | — | 待裁剪的消息列表 |
| `max_tokens` | `int \| None` | `None` | 覆盖默认的最大 token 数；`None` 使用构造时的值 |

**返回值：** `list[dict]` — 裁剪后的消息列表。

```python
trimmed = ctx.trim_messages(messages, max_tokens=2048)
```

---

### TaskPlanner

```
soul_agent.core.planner.TaskPlanner
```

使用 LLM 将复杂任务分解为多步骤执行计划。

#### `__init__(llm_client)`

| 参数 | 类型 | 说明 |
|------|------|------|
| `llm_client` | `LLMClient` | 大语言模型客户端 |

```python
from soul_agent.core.planner import TaskPlanner

planner = TaskPlanner(llm_client)
```

---

#### `async plan(task, available_tools) -> dict`

为给定任务生成分步执行计划。

| 参数 | 类型 | 说明 |
|------|------|------|
| `task` | `str` | 任务描述 |
| `available_tools` | `list[str]` | 可用工具名称列表 |

**返回值：** `dict` — 执行计划，结构如下：

```python
{
    "task": "部署应用到服务器",
    "complexity": "complex",
    "steps": [
        {
            "id": 1,
            "description": "读取配置文件",
            "tool": "read_file",
            "depends_on": []
        },
        {
            "id": 2,
            "description": "执行部署命令",
            "tool": "run_command",
            "depends_on": [1]
        }
    ]
}
```

```python
plan = await planner.plan(
    task="在项目根目录查找所有 Python 文件并统计行数",
    available_tools=["search_files", "run_command", "read_file"],
)
```

---

### PlanTracker

```
soul_agent.core.plan_tracker.PlanTracker
```

计划进度追踪器，将 `TaskPlanner` 生成的计划转化为可追踪状态，将 Agent 的工具调用自动匹配到计划步骤。

#### `__init__(plan: dict)`

| 参数 | 类型 | 说明 |
|------|------|------|
| `plan` | `dict` | TaskPlanner.plan() 返回的计划字典 |

```python
from soul_agent.core.plan_tracker import PlanTracker

tracker = PlanTracker(plan)
print(tracker.task)  # 任务描述
```

---

#### `mark_tool_done(tool_name: str) -> int | None`

将工具调用匹配到第一个 pending 步骤，标记为 done。

| 参数 | 类型 | 说明 |
|------|------|------|
| `tool_name` | `str` | 工具名称 |

**返回值：** `int | None` — 匹配到的 step id，没有匹配到则返回 `None`。

---

**只读属性：**

| 属性 | 类型 | 说明 |
|------|------|------|
| `task` | `str` | 任务描述 |
| `complexity` | `str` | 复杂度（`simple` 或 `complex`） |
| `steps` | `list[PlanStep]` | 步骤列表 |
| `done_count` | `int` | 已完成步骤数 |
| `total_count` | `int` | 总步骤数 |
| `all_done` | `bool` | 全部步骤是否已完成 |
| `has_tool_steps` | `bool` | 是否至少有一个需要工具的步骤 |

### PlanStep

```
soul_agent.core.plan_tracker.PlanStep
```

计划步骤数据类。

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | `int` | 步骤序号 |
| `description` | `str` | 步骤描述 |
| `tool` | `str \| None` | 需要的工具名（无则为 `None`） |
| `depends_on` | `list[int]` | 依赖的前置步骤 ID |
| `status` | `str` | 状态：`"pending"` 或 `"done"` |

---

## soul_agent.memory — 记忆模块

### MemoryManager

```
soul_agent.memory.manager.MemoryManager
```

记忆系统的统一管理器，协调短期记忆、长期记忆（SQLite）与向量检索（ChromaDB）。

#### `__init__(config: MemoryConfig, llm_client=None)`

| 参数 | 类型 | 说明 |
|------|------|------|
| `config` | `MemoryConfig` | 记忆系统配置 |
| `llm_client` | `LLMClient \| None` | LLM 客户端，用于自动提取记忆和摘要生成 |

```python
from soul_agent.memory.manager import MemoryManager

mm = MemoryManager(config=memory_config, llm_client=llm_client)
```

---

#### `async initialize()`

初始化记忆系统，包括 SQLite 数据库建表和 ChromaDB 集合创建。**使用前必须调用。**

```python
await mm.initialize()
```

---

#### `async retrieve(query, top_k=5) -> list[MemoryEntry]`

根据查询语句检索最相关的记忆条目。若 ChromaDB 可用则优先进行向量检索，否则回退到关键词搜索。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `query` | `str` | — | 查询文本 |
| `top_k` | `int` | `5` | 返回的最大条目数 |

**返回值：** `list[MemoryEntry]` — 按相关度排序的记忆条目列表。

```python
memories = await mm.retrieve("用户的编程语言偏好", top_k=3)
for m in memories:
    print(f"[{m.memory_type}] {m.content} (重要性: {m.importance})")
```

---

#### `async process_turn(user_input, assistant_reply)`

处理一轮对话，先写入短期记忆，再使用 LLM 自动提取值得长期记住的信息。仅当提取到的记忆重要性超过 `importance_threshold`（由配置决定）时才会存储。

在标准 Agent 流程中，该方法由 `Agent._schedule_memory_update()` 后台调度，不会阻塞 `Agent.run()` 返回。手动直接调用时仍然需要 `await`，调用方会等待记忆提取和存储完成。

| 参数 | 类型 | 说明 |
|------|------|------|
| `user_input` | `str` | 用户输入 |
| `assistant_reply` | `str` | 助手回复 |

```python
await mm.process_turn(
    user_input="我最喜欢用 Python 写代码",
    assistant_reply="好的，我记住了你喜欢 Python！",
)
```

---

#### `async store(content, memory_type, importance=0.5, metadata=None) -> str`

手动存储一条记忆。执行**双写**：同时写入 SQLite（结构化存储）和 ChromaDB（向量索引）。ChromaDB 的同步 `upsert` 会通过线程执行，避免阻塞事件循环。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `content` | `str` | — | 记忆内容 |
| `memory_type` | `str` | — | 记忆类型，如 `"preference"`、`"fact"`、`"experience"` |
| `importance` | `float` | `0.5` | 重要性评分，范围 0.0 ~ 1.0 |
| `metadata` | `dict \| None` | `None` | 附加元数据 |

**返回值：** `str` — 新建记忆的唯一 ID。

```python
memory_id = await mm.store(
    content="用户是一名后端开发工程师",
    memory_type="fact",
    importance=0.8,
    metadata={"source": "self_introduction"},
)
```

---

#### `async forget(memory_id)`

删除指定 ID 的记忆条目（同时从 SQLite 和 ChromaDB 中移除）。

| 参数 | 类型 | 说明 |
|------|------|------|
| `memory_id` | `str` | 记忆条目 ID |

```python
await mm.forget("a1b2c3d4-xxxx-xxxx-xxxx-xxxxxxxxxxxx")
```

---

#### `async list_all(memory_type=None) -> list[MemoryEntry]`

列出所有记忆条目，可按类型筛选。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `memory_type` | `str \| None` | `None` | 筛选类型；`None` 表示返回全部 |

**返回值：** `list[MemoryEntry]`

```python
all_facts = await mm.list_all(memory_type="fact")
```

---

---

### 对话持久化方法（MemoryManager）

以下方法桥接至 LongTermMemory，用于管理历史会话。

#### `async create_conversation(title="") -> str`

创建新会话。

```python
conv_id = await mm.create_conversation(title="新对话")
```

#### `async create_conversation_with_id(conversation_id, title="")`

使用预生成 ID 创建会话。

```python
await mm.create_conversation_with_id(agent.conversation.conversation_id)
```

#### `async save_conversation_turn(conversation_id, user_input, assistant_reply)`

持久化一轮用户-助手消息对。

```python
await mm.save_conversation_turn(conv_id, "你好", "你好！")
```

#### `async list_conversations(limit=50)`

列出历史会话。

```python
conversations = await mm.list_conversations()
```

#### `async get_conversation_messages(conversation_id) -> list[dict]`

加载某会话的全部消息。

```python
messages = await mm.get_conversation_messages(conv_id)
```

#### `async update_conversation_title(conversation_id, title)`

重命名会话。

```python
await mm.update_conversation_title(conv_id, "重要讨论")
```

#### `async summarize_conversation() -> str`

对当前对话历史生成摘要文本。

**返回值：** `str` — 对话摘要。

```python
summary = await mm.summarize_conversation()
print(summary)
```

---

### ShortTermMemory

```
soul_agent.memory.short_term.ShortTermMemory
```

短期记忆，以 dataclass 形式维护当前会话的消息列表。

**字段：**

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `messages` | `list[dict]` | `[]` | 消息列表 |
| `max_messages` | `int` | `50` | 最大消息数 |

#### `add(role, content)`

添加一条消息。超出 `max_messages` 时自动丢弃最早的消息。

| 参数 | 类型 | 说明 |
|------|------|------|
| `role` | `str` | 角色，如 `"user"`、`"assistant"` |
| `content` | `str` | 消息内容 |

```python
from soul_agent.memory.short_term import ShortTermMemory

stm = ShortTermMemory()
stm.add("user", "你好")
stm.add("assistant", "你好！有什么可以帮你的？")
```

---

#### `get_messages() -> list[dict]`

获取当前所有消息。

**返回值：** `list[dict]` — 如 `[{"role": "user", "content": "..."}]`

```python
msgs = stm.get_messages()
```

---

#### `clear()`

清空所有短期记忆。

```python
stm.clear()
```

---

### MemoryEntry

```
soul_agent.memory.long_term.MemoryEntry
```

记忆条目数据类，表示一条长期记忆。

**字段：**

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `id` | `str` | — | 唯一标识符（UUID） |
| `content` | `str` | — | 记忆内容 |
| `memory_type` | `str` | — | 类型，如 `"preference"`、`"fact"`、`"experience"` |
| `importance` | `float` | — | 重要性评分（0.0 ~ 1.0） |
| `created_at` | `datetime` | — | 创建时间 |
| `last_accessed` | `datetime` | — | 最后访问时间 |
| `access_count` | `int` | — | 访问次数 |
| `metadata` | `dict` | — | 附加元数据 |
| `similarity` | `float` | `0.0` | 向量检索时的相似度分数 |

```python
from soul_agent.memory.long_term import MemoryEntry

# 通常由 LongTermMemory 或 MemoryRetriever 返回，无需手动构造
entry: MemoryEntry
print(f"内容: {entry.content}")
print(f"类型: {entry.memory_type}")
print(f"重要性: {entry.importance}")
print(f"相似度: {entry.similarity}")
```

---

### LongTermMemory

```
soul_agent.memory.long_term.LongTermMemory
```

基于 SQLite 的长期记忆持久化存储。

#### `__init__(db_path: str)`

| 参数 | 类型 | 说明 |
|------|------|------|
| `db_path` | `str` | SQLite 数据库文件路径 |

```python
from soul_agent.memory.long_term import LongTermMemory

ltm = LongTermMemory(db_path="data/memory.db")
```

---

#### `async initialize()`

初始化数据库，创建所需的表结构。**使用前必须调用。**

```python
await ltm.initialize()
```

---

#### `async store(content, memory_type, importance=0.5, metadata=None) -> str`

存储一条记忆到 SQLite。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `content` | `str` | — | 记忆内容 |
| `memory_type` | `str` | — | 记忆类型 |
| `importance` | `float` | `0.5` | 重要性评分 |
| `metadata` | `dict \| None` | `None` | 附加元数据 |

**返回值：** `str` — 记忆 ID。

```python
mid = await ltm.store("用户喜欢深色主题", "preference", importance=0.6)
```

---

#### `async get_all(memory_type=None) -> list[MemoryEntry]`

获取所有记忆条目，可按类型筛选。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `memory_type` | `str \| None` | `None` | 筛选类型 |

**返回值：** `list[MemoryEntry]`

```python
all_entries = await ltm.get_all()
prefs = await ltm.get_all(memory_type="preference")
```

---

#### `async search_by_keyword(keyword, top_k=10) -> list[MemoryEntry]`

按关键词搜索记忆（SQLite LIKE 匹配）。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `keyword` | `str` | — | 搜索关键词 |
| `top_k` | `int` | `10` | 最大返回数 |

**返回值：** `list[MemoryEntry]`

```python
results = await ltm.search_by_keyword("Python", top_k=5)
```

---

#### `async update_access(memory_id)`

更新记忆的访问记录：`last_accessed` 设为当前时间，`access_count` 加一。

| 参数 | 类型 | 说明 |
|------|------|------|
| `memory_id` | `str` | 记忆 ID |

```python
await ltm.update_access("a1b2c3d4-xxxx-xxxx-xxxx-xxxxxxxxxxxx")
```

---

#### `async delete(memory_id)`

删除指定记忆。

| 参数 | 类型 | 说明 |
|------|------|------|
| `memory_id` | `str` | 记忆 ID |

```python
await ltm.delete("a1b2c3d4-xxxx-xxxx-xxxx-xxxxxxxxxxxx")
```

---

### ConversationEntry

```
soul_agent.memory.long_term.ConversationEntry
```

会话条目数据类，表示一次持久化的对话记录。

**字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | `str` | 唯一标识符（UUID） |
| `title` | `str` | 会话标题 |
| `created_at` | `datetime` | 创建时间 |
| `updated_at` | `datetime` | 最后更新时间 |
| `message_count` | `int` | 消息数量 |

```python
from soul_agent.memory.long_term import ConversationEntry

conv: ConversationEntry
print(f"标题: {conv.title}")
print(f"消息数: {conv.message_count}")
print(f"更新时间: {conv.updated_at}")
```

---

### 对话持久化方法（LongTermMemory）

以下方法用于会话与消息的持久化存储。

#### `async create_conversation(title="") -> str`

创建新会话，返回 `conversation_id`。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `title` | `str` | `""` | 会话标题 |

```python
conv_id = await ltm.create_conversation(title="技术讨论")
```

---

#### `async create_conversation_with_id(conversation_id, title="") -> str`

使用预生成 ID 创建会话（`INSERT OR IGNORE` 语义，重复调用无副作用）。

```python
conv_id = await ltm.create_conversation_with_id(
    "my-custom-uuid", title="指定ID会话"
)
```

---

#### `async save_message(conversation_id, role, content, tool_calls=None) -> str`

保存一条消息到指定会话。

| 参数 | 类型 | 说明 |
|------|------|------|
| `conversation_id` | `str` | 会话 ID |
| `role` | `str` | 消息角色（`user` / `assistant` / `tool`） |
| `content` | `str` | 消息内容 |
| `tool_calls` | `str \| None` | JSON 序列化的工具调用记录 |

```python
await ltm.save_message(conv_id, "user", "你好")
await ltm.save_message(conv_id, "assistant", "你好！有什么可以帮你的？")
```

---

#### `async list_conversations(limit=50) -> list[ConversationEntry]`

列出所有会话，按更新时间倒序，含消息数量。

```python
conversations = await ltm.list_conversations()
for c in conversations:
    print(f"{c.title} — {c.message_count} 条消息")
```

---

#### `async get_conversation_messages(conversation_id) -> list[dict]`

获取某个会话的全部消息（按创建时间正序）。

```python
messages = await ltm.get_conversation_messages(conv_id)
for msg in messages:
    print(f"[{msg['role']}] {msg['content']}")
```

---

#### `async update_conversation_title(conversation_id, title)`

重命名会话。

```python
await ltm.update_conversation_title(conv_id, "新的标题")
```

---

### MemoryRetriever

```
soul_agent.memory.retriever.MemoryRetriever
```

记忆检索器，结合 ChromaDB 向量搜索与 SQLite 关键词搜索实现混合检索。

#### `__init__(long_term, vector_db_path=None)`

| 参数 | 类型 | 说明 |
|------|------|------|
| `long_term` | `LongTermMemory` | 长期记忆实例 |
| `vector_db_path` | `str \| None` | ChromaDB 持久化路径；`None` 则禁用向量检索 |

```python
from soul_agent.memory.retriever import MemoryRetriever

retriever = MemoryRetriever(
    long_term=ltm,
    vector_db_path="data/chroma_db",
)
```

---

#### `has_vector_search -> bool`

只读属性。指示 ChromaDB 向量检索是否可用。

```python
if retriever.has_vector_search:
    print("向量检索已启用")
```

---

#### `async add_embedding(memory_id, content, metadata=None)`

为一条记忆添加向量嵌入到 ChromaDB。内部通过 `asyncio.to_thread()` 执行同步 `collection.upsert()`。

| 参数 | 类型 | 说明 |
|------|------|------|
| `memory_id` | `str` | 记忆 ID |
| `content` | `str` | 用于生成嵌入的文本内容 |
| `metadata` | `dict \| None` | 附加元数据 |

```python
await retriever.add_embedding(memory_id, "用户偏好使用 Vim 编辑器")
```

---

#### `async delete_embedding(memory_id)`

从 ChromaDB 删除指定记忆的向量嵌入。内部通过 `asyncio.to_thread()` 执行同步 `collection.delete()`。

| 参数 | 类型 | 说明 |
|------|------|------|
| `memory_id` | `str` | 记忆 ID |

```python
await retriever.delete_embedding("a1b2c3d4-xxxx-xxxx-xxxx-xxxxxxxxxxxx")
```

---

#### `async retrieve(query, top_k=5) -> list[MemoryEntry]`

执行混合检索：优先向量语义搜索，向量不可用时回退到关键词搜索。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `query` | `str` | — | 查询文本 |
| `top_k` | `int` | `5` | 最大返回数 |

**返回值：** `list[MemoryEntry]` — 检索结果，包含 `similarity` 分数。

```python
results = await retriever.retrieve("用户的工作环境", top_k=3)
```

---

### ConversationSummarizer

```
soul_agent.memory.summarizer.ConversationSummarizer
```

对话摘要生成器，调用 LLM 对历史消息进行压缩总结。

#### `__init__(llm_client=None)`

| 参数 | 类型 | 说明 |
|------|------|------|
| `llm_client` | `LLMClient \| None` | LLM 客户端；`None` 则摘要功能不可用 |

```python
from soul_agent.memory.summarizer import ConversationSummarizer

summarizer = ConversationSummarizer(llm_client=llm_client)
```

---

#### `async summarize(messages: list[dict]) -> str`

对消息列表生成对话摘要。

| 参数 | 类型 | 说明 |
|------|------|------|
| `messages` | `list[dict]` | 对话消息列表 |

**返回值：** `str` — 生成的摘要文本。

```python
summary = await summarizer.summarize([
    {"role": "user", "content": "帮我分析一下这个错误日志"},
    {"role": "assistant", "content": "这个错误是由于数据库连接超时导致的..."},
    {"role": "user", "content": "怎么修复？"},
    {"role": "assistant", "content": "你可以增加连接池大小或设置重试机制..."},
])
print(summary)
# "用户请求分析错误日志，问题为数据库连接超时，已建议增加连接池和添加重试机制。"
```

---

## soul_agent.tools — 工具模块

### ToolResult

```
soul_agent.tools.base.ToolResult
```

工具执行结果数据类。

**字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `success` | `bool` | 是否执行成功 |
| `output` | `str` | 输出内容 |
| `error` | `str \| None` | 错误信息，成功时为 `None` |

```python
from soul_agent.tools.base import ToolResult

result = ToolResult(success=True, output="文件内容...", error=None)
if result.success:
    print(result.output)
else:
    print(f"错误: {result.error}")
```

---

### Tool（抽象基类）

```
soul_agent.tools.base.Tool(ABC)
```

所有工具必须继承的抽象基类。

**抽象属性：**

| 属性 | 类型 | 说明 |
|------|------|------|
| `name` | `str` | 工具名称（唯一标识） |
| `description` | `str` | 工具功能描述 |
| `parameters` | `dict` | 参数的 JSON Schema 定义 |

#### `abstract async execute(**kwargs) -> ToolResult`

执行工具逻辑。子类必须实现此方法。

**返回值：** `ToolResult`

---

#### `to_schema() -> dict`

生成符合 OpenAI Function Calling 格式的 schema 定义。

**返回值：** `dict` — OpenAI 函数定义。

```python
schema = tool.to_schema()
# {
#     "type": "function",
#     "function": {
#         "name": "read_file",
#         "description": "读取文件内容",
#         "parameters": { ... }
#     }
# }
```

**自定义工具示例：**

```python
from soul_agent.tools.base import Tool, ToolResult

class MyTool(Tool):
    name = "my_tool"
    description = "执行自定义操作"
    parameters = {
        "type": "object",
        "properties": {
            "input": {"type": "string", "description": "输入数据"}
        },
        "required": ["input"]
    }

    async def execute(self, **kwargs) -> ToolResult:
        input_data = kwargs.get("input", "")
        return ToolResult(success=True, output=f"处理结果: {input_data}")
```

---

### ToolRegistry

```
soul_agent.tools.registry.ToolRegistry
```

工具注册表，管理所有可用工具的注册与查找。

#### `register(tool)`

注册一个工具实例。

| 参数 | 类型 | 说明 |
|------|------|------|
| `tool` | `Tool` | 工具实例 |

```python
from soul_agent.tools.registry import ToolRegistry

registry = ToolRegistry()
registry.register(MyTool())
```

---

#### `get(name) -> Tool | None`

按名称获取工具。

| 参数 | 类型 | 说明 |
|------|------|------|
| `name` | `str` | 工具名称 |

**返回值：** `Tool | None` — 对应的工具实例，未找到时返回 `None`。

```python
tool = registry.get("read_file")
if tool:
    result = await tool.execute(path="/tmp/test.txt")
```

---

#### `schemas -> list[dict]`

只读属性。返回所有已注册工具的 OpenAI Function Calling schema 列表。

```python
all_schemas = registry.schemas
# [{"type": "function", "function": {"name": "read_file", ...}}, ...]
```

---

#### `names -> list[str]`

只读属性。返回所有已注册工具的名称列表。

```python
print(registry.names)
# ["read_file", "write_file", "list_directory", ...]
```

---

#### `get_descriptions() -> str`

获取所有工具的描述信息，以格式化字符串返回。

**返回值：** `str` — 格式化的工具描述文本。

```python
print(registry.get_descriptions())
# read_file: 读取指定路径的文件内容
# write_file: 将内容写入指定路径的文件
# ...
```

---

### ToolExecutor

```
soul_agent.tools.executor.ToolExecutor
```

工具执行器，将 LLM 返回的工具调用请求转化为实际执行。

#### `__init__(registry)`

| 参数 | 类型 | 说明 |
|------|------|------|
| `registry` | `ToolRegistry` | 工具注册表 |

```python
from soul_agent.tools.executor import ToolExecutor

executor = ToolExecutor(registry)
```

---

#### `async execute(tool_call: dict) -> dict`

执行单个工具调用，返回符合 OpenAI 消息格式的结果。

| 参数 | 类型 | 说明 |
|------|------|------|
| `tool_call` | `dict` | LLM 返回的工具调用信息，含 `id`、`function.name`、`function.arguments` |

**返回值：** `dict` — `role="tool"` 的消息字典。

```python
result_msg = await executor.execute({
    "id": "call_abc123",
    "function": {
        "name": "read_file",
        "arguments": '{"path": "/tmp/test.txt"}'
    }
})
# {"role": "tool", "tool_call_id": "call_abc123", "content": "文件内容..."}
```

---

#### `async execute_batch(tool_calls) -> list[dict]`

批量执行多个工具调用。

| 参数 | 类型 | 说明 |
|------|------|------|
| `tool_calls` | `list[dict]` | 工具调用列表 |

**返回值：** `list[dict]` — 结果消息列表。

```python
results = await executor.execute_batch(response.tool_calls)
```

---

### 内置工具

以下工具随框架内置，均继承自 `Tool` 抽象基类。

---

#### ReadFileTool

```
soul_agent.tools.builtin.ReadFileTool
```

读取文件内容。**文件大小限制：100KB。**

| 属性 | 值 |
|------|----|
| `name` | `"read_file"` |

**参数 Schema：**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `path` | `string` | 是 | — | 文件路径 |
| `encoding` | `string` | 否 | `"utf-8"` | 文件编码 |

```python
result = await read_file_tool.execute(path="src/main.py")
result = await read_file_tool.execute(path="data/gbk.csv", encoding="gbk")
```

---

#### WriteFileTool

```
soul_agent.tools.builtin.WriteFileTool
```

写入文件内容。**自动创建不存在的父目录。**

| 属性 | 值 |
|------|----|
| `name` | `"write_file"` |

**参数 Schema：**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `path` | `string` | 是 | — | 文件路径 |
| `content` | `string` | 是 | — | 写入内容 |
| `encoding` | `string` | 否 | `"utf-8"` | 文件编码 |

```python
result = await write_file_tool.execute(
    path="output/result.txt",
    content="处理完成",
)
```

---

#### ListDirectoryTool

```
soul_agent.tools.builtin.ListDirectoryTool
```

列出目录内容。

| 属性 | 值 |
|------|----|
| `name` | `"list_directory"` |

**参数 Schema：**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `path` | `string` | 是 | — | 目录路径 |
| `recursive` | `boolean` | 否 | `false` | 是否递归列出子目录 |

```python
result = await list_dir_tool.execute(path="src/", recursive=True)
```

---

#### RunCommandTool

```
soul_agent.tools.builtin.RunCommandTool
```

执行 shell 命令。内置危险命令拦截机制。**输出限制：10000 字符。**

| 属性 | 值 |
|------|----|
| `name` | `"run_command"` |

**参数 Schema：**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `command` | `string` | 是 | — | 要执行的命令 |
| `timeout` | `number` | 否 | — | 超时时间（秒） |

#### `__init__(shell_config)`

| 参数 | 类型 | 说明 |
|------|------|------|
| `shell_config` | `ShellConfig` | Shell 配置，包含被拦截的命令列表等 |

```python
from soul_agent.tools.builtin import RunCommandTool

cmd_tool = RunCommandTool(shell_config=shell_config)
result = await cmd_tool.execute(command="ls -la", timeout=30)
```

> **安全提示：** 内置命令黑名单会拦截危险操作（如 `rm -rf /`）。具体拦截规则由 `ShellConfig` 配置。

---

#### WebRequestTool

```
soul_agent.tools.builtin.WebRequestTool
```

发送 HTTP 请求。基于 `urllib` 实现。**响应内容限制：10000 字符。**

| 属性 | 值 |
|------|----|
| `name` | `"web_request"` |

**参数 Schema：**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `url` | `string` | 是 | — | 请求 URL |
| `method` | `string` | 否 | `"GET"` | HTTP 方法（`GET` 或 `POST`） |
| `headers` | `object` | 否 | — | 请求头字典 |
| `body` | `string` | 否 | — | 请求体内容 |

```python
result = await web_tool.execute(
    url="https://api.example.com/data",
    method="POST",
    headers={"Content-Type": "application/json"},
    body='{"key": "value"}',
)
```

---

#### SearchFilesTool

```
soul_agent.tools.builtin.SearchFilesTool
```

在文件内容中搜索匹配模式。**最大返回 100 条结果。**

| 属性 | 值 |
|------|----|
| `name` | `"search_files"` |

**参数 Schema：**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `pattern` | `string` | 是 | — | 搜索模式（正则表达式或字符串） |
| `path` | `string` | 否 | `"."` | 搜索起始路径 |
| `file_pattern` | `string` | 否 | `"*"` | 文件名匹配模式（glob） |

```python
result = await search_tool.execute(
    pattern="def main",
    path="src/",
    file_pattern="*.py",
)
```

---

## soul_agent.llm — 大语言模型模块

### LLMClient

```
soul_agent.llm.client.LLMClient
```

LLM 客户端，对底层 Provider 的统一封装。

#### `__init__(config: LLMConfig)`

| 参数 | 类型 | 说明 |
|------|------|------|
| `config` | `LLMConfig` | LLM 配置，包含模型名称、API 密钥、基础 URL 等 |

```python
from soul_agent.llm.client import LLMClient

client = LLMClient(config=llm_config)
```

---

#### `async chat(messages, tools=None, stream=False) -> LLMResponse`

发送聊天请求并获取回复。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `messages` | `list[dict]` | — | 消息列表 |
| `tools` | `list[dict] \| None` | `None` | 工具 schema 列表（OpenAI Function Calling 格式） |
| `stream` | `bool` | `False` | 是否启用流式输出 |

**返回值：** `LLMResponse`

```python
response = await client.chat(
    messages=[
        {"role": "system", "content": "你是一个助手"},
        {"role": "user", "content": "你好"},
    ],
    tools=registry.schemas,
    stream=True,
)

print(response.content)
if response.has_tool_calls:
    for tc in response.tool_calls:
        print(f"工具调用: {tc['function']['name']}")
```

---

### LLMResponse

```
soul_agent.llm.providers.openai.LLMResponse
```

LLM 响应对象。

**属性：**

| 属性 | 类型 | 说明 |
|------|------|------|
| `content` | `str` | 回复文本内容 |
| `tool_calls` | `list[dict]` | 工具调用列表 |
| `usage` | `dict` | token 使用统计 |

#### `has_tool_calls -> bool`

只读属性。判断回复中是否包含工具调用。

```python
response: LLMResponse

if response.has_tool_calls:
    print(f"需要调用 {len(response.tool_calls)} 个工具")
else:
    print(f"回复: {response.content}")

# usage 示例
print(f"输入 tokens: {response.usage.get('prompt_tokens')}")
print(f"输出 tokens: {response.usage.get('completion_tokens')}")
```

---

### OpenAIProvider

```
soul_agent.llm.providers.openai.OpenAIProvider
```

OpenAI 兼容的 LLM 提供者，使用 `AsyncOpenAI` 客户端。

#### `__init__(config: LLMConfig)`

根据配置创建 `AsyncOpenAI` 客户端实例。

| 参数 | 类型 | 说明 |
|------|------|------|
| `config` | `LLMConfig` | LLM 配置 |

```python
from soul_agent.llm.providers.openai import OpenAIProvider

provider = OpenAIProvider(config=llm_config)
```

---

#### `async chat(messages, tools=None, stream=True) -> LLMResponse`

发送聊天补全请求。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `messages` | `list[dict]` | — | 消息列表 |
| `tools` | `list[dict] \| None` | `None` | 工具定义 |
| `stream` | `bool` | `True` | 是否流式输出 |

**返回值：** `LLMResponse`

---

### LocalProvider

```
soul_agent.llm.providers.local.LocalProvider(OpenAIProvider)
```

本地模型提供者，继承自 `OpenAIProvider`。默认将 `base_url` 指向本地 Ollama 服务。

如果配置中未设置 `base_url`，自动使用 `http://localhost:11434/v1`。

```python
from soul_agent.llm.providers.local import LocalProvider

# 连接本地 Ollama
local = LocalProvider(config=LLMConfig(model="qwen2.5:7b"))
```

---

## soul_agent.config — 配置模块

```
soul_agent.config.settings
```

基于 Pydantic BaseModel 的分层配置系统。支持配置文件加载、环境变量解析和深度合并。

### 配置数据类

所有配置类均继承自 `pydantic.BaseModel`。

#### LLMConfig

| 字段 | 类型 | 说明 |
|------|------|------|
| `model` | `str` | 模型名称 |
| `api_key` | `str` | API 密钥 |
| `base_url` | `str \| None` | API 基础 URL |
| `temperature` | `float` | 采样温度 |
| `max_tokens` | `int` | 最大输出 token 数 |

#### AgentConfig

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `max_iterations` | `int` | `30` | ReAct 循环最大迭代次数 |
| `system_prompt_path` | `str \| None` | `None` | 自定义系统提示词文件路径 |
| `planning_enabled` | `bool` | `True` | 是否启用自动任务规划 |
| `planning_complexity_threshold` | `int` | `2` | 触发规划的复杂度阈值（0-10） |

#### MemoryConfig

| 字段 | 类型 | 说明 |
|------|------|------|
| `enabled` | `bool` | 是否启用记忆 |
| `db_path` | `str` | SQLite 数据库路径 |
| `vector_db_path` | `str \| None` | ChromaDB 路径 |
| `importance_threshold` | `float` | 记忆重要性阈值 |

#### ShellConfig

| 字段 | 类型 | 说明 |
|------|------|------|
| `blocked_commands` | `list[str]` | 被拦截的危险命令列表 |

#### ToolsConfig

| 字段 | 类型 | 说明 |
|------|------|------|
| `enabled` | `list[str]` | 启用的工具名称列表 |

#### UIConfig

| 字段 | 类型 | 说明 |
|------|------|------|
| `theme` | `str` | 主题名称 |

#### AppConfig

顶层应用配置，包含所有子配置。

| 字段 | 类型 | 说明 |
|------|------|------|
| `llm` | `LLMConfig` | LLM 配置 |
| `agent` | `AgentConfig` | Agent 配置 |
| `memory` | `MemoryConfig` | 记忆配置 |
| `shell` | `ShellConfig` | Shell 配置 |
| `tools` | `ToolsConfig` | 工具配置 |
| `ui` | `UIConfig` | 界面配置 |

```python
from soul_agent.config.settings import AppConfig, LLMConfig

config = AppConfig(
    llm=LLMConfig(model="gpt-4", api_key="sk-xxx"),
)
```

---

### load_config

#### `load_config(config_path=None) -> AppConfig`

加载配置文件并返回 `AppConfig` 实例。

搜索顺序：
1. 参数指定的路径
2. 当前目录下的 `soul_agent.yaml` / `soul_agent.yml`
3. 使用默认配置

支持环境变量替换（`${ENV_VAR}` 语法）和配置深度合并。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `config_path` | `str \| None` | `None` | 配置文件路径 |

**返回值：** `AppConfig`

```python
from soul_agent.config.settings import load_config

# 自动搜索配置文件
config = load_config()

# 指定配置文件
config = load_config("config/production.yaml")
```

---

### 辅助函数

#### `_deep_merge(base, override) -> dict`

深度合并两个字典。`override` 中的值覆盖 `base` 中的同名键，嵌套字典递归合并。

| 参数 | 类型 | 说明 |
|------|------|------|
| `base` | `dict` | 基础字典 |
| `override` | `dict` | 覆盖字典 |

**返回值：** `dict` — 合并后的字典。

---

#### `_resolve_env_vars(config) -> dict`

递归解析配置中的环境变量引用，将 `${VAR_NAME}` 替换为对应环境变量的值。

| 参数 | 类型 | 说明 |
|------|------|------|
| `config` | `dict` | 配置字典 |

**返回值：** `dict` — 解析后的配置字典。

```yaml
# soul_agent.yaml
llm:
  api_key: ${OPENAI_API_KEY}
  model: gpt-4
```

---

## soul_agent.ui — 用户界面模块

### Renderer

```
soul_agent.ui.renderer.Renderer
```

基于 [Rich](https://github.com/Textualize/rich) 库的终端渲染器，负责格式化输出 Agent 的各类信息。

#### `__init__(theme_name="monokai")`

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `theme_name` | `str` | `"monokai"` | 主题名称，可选 `"monokai"`、`"dracula"`、`"default"` |

```python
from soul_agent.ui.renderer import Renderer

renderer = Renderer(theme_name="dracula")
```

---

#### `render_welcome()`

渲染欢迎信息面板。

```python
renderer.render_welcome()
```

---

#### `render_assistant(text)`

以 Markdown 格式渲染助手回复。`●` 圆点与正文首行同行，续行自动缩进 2 格对齐。

| 参数 | 类型 | 说明 |
|------|------|------|
| `text` | `str` | 助手回复文本（支持 Markdown） |

```python
renderer.render_assistant("项目结构如下：\n```\nsrc/\n├── main.py\n└── utils.py\n```")
```

---

#### `render_tool_call(tool_name, args)`

渲染工具调用信息。将工具行加入待定列表，在底部 Live 区域显示闪烁的白色圆点。

| 参数 | 类型 | 说明 |
|------|------|------|
| `tool_name` | `str` | 工具名称 |
| `args` | `dict` | 工具参数 |

```python
renderer.render_tool_call("read_file", {"path": "config.yaml"})
```

**显示效果**：执行中圆点闪烁（白色明暗交替），等待 `render_tool_result` 定色输出。

---

#### `render_tool_result(tool_name, success, output, error=None)`

渲染工具执行结果。从待定列表取出工具行，以绿点（成功）或红点（失败）定格输出，紧接 `⎿` 连接符显示结果摘要。

| 参数 | 类型 | 说明 |
|------|------|------|
| `tool_name` | `str` | 工具名称 |
| `success` | `bool` | 是否执行成功 |
| `output` | `str` | 输出内容 |
| `error` | `str \| None` | 错误信息，成功时为 `None` |

```python
renderer.render_tool_result("write_file", True, "已写入文件: output.txt")
renderer.render_tool_result("read_file", False, "", "文件不存在: /bad/path")
```

**显示效果**：
- 成功：`● read_file(config.yaml)` 绿色圆点 + `⎿ 读取 50 行`
- 失败：`● read_file(bad.txt)` 红色圆点 + `⎿ 错误: 文件不存在`

---

#### `render_plan_steps(tracker)`

使用 Rich Live 组件在终端底部原位刷新计划执行进度面板。

| 参数 | 类型 | 说明 |
|------|------|------|
| `tracker` | `PlanTracker` | 计划进度追踪器实例 |

```python
renderer.render_plan_steps(plan_tracker)
```

**效果：** 在终端底部显示 `执行计划` 面板，✓ 标记已完成步骤，· 标记待完成步骤，每步显示工具名。任务执行完成后由 `clear_plan_live()` 收起。

---

#### `clear_plan_live()`

停止计划面板的 Live 显示，恢复终端正常滚动。在每轮对话开始前和 Agent 回复前调用。

```python
renderer.clear_plan_live()
```

---

#### `render_error(message)`

渲染错误信息。

| 参数 | 类型 | 说明 |
|------|------|------|
| `message` | `str` | 错误信息 |

```python
renderer.render_error("无法连接到 LLM 服务")
```

---

#### `render_info(message)`

渲染提示信息。

| 参数 | 类型 | 说明 |
|------|------|------|
| `message` | `str` | 提示信息 |

```python
renderer.render_info("记忆系统已初始化")
```

---

#### `render_memory_list(memories)`

以 Rich Table 表格渲染记忆列表。

| 参数 | 类型 | 说明 |
|------|------|------|
| `memories` | `list[MemoryEntry]` | 记忆条目列表 |

```python
memories = await mm.list_all()
renderer.render_memory_list(memories)
```

---

#### `render_conversation_list(conversations)`

以 Rich Table 表格渲染历史会话列表。

| 参数 | 类型 | 说明 |
|------|------|------|
| `conversations` | `list[ConversationEntry]` | 会话条目列表 |

```python
conversations = await agent.memory.list_conversations()
renderer.render_conversation_list(conversations)
```

---

#### `render_help()`

渲染帮助信息，显示所有可用命令（含 `/history`、`/name`）。

```python
renderer.render_help()
```

---

### InputHandler

```
soul_agent.ui.input.InputHandler
```

交互式输入处理器，基于 `prompt_toolkit`，支持历史记录与自动补全。

#### `__init__()`

初始化输入处理器。使用 `data/.input_history` 作为历史记录文件，并启用 `AutoSuggestFromHistory` 自动建议。

```python
from soul_agent.ui.input import InputHandler

handler = InputHandler()
```

---

#### `async get_input(prompt_text=">>> ") -> str`

异步获取用户输入。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `prompt_text` | `str` | `">>> "` | 输入提示符 |

**返回值：** `str` — 用户输入的文本。

```python
user_input = await handler.get_input("Soul> ")
```

---

### 主题系统

```
soul_agent.ui.themes
```

内置终端配色方案。

#### `THEMES`

预定义主题字典，包含以下主题：

| 主题名 | 说明 |
|--------|------|
| `"monokai"` | Monokai 风格配色 |
| `"dracula"` | Dracula 风格配色 |
| `"default"` | 默认配色方案 |

每个主题包含以下颜色键：

- `primary` — 主色调
- `secondary` — 辅助色调
- `accent` — 强调色
- `error` — 错误色
- `success` — 成功色
- `warning` — 警告色
- `info` — 信息色

---

#### `get_theme(name) -> dict`

获取指定名称的主题配置。

| 参数 | 类型 | 说明 |
|------|------|------|
| `name` | `str` | 主题名称 |

**返回值：** `dict` — 主题颜色配置字典。

```python
from soul_agent.ui.themes import get_theme

theme = get_theme("dracula")
print(theme["primary"])  # 颜色值
```

---

## soul_agent.app — 应用入口

```
soul_agent.app
```

应用层入口函数，提供快速启动 Agent 的便捷方法。

#### `async create_agent(config=None) -> Agent`

创建并初始化一个完整的 Agent 实例，包括配置加载、LLM 客户端创建、记忆系统初始化、工具注册、首会话预创建及持久化回调注入等全部流程。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `config` | `AppConfig \| None` | `None` | 应用配置；`None` 时自动加载 |

**返回值：** `Agent` — 就绪的 Agent 实例。

```python
from soul_agent.app import create_agent

agent = await create_agent()
reply = await agent.run("你好")
```

---

#### `async run_chat()`

启动交互式聊天模式。循环读取用户输入并调用 Agent 生成回复，直到用户退出。

```python
from soul_agent.app import run_chat

await run_chat()
```

---

#### `async run_ask(message)`

单次问答模式。发送一条消息并输出回复，不进入交互循环。

| 参数 | 类型 | 说明 |
|------|------|------|
| `message` | `str` | 用户消息 |

```python
from soul_agent.app import run_ask

await run_ask("列出当前目录的所有文件")
```

---

#### `async run_memory()`

进入记忆管理模式。可查看、搜索、删除记忆条目。

```python
from soul_agent.app import run_memory

await run_memory()
```

---

## soul_agent.utils — 工具函数

### 日志

```
soul_agent.utils.logger
```

#### `setup_logger(name, level, log_file) -> Logger`

创建并配置日志记录器。

| 参数 | 类型 | 说明 |
|------|------|------|
| `name` | `str` | 日志器名称 |
| `level` | `str \| int` | 日志级别，如 `"DEBUG"`、`"INFO"` |
| `log_file` | `str \| None` | 日志文件路径；`None` 仅输出到控制台 |

**返回值：** `logging.Logger`

```python
from soul_agent.utils.logger import setup_logger

log = setup_logger("my_module", level="DEBUG", log_file="logs/app.log")
log.info("模块已初始化")
```

---

#### `logger`

模块级预配置日志实例，可直接导入使用。

```python
from soul_agent.utils.logger import logger

logger.info("应用启动")
logger.error("发生错误", exc_info=True)
```

---

### 异常类

```
soul_agent.utils.exceptions
```

Soul-Agent 自定义异常层级，所有异常均继承自 `SoulAgentError`。

| 异常类 | 父类 | 说明 |
|--------|------|------|
| `SoulAgentError` | `Exception` | 基础异常类 |
| `ConfigError` | `SoulAgentError` | 配置相关错误（文件缺失、格式错误等） |
| `LLMError` | `SoulAgentError` | LLM 调用错误（API 失败、超时等） |
| `ToolError` | `SoulAgentError` | 工具执行错误 |
| `MemoryError` | `SoulAgentError` | 记忆系统错误（数据库、向量存储等） |

```python
from soul_agent.utils.exceptions import LLMError, ToolError

try:
    response = await client.chat(messages)
except LLMError as e:
    print(f"LLM 调用失败: {e}")

try:
    result = await executor.execute(tool_call)
except ToolError as e:
    print(f"工具执行失败: {e}")
```

---

## 附录：快速入门示例

以下是一个完整的使用示例，展示如何组装并运行 Soul-Agent：

```python
import asyncio
from soul_agent.app import create_agent

async def main():
    # 方式一：使用 create_agent 快速创建
    agent = await create_agent()
    reply = await agent.run("帮我查看当前目录下的文件")
    print(reply)

    # 方式二：手动组装
    from soul_agent.config.settings import load_config
    from soul_agent.llm.client import LLMClient
    from soul_agent.memory.manager import MemoryManager
    from soul_agent.tools.registry import ToolRegistry
    from soul_agent.tools.executor import ToolExecutor
    from soul_agent.tools.builtin import ReadFileTool, WriteFileTool
    from soul_agent.core.agent import Agent

    config = load_config()

    llm_client = LLMClient(config.llm)

    memory_manager = MemoryManager(config.memory, llm_client)
    await memory_manager.initialize()

    registry = ToolRegistry()
    registry.register(ReadFileTool())
    registry.register(WriteFileTool())
    executor = ToolExecutor(registry)

    agent = Agent(
        config=config.agent,
        llm_client=llm_client,
        memory_manager=memory_manager,
        tool_registry=registry,
        tool_executor=executor,
    )

    agent.set_callbacks(
        on_tool_call=lambda name, args: print(f"🔧 {name}({args})"),
        on_tool_result=lambda name, success, output, error: print(f"{'✓' if success else '✗'} {name}"),
    )

    reply = await agent.run("读取 README.md 文件")
    print(reply)

    agent.reset()

asyncio.run(main())
```

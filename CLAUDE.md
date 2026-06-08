# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 常用命令

```bash
# 安装（推荐使用 uv）
uv venv
.venv\Scripts\activate   # Windows
uv pip install -e ".[dev]"

# 运行
soul-agent                 # 交互式对话（默认）
soul-agent chat            # 显式进入聊天模式
soul-agent ask "问题"      # 单次提问
soul-agent memory          # 查看记忆列表
soul-agent config          # 查看当前配置

# 测试
pytest tests/ -v                              # 全部 42 个测试
pytest tests/test_agent.py -v                 # Agent 核心（10 个）
pytest tests/test_memory.py -v                # 记忆系统（14 个）
pytest tests/test_tools.py -v                 # 工具系统（18 个）

# 代码检查
ruff check .
```

## 架构总览

项目采用分层架构，依赖自顶向下：**CLI → UI → Core → (Memory / Tools / LLM) → Config / Utils**

### 启动与组装流程（`app.py`）

`app.py` 的 `create_agent()` 是核心组装工厂，按顺序创建所有组件并注入 Agent：

1. `load_config()` — 4 级优先级加载配置（见下文）
2. `LLMClient(config.llm)` — 根据 `provider` 字段选择 OpenAIProvider 或 LocalProvider
3. `MemoryManager(config.memory, llm_client)` — 若启用，初始化 SQLite + ChromaDB
4. `ToolRegistry` → `register_builtin_tools()` → `ToolExecutor`
5. `Agent(config, llm_client, memory_manager, tool_registry, tool_executor)` — 组装所有依赖

### Agent 主循环（`core/agent.py`）

Agent 实现 **ReAct（Reasoning + Acting）** 模式，每次 `run(user_input)` 执行：

1. 调用 `MemoryManager.retrieve()` 检索相关记忆
2. 构建系统提示词（注入工具描述 + 记忆上下文）
3. 通过 `Conversation.build_messages()` 构建消息列表
4. **ReAct 循环**（最多 `max_iterations` 轮，默认 10）：
   - 调用 LLM，附带工具 schema
   - 若返回 `tool_calls`：格式化消息 → `ToolExecutor.execute_batch()` → 追加结果，继续循环
   - 若返回纯文本：退出循环
5. 调用 `MemoryManager.process_turn()` 异步提取记忆（LLM 判断是否需要记忆）
6. `Conversation.add_turn()` 更新对话历史

### 记忆系统（`memory/`）

核心差异化功能，双存储架构：

| 组件 | 存储 | 用途 |
|------|------|------|
| `ShortTermMemory` | 内存列表 | 会话内消息（50 条上限，FIFO） |
| `LongTermMemory` | SQLite | 跨会话持久化（CRUD） |
| `MemoryRetriever` | ChromaDB + 关键词 | 混合检索：语义相似度 50% + 重要性 30% + 时间衰减 20%（半衰期 72h） |
| `ConversationSummarizer` | LLM 调用 | 对话摘要生成 |

`MemoryManager` 是统一入口，协调上述所有组件。每次对话轮次后，由 LLM 通过 `EXTRACT_MEMORIES_PROMPT` 判断是否提取记忆，低于 `importance_threshold`（默认 0.3）的记忆不存储。ChromaDB 不可用时自动降级为关键词搜索。

### LLM 适配层（`llm/`）

- `LLMClient` 是门面，根据 `provider` 配置分发到具体 Provider
- `OpenAIProvider` — 基于 `openai` SDK 的 AsyncOpenAI，支持普通和流式聊天
- `LocalProvider(OpenAIProvider)` — 仅覆写 `base_url` 为 `http://localhost:11434/v1`，用于 Ollama
- Provider 返回统一的 `LLMResponse` 对象（含 `content`、`tool_calls`、`has_tool_calls` 属性）

### 配置加载优先级（`config/settings.py`）

从低到高：`defaults.py` 硬编码字典 → `config/default.yaml` → `${VAR}` 环境变量解析 → `OPENAI_API_KEY` / `OPENAI_BASE_URL` / `SOUL_AGENT_MODEL` 直接覆盖

配置通过 Pydantic v2 模型验证：`LLMConfig`、`AgentConfig`、`MemoryConfig`、`ShellConfig`、`ToolsConfig`、`UIConfig`，全部聚合到 `AppConfig`。

### 工具系统（`tools/`）

- `Tool` 是抽象基类，定义 `name`、`description`、`parameters`（JSON Schema）、`execute(**kwargs) → ToolResult`
- `ToolRegistry` 按名称存储 Tool 实例，提供 `schemas`（给 LLM）和 `get_descriptions()`（给系统提示词）
- `ToolExecutor` 负责单个/批量执行，从 Registry 查找工具、调用 `execute()`、格式化为 LLM 可读的消息
- 6 个内置工具：`read_file`、`write_file`、`list_directory`、`run_command`（危险命令黑名单 + 超时）、`web_request`（GET/POST，响应截断 10KB）、`search_files`（glob + 行匹配）

### 异常体系（`utils/__init__.py`）

```
SoulAgentError（基础）
├── ConfigError    — 配置错误
├── LLMError       — LLM 调用错误
├── ToolError      — 工具执行错误
└── MemoryError    — 记忆系统错误
```

### 终端 UI（`ui/`）

- `Renderer` — 基于 Rich 的 Markdown 渲染、面板、表格、欢迎界面、工具调用展示
- `InputHandler` — 基于 prompt_toolkit，带历史记录和自动补全
- `themes.py` — 3 套主题：monokai、dracula、default

### 对话管理（`core/conversation.py`）

- `Conversation` 维护消息列表，`add_turn(user, assistant)` 追加一轮对话
- 20 轮历史上限，超出自动裁剪
- `ContextManager` 提供启发式 token 估算和消息裁剪（始终保留 system prompt + 最后一条用户消息）

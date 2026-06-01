# Soul-agent: 更懂你的通用Agent — 开发设计方案

## 1. 项目概述

### 1.1 项目定位

Soul-agent 是一个基于大语言模型的终端智能助手，通过命令行交互完成用户的各类任务。其核心特色是**长期记忆系统**——能够记住用户的偏好、历史对话和关键信息，实现"越用越懂你"的个性化体验。

### 1.2 核心功能

| 功能模块 | 描述 |
|---------|------|
| 对话聊天 | 基于LLM的自然语言对话，支持多轮上下文 |
| 工具调用 | 执行本地命令、文件操作、网络请求等 |
| 长期记忆 | 持久化存储用户信息与对话摘要，智能检索 |
| 文档读写 | 读取、生成、编辑各类文档 |
| 任务规划 | 将复杂任务拆解为可执行步骤 |

### 1.3 技术选型

| 组件 | 技术方案 | 理由 |
|------|---------|------|
| 编程语言 | Python 3.11+ | 生态丰富，LLM库支持好 |
| LLM接口 | OpenAI兼容API（支持多模型切换） | 通用性强，可接入多种模型 |
| 终端UI | Rich + Prompt Toolkit | 美观的终端渲染和输入体验 |
| 记忆存储 | SQLite + ChromaDB | 结构化数据+向量检索 |
| 配置管理 | YAML | 可读性好，易于编辑 |
| 包管理 | Poetry | 依赖管理规范 |
| 测试框架 | Pytest | Python标准测试方案 |

---

## 2. 系统架构

### 2.1 整体架构图

```
┌─────────────────────────────────────────────────────┐
│                    用户终端 (CLI)                      │
├─────────────────────────────────────────────────────┤
│                  交互层 (Interface)                    │
│         Rich渲染 | Prompt Toolkit输入 | 命令解析       │
├─────────────────────────────────────────────────────┤
│                  核心层 (Core)                         │
│    Agent引擎 | 对话管理 | 任务规划 | 上下文管理         │
├──────────┬──────────┬───────────┬───────────────────┤
│ 记忆系统  │ 工具系统  │  LLM适配  │    配置系统        │
│ Memory   │  Tools   │ LLM Layer │    Config         │
├──────────┴──────────┴───────────┴───────────────────┤
│                  存储层 (Storage)                      │
│         SQLite | ChromaDB | 本地文件系统               │
└─────────────────────────────────────────────────────┘
```

### 2.2 模块职责

- **交互层**：处理用户输入输出，命令解析，终端渲染
- **核心层**：Agent决策循环，对话状态管理，任务编排
- **记忆系统**：长期记忆的存储、检索、更新、遗忘
- **工具系统**：本地工具注册、调用、结果处理
- **LLM适配层**：统一的模型调用接口，支持多provider
- **配置系统**：用户配置、模型配置、工具配置管理

---

## 3. 目录结构

```
Soul-agent/
├── soul_agent/                # 主包
│   ├── __init__.py
│   ├── main.py               # 入口文件
│   ├── cli.py                # CLI命令定义
│   ├── core/                 # 核心模块
│   │   ├── __init__.py
│   │   ├── agent.py          # Agent主循环
│   │   ├── conversation.py   # 对话管理
│   │   ├── planner.py        # 任务规划器
│   │   └── context.py        # 上下文窗口管理
│   ├── memory/               # 记忆系统
│   │   ├── __init__.py
│   │   ├── manager.py        # 记忆管理器（统一入口）
│   │   ├── short_term.py     # 短期记忆（会话内）
│   │   ├── long_term.py      # 长期记忆（跨会话）
│   │   ├── retriever.py      # 记忆检索（向量+关键词）
│   │   └── summarizer.py     # 对话摘要生成
│   ├── tools/                # 工具系统
│   │   ├── __init__.py
│   │   ├── registry.py       # 工具注册中心
│   │   ├── executor.py       # 工具执行器
│   │   ├── builtin/          # 内置工具
│   │   │   ├── __init__.py
│   │   │   ├── file_ops.py   # 文件读写
│   │   │   ├── shell.py      # 命令执行
│   │   │   ├── web.py        # 网络请求
│   │   │   └── search.py     # 本地搜索
│   │   └── base.py           # 工具基类
│   ├── llm/                  # LLM适配层
│   │   ├── __init__.py
│   │   ├── client.py         # 统一客户端
│   │   ├── providers/        # 模型提供商
│   │   │   ├── __init__.py
│   │   │   ├── openai.py     # OpenAI/兼容API
│   │   │   └── local.py      # 本地模型(Ollama等)
│   │   └── prompts.py        # 系统提示词管理
│   ├── ui/                   # 终端UI
│   │   ├── __init__.py
│   │   ├── renderer.py       # Rich渲染器
│   │   ├── input.py          # 输入处理
│   │   └── themes.py         # 主题配置
│   ├── config/               # 配置模块
│   │   ├── __init__.py
│   │   ├── settings.py       # 配置加载与验证
│   │   └── defaults.py       # 默认配置
│   └── utils/                # 工具函数
│       ├── __init__.py
│       ├── logger.py         # 日志
│       └── exceptions.py     # 自定义异常
├── data/                     # 运行时数据（gitignore）
│   ├── memory.db             # SQLite记忆数据库
│   ├── chroma/               # 向量数据库
│   └── logs/                 # 日志文件
├── config/                   # 配置文件
│   └── default.yaml          # 默认配置模板
├── tests/                    # 测试
│   ├── __init__.py
│   ├── test_agent.py
│   ├── test_memory.py
│   └── test_tools.py
├── docs/                     # 文档
│   └── development-design.md # 本文件
├── pyproject.toml            # 项目配置
├── README.md
├── .gitignore
└── .env.example              # 环境变量模板
```

---

## 4. 核心模块详细设计

### 4.1 Agent核心循环

Agent采用 ReAct (Reasoning + Acting) 模式，循环执行：观察→思考→行动→观察。

```python
# soul_agent/core/agent.py

class Agent:
    """Agent主循环，协调各模块完成用户任务"""

    def __init__(self, config, llm_client, memory_manager, tool_registry):
        self.config = config
        self.llm = llm_client
        self.memory = memory_manager
        self.tools = tool_registry
        self.conversation = Conversation()

    async def run(self, user_input: str) -> str:
        """处理一次用户输入，返回最终响应"""
        # 1. 检索相关记忆
        relevant_memories = await self.memory.retrieve(user_input)

        # 2. 构建消息（含记忆上下文）
        messages = self.conversation.build_messages(
            user_input=user_input,
            memories=relevant_memories
        )

        # 3. Agent循环（最多N轮工具调用）
        for _ in range(self.config.max_iterations):
            response = await self.llm.chat(messages, tools=self.tools.schemas)

            if response.has_tool_calls:
                # 执行工具并将结果加入消息
                results = await self.tools.execute_batch(response.tool_calls)
                messages.extend(results)
            else:
                # 无工具调用，返回最终回复
                break

        final_reply = response.content

        # 4. 更新记忆
        await self.memory.process_turn(user_input, final_reply)

        # 5. 更新对话历史
        self.conversation.add_turn(user_input, final_reply)

        return final_reply
```

### 4.2 记忆系统

记忆系统是本项目的核心差异化功能，分为三层：

```
┌─────────────────────────────────────┐
│          记忆管理器 (Manager)         │
├───────────┬───────────┬─────────────┤
│  短期记忆   │  长期记忆   │  记忆检索    │
│ (会话内)   │ (跨会话)   │ (智能召回)   │
├───────────┴───────────┴─────────────┤
│    SQLite (结构化) + ChromaDB (向量)   │
└─────────────────────────────────────┘
```

#### 4.2.1 记忆数据模型

```python
# soul_agent/memory/long_term.py

@dataclass
class MemoryEntry:
    id: str                    # UUID
    content: str               # 记忆内容
    memory_type: str           # 类型: fact/preference/event/summary
    importance: float          # 重要性评分 0-1
    created_at: datetime
    last_accessed: datetime
    access_count: int          # 访问次数
    metadata: dict             # 附加信息（来源对话ID等）
```

#### 4.2.2 记忆类型

| 类型 | 说明 | 示例 |
|------|------|------|
| fact | 用户相关事实 | "用户是计算机专业大三学生" |
| preference | 用户偏好 | "喜欢简洁的代码风格" |
| event | 重要事件 | "2024-03-15完成了项目A的部署" |
| summary | 对话摘要 | "讨论了数据库选型，最终选择PostgreSQL" |

#### 4.2.3 智能记忆检索

```python
# soul_agent/memory/retriever.py

class MemoryRetriever:
    """混合检索：向量相似度 + 时间衰减 + 重要性加权"""

    async def retrieve(self, query: str, top_k: int = 5) -> list[MemoryEntry]:
        # 1. 向量相似度检索
        vector_results = await self.vector_search(query, top_k=top_k * 2)

        # 2. 计算综合得分
        scored = []
        for memory in vector_results:
            score = (
                memory.similarity * 0.5 +          # 语义相关性
                memory.importance * 0.3 +           # 重要性
                self.recency_score(memory) * 0.2    # 时间衰减
            )
            scored.append((memory, score))

        # 3. 排序返回top_k
        scored.sort(key=lambda x: x[1], reverse=True)
        return [m for m, _ in scored[:top_k]]

    def recency_score(self, memory: MemoryEntry) -> float:
        """时间衰减函数：越近的记忆分数越高"""
        hours_ago = (datetime.now() - memory.last_accessed).total_seconds() / 3600
        return math.exp(-0.01 * hours_ago)
```

#### 4.2.4 记忆写入决策

不是所有对话都需要记忆，由LLM判断是否需要存储：

```python
# soul_agent/memory/manager.py

class MemoryManager:
    async def process_turn(self, user_input: str, assistant_reply: str):
        """处理一轮对话，决定是否生成记忆"""
        # 让LLM判断是否包含值得记忆的信息
        decision = await self.llm.chat([
            {"role": "system", "content": MEMORY_EXTRACTION_PROMPT},
            {"role": "user", "content": f"用户: {user_input}\n助手: {assistant_reply}"}
        ])

        if decision.should_memorize:
            for item in decision.memories:
                await self.long_term.store(item)
```

### 4.3 工具系统

采用注册制，工具通过装饰器声明，自动生成schema供LLM调用。

```python
# soul_agent/tools/base.py

class Tool(ABC):
    """工具基类"""
    name: str
    description: str
    parameters: dict  # JSON Schema格式

    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        pass

@dataclass
class ToolResult:
    success: bool
    output: str
    error: str | None = None
```

```python
# soul_agent/tools/builtin/file_ops.py

class ReadFileTool(Tool):
    name = "read_file"
    description = "读取指定路径的文件内容"
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "文件路径"},
            "encoding": {"type": "string", "default": "utf-8"}
        },
        "required": ["path"]
    }

    async def execute(self, path: str, encoding: str = "utf-8") -> ToolResult:
        try:
            content = Path(path).read_text(encoding=encoding)
            return ToolResult(success=True, output=content)
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
```

#### 4.3.1 内置工具清单

| 工具名 | 功能 | 参数 |
|--------|------|------|
| read_file | 读取文件 | path, encoding |
| write_file | 写入文件 | path, content, encoding |
| list_directory | 列出目录内容 | path, recursive |
| run_command | 执行shell命令 | command, timeout |
| web_request | HTTP请求 | url, method, headers, body |
| search_files | 搜索文件内容 | pattern, directory, file_type |

### 4.4 LLM适配层

```python
# soul_agent/llm/client.py

class LLMClient:
    """统一的LLM调用接口"""

    def __init__(self, config: LLMConfig):
        self.provider = self._init_provider(config)

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        stream: bool = True
    ) -> LLMResponse:
        """发送对话请求，支持流式输出"""
        return await self.provider.chat(messages, tools=tools, stream=stream)

    def _init_provider(self, config):
        providers = {
            "openai": OpenAIProvider,
            "local": LocalProvider,
        }
        return providers[config.provider](config)
```

### 4.5 CLI交互层

```python
# soul_agent/cli.py

import click
from rich.console import Console

@click.group()
def cli():
    """Soul-agent: 更懂你的通用Agent"""
    pass

@cli.command()
def chat():
    """启动交互式对话"""
    pass

@cli.command()
@click.argument("message")
def ask(message: str):
    """单次提问模式"""
    pass

@cli.command()
def memory():
    """查看/管理记忆"""
    pass

@cli.command()
def config():
    """配置管理"""
    pass
```

---

## 5. 配置文件设计

```yaml
# config/default.yaml

llm:
  provider: "openai"           # openai / local
  model: "gpt-4o-mini"        # 模型名称
  api_key: "${OPENAI_API_KEY}" # 从环境变量读取
  base_url: null               # 自定义API地址（兼容API用）
  temperature: 0.7
  max_tokens: 4096

agent:
  max_iterations: 10           # 单次任务最大工具调用轮数
  system_prompt_path: null     # 自定义系统提示词文件

memory:
  enabled: true
  db_path: "./data/memory.db"
  vector_db_path: "./data/chroma"
  max_memories_per_query: 5    # 每次检索返回的记忆数
  importance_threshold: 0.3    # 低于此分数的记忆不存储
  embedding_model: "text-embedding-3-small"

tools:
  enabled:
    - read_file
    - write_file
    - list_directory
    - run_command
    - web_request
    - search_files
  shell:
    timeout: 30                # 命令执行超时（秒）
    blocked_commands:           # 禁止执行的危险命令
      - "rm -rf /"
      - "format"

ui:
  theme: "monokai"             # 终端主题
  stream: true                 # 流式输出
  show_thinking: false         # 是否显示思考过程
  language: "zh"               # 界面语言
```

---

## 6. 数据库设计

### 6.1 SQLite表结构

```sql
-- 对话历史
CREATE TABLE conversations (
    id TEXT PRIMARY KEY,
    title TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 消息记录
CREATE TABLE messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT REFERENCES conversations(id),
    role TEXT NOT NULL,          -- user/assistant/system/tool
    content TEXT NOT NULL,
    tool_calls TEXT,             -- JSON格式的工具调用
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 长期记忆
CREATE TABLE memories (
    id TEXT PRIMARY KEY,
    content TEXT NOT NULL,
    memory_type TEXT NOT NULL,   -- fact/preference/event/summary
    importance REAL DEFAULT 0.5,
    embedding_id TEXT,           -- ChromaDB中的向量ID
    source_conversation_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    access_count INTEGER DEFAULT 0,
    metadata TEXT                -- JSON
);

-- 索引
CREATE INDEX idx_memories_type ON memories(memory_type);
CREATE INDEX idx_memories_importance ON memories(importance);
CREATE INDEX idx_messages_conversation ON messages(conversation_id);
```

---

## 7. 关键流程

### 7.1 用户输入处理流程

```
用户输入
    │
    ▼
命令解析（是否为系统命令如 /memory, /config）
    │
    ├── 是 → 执行系统命令 → 返回结果
    │
    └── 否 → 进入Agent处理
              │
              ▼
         检索相关记忆
              │
              ▼
         构建LLM请求（系统提示 + 记忆 + 对话历史 + 用户输入）
              │
              ▼
         LLM响应
              │
              ├── 包含工具调用 → 执行工具 → 结果回传LLM → 循环
              │
              └── 纯文本回复 → 输出给用户
                                    │
                                    ▼
                              记忆提取与存储
```

### 7.2 记忆检索决策流程

```
用户输入
    │
    ▼
快速分类（LLM判断）
    │
    ├── 闲聊/简单问答 → 不检索记忆
    │
    ├── 涉及用户个人信息 → 检索fact/preference类记忆
    │
    ├── 涉及历史任务 → 检索event/summary类记忆
    │
    └── 复杂任务 → 全类型检索
```

---

## 8. 系统提示词设计

```python
SYSTEM_PROMPT = """你是 Soul-agent，一个运行在终端中的智能助手。

## 核心能力
- 通过工具完成文件操作、命令执行、网络请求等任务
- 记住用户的偏好和重要信息，提供个性化服务
- 将复杂任务拆解为步骤逐一完成

## 行为准则
1. 优先使用工具完成任务，而非仅给出建议
2. 执行危险操作前必须确认
3. 回复简洁直接，避免冗余
4. 遇到不确定的情况主动询问

## 当前上下文
{memory_context}

## 可用工具
{tool_descriptions}
"""

MEMORY_EXTRACTION_PROMPT = """分析以下对话，提取值得长期记忆的信息。

提取规则：
1. 用户的个人信息（姓名、职业、偏好等）→ type: fact
2. 用户表达的偏好（喜欢/不喜欢）→ type: preference
3. 重要事件或决定 → type: event
4. 不提取临时性、无长期价值的信息

输出JSON格式：
{
  "should_memorize": true/false,
  "memories": [
    {"content": "...", "type": "...", "importance": 0.0-1.0}
  ]
}
"""
```

---

## 9. 开发计划

### Phase 1: 基础框架（第1-2周）

- [ ] 项目初始化（Poetry、目录结构、配置）
- [ ] CLI框架搭建（Click + Rich）
- [ ] LLM适配层实现（OpenAI兼容API）
- [ ] 基础对话功能（多轮对话、流式输出）

### Phase 2: 工具系统（第3-4周）

- [ ] 工具注册与执行框架
- [ ] 内置工具实现（文件、命令、网络）
- [ ] Agent ReAct循环
- [ ] 工具调用安全控制

### Phase 3: 记忆系统（第5-6周）

- [ ] SQLite存储层
- [ ] ChromaDB向量检索
- [ ] 记忆写入决策（LLM判断）
- [ ] 智能记忆检索（混合评分）
- [ ] 对话摘要生成

### Phase 4: 完善与优化（第7-8周）

- [ ] 错误处理与边界情况
- [ ] 性能优化（缓存、并发）
- [ ] 用户体验优化（进度条、快捷键）
- [ ] 单元测试与集成测试
- [ ] 文档编写

---

## 10. 依赖清单

```toml
# pyproject.toml 核心依赖

[tool.poetry.dependencies]
python = "^3.11"
openai = "^1.40.0"          # LLM API调用
chromadb = "^0.5.0"         # 向量数据库
rich = "^13.7.0"            # 终端美化
prompt-toolkit = "^3.0.43"  # 终端输入增强
click = "^8.1.7"            # CLI框架
pyyaml = "^6.0.1"           # 配置文件解析
pydantic = "^2.6.0"         # 数据验证
aiosqlite = "^0.20.0"       # 异步SQLite
python-dotenv = "^1.0.1"    # 环境变量

[tool.poetry.dependencies.dev]
pytest = "^8.0.0"
pytest-asyncio = "^0.23.0"
ruff = "^0.3.0"             # 代码检查与格式化
```

---

## 11. 接口规范

### 11.1 工具定义Schema（供LLM调用）

```json
{
  "type": "function",
  "function": {
    "name": "read_file",
    "description": "读取指定路径的文件内容",
    "parameters": {
      "type": "object",
      "properties": {
        "path": {
          "type": "string",
          "description": "文件的绝对或相对路径"
        }
      },
      "required": ["path"]
    }
  }
}
```

### 11.2 记忆检索接口

```python
class MemoryManager:
    async def retrieve(self, query: str, top_k: int = 5) -> list[MemoryEntry]: ...
    async def store(self, content: str, memory_type: str, importance: float): ...
    async def forget(self, memory_id: str): ...
    async def list_all(self, memory_type: str | None = None) -> list[MemoryEntry]: ...
```

---

## 12. 安全设计

| 风险 | 防护措施 |
|------|---------|
| 命令注入 | 命令白名单 + 危险命令拦截 + 用户确认 |
| API密钥泄露 | 环境变量存储，不写入代码或日志 |
| 文件越权访问 | 工作目录限制，敏感路径黑名单 |
| 记忆投毒 | 记忆内容不直接作为系统指令 |
| 资源耗尽 | 命令执行超时，输出长度限制 |

---

## 13. 扩展方向（后期）

1. **插件系统**：支持用户自定义工具插件
2. **多模态**：支持图片输入分析
3. **Web UI**：可选的浏览器界面
4. **多Agent协作**：任务分发给专业子Agent
5. **知识库**：接入本地文档作为RAG知识源

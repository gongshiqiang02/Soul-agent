<h1 align="center">Soul-agent</h1>

<p align="center">
  <strong>更懂你的通用 Agent —— 基于 LLM 的终端智能助手</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.11+-blue.svg" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/license-MIT-green.svg" alt="MIT License">
  <img src="https://img.shields.io/badge/tests-76%20passed-brightgreen.svg" alt="Tests">
</p>

---

Soul-agent 是一个运行在终端中的 AI 智能助手。它不仅能通过自然语言对话完成各类任务，更拥有**长期记忆系统**——能够记住你的偏好、历史对话和关键信息，实现"越用越懂你"的个性化体验。

## ✨ 功能特性

| 功能 | 说明 |
|------|------|
| **智能对话** | 基于 LLM 的多轮自然语言对话，支持流式输出 |
| 🔧 **工具调用** | 自动执行文件操作、Shell 命令、网络请求等，采用 ReAct 推理循环 |
| 🧠 **长期记忆** | 自动提取并持久化用户偏好与关键信息，智能混合检索召回 |
| 📝 **文档读写** | 读取、生成、编辑各类文档 |
| 📋 **任务规划** | 将复杂任务自动拆解为可执行步骤，实时进度显示 |
| 🎨 **精致终端 UI** | Claude Code 风格紧凑显示，工具调用参数可见，流式输出，回合统计 |
| 🔌 **多模型支持** | OpenAI / 兼容 API / Ollama 本地模型，一键切换 |

---

## 📦 安装

### 环境要求

- Python 3.11+
- [uv](https://github.com/astral-sh/uv)（推荐）或 pip

### 步骤

```bash
# 1. 克隆项目
git clone <repo-url>
cd Soul-agent

# 2. 创建虚拟环境
uv venv
# Windows:
.venv\Scripts\activate
# Linux / macOS:
source .venv/bin/activate

# 3. 安装依赖（含开发依赖）
uv pip install -e ".[dev]"
```

---

## ⚙️ 配置

### 环境变量

```bash
# 复制模板
cp .env.example .env
```

编辑 `.env` 文件：

```ini
# OpenAI API Key（必填）
OPENAI_API_KEY=sk-your-api-key-here

# 自定义 API 地址（可选，用于接入兼容 API，如 DeepSeek、智谱、中转站等）
OPENAI_BASE_URL=https://api.example.com/v1

# 模型名称（可选，覆盖配置文件中的模型）
SOUL_AGENT_MODEL=gpt-4o-mini
```

### 配置文件

主配置文件位于 `config/default.yaml`，支持以下选项：

```yaml
llm:
  provider: "openai"           # 模型提供商: openai / local
  model: "gpt-4o-mini"        # 模型名称
  api_key: "${OPENAI_API_KEY}" # 从环境变量读取
  base_url: null               # 自定义 API 地址
  temperature: 0.7             # 生成温度
  max_tokens: 4096             # 最大输出 token

agent:
  max_iterations: 10           # 单次任务最大工具调用轮数

memory:
  enabled: true                # 是否启用记忆系统
  db_path: "./data/memory.db"  # SQLite 数据库路径
  vector_db_path: "./data/chroma"  # 向量数据库路径
  max_memories_per_query: 5    # 每次检索返回的记忆条数
  importance_threshold: 0.3    # 低于此分数的记忆不存储

tools:
  enabled:                     # 启用的工具列表
    - read_file
    - write_file
    - list_directory
    - run_command
    - web_request
    - search_files
  shell:
    timeout: 30                # 命令执行超时（秒）
    blocked_commands:           # 被禁止的危险命令
      - "rm -rf /"
      - "format"

ui:
  theme: "monokai"             # 终端主题: monokai / dracula / default
  stream: true                 # 是否启用流式输出（已启用）
  show_thinking: false         # 是否显示思考过程
  language: "zh"               # 界面语言
```

### 使用本地模型（Ollama）

1. 安装并启动 [Ollama](https://ollama.ai/)
2. 修改配置：

```yaml
llm:
  provider: "local"
  model: "qwen2.5:7b"    # 或其他已下载的模型
```

---

## 🚀 使用

### 启动交互式对话

```bash
soul-agent
# 或
soul-agent chat
```

启动后会进入交互式终端，直接输入问题即可对话：

```
┌──────────────────────────────────────────────┐
│ soul-agent — 更懂你的通用Agent               │
│ 模型: gpt-4o-mini                            │
│ Provider: openai                             │
│ 工作目录: E:\Projects\Soul-agent             │
│ 已启用工具: 6 个                              │
│ 记忆系统: 启用                               │
│                                              │
│ 输入你的问题开始对话，输入 /help 查看帮助，    │
│ /quit 退出                                   │
└──────────────────────────────────────────────┘

>>> 查看当前目录有哪些文件

✻ 思考中… (第 1 轮)

● list_directory(.)
  ⎿ [目录] soul_agent
    [文件] README.md
    [文件] pyproject.toml
    … +8 行

● 当前目录包含以下内容：
- **soul_agent/** - 主程序包目录
- **README.md** - 项目说明文档
- **pyproject.toml** - 项目配置文件
...

✓ 完成 · 1 次工具调用 · 3.2s · 1.5k tokens
```

### 单次提问

```bash
soul-agent ask "今天天气怎么样"
soul-agent ask "帮我写一个Python冒泡排序"
```

### 查看记忆

```bash
soul-agent memory
```

### 查看当前配置

```bash
soul-agent config
```

### 交互命令

在对话中可以使用以下命令：

| 命令 | 说明 |
|------|------|
| `/help` | 显示帮助信息 |
| `/memory` | 查看所有记忆列表 |
| `/history` | 查看历史会话列表 |
| `/name <标题>` | 为当前会话命名（如 `/name 技术讨论`） |
| `/clear` | 清除当前对话历史 |
| `/config` | 显示当前配置信息 |
| `/quit` | 退出程序（也可用 `/exit` 或 `Ctrl+C`） |

---

## 🧠 记忆系统

记忆系统是 Soul-agent 的核心差异化功能。它让 Agent 能够跨会话地记住用户信息，实现个性化交互。

### 工作原理

```
用户对话 → LLM 判断是否需要记忆 → 提取记忆条目 → 存储到 SQLite + ChromaDB
                                                          ↓
下次对话 → 检索相关记忆 → 注入上下文 → 生成更个性化的回复 ←─┘
```

### 记忆类型

| 类型 | 说明 | 示例 |
|------|------|------|
| `fact` | 用户相关事实 | "用户是计算机专业大三学生" |
| `preference` | 用户偏好 | "喜欢简洁的代码风格，偏好 Python" |
| `event` | 重要事件 | "2024-03-15 完成了项目部署" |
| `summary` | 对话摘要 | "讨论了数据库选型，最终选择 PostgreSQL" |

### 智能检索

记忆检索采用混合评分策略：

- **语义相似度 (50%)** — 基于 ChromaDB 向量检索，理解语义层面的相关性
- **重要性权重 (30%)** — 高重要性的记忆优先召回
- **时间衰减 (20%)** — 最近访问的记忆更容易被想起，半衰期 72 小时

当 ChromaDB 不可用时，自动降级为关键词搜索。

---

## 🔧 内置工具

Agent 可以自动调用以下工具完成任务：

| 工具 | 功能 | 安全限制 |
|------|------|---------|
| `read_file` | 读取文件内容 | 最大 100KB |
| `write_file` | 写入/创建文件 | 自动创建父目录 |
| `list_directory` | 列出目录内容 | 支持递归 |
| `run_command` | 执行 Shell 命令 | 超时控制 + 危险命令拦截 |
| `web_request` | 发送 HTTP 请求 | GET/POST，响应截断 10000 字符 |
| `search_files` | 搜索文件内容 | 按关键词匹配，返回文件名和行号 |

Agent 采用 **ReAct 模式**（Reasoning + Acting）自动决定何时调用工具：

```
观察用户输入 → 思考需要什么工具 → 调用工具 → 观察结果 → 继续思考或回复
```

---

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────────────┐
│                    用户终端 (CLI)                     │
├─────────────────────────────────────────────────────┤
│                  交互层 (Interface)                   │
│         Rich 渲染 │ Prompt Toolkit 输入 │ 命令解析    │
├─────────────────────────────────────────────────────┤
│                  核心层 (Core)                        │
│    Agent 引擎 │ 对话管理 │ 任务规划 │ 上下文管理       │
├──────────┬──────────┬───────────┬───────────────────┤
│ 记忆系统  │ 工具系统  │  LLM 适配  │    配置系统       │
│ Memory   │  Tools   │ LLM Layer │    Config         │
├──────────┴──────────┴───────────┴───────────────────┤
│                  存储层 (Storage)                     │
│         SQLite │ ChromaDB │ 本地文件系统              │
└─────────────────────────────────────────────────────┘
```

### 目录结构

```
Soul-agent/
├── soul_agent/                # 主包
│   ├── main.py               # 入口文件
│   ├── cli.py                # CLI 命令定义（Click）
│   ├── app.py                # 应用逻辑，连接各模块
│   ├── core/                 # 核心模块
│   │   ├── agent.py          # Agent 主循环（ReAct）
│   │   ├── conversation.py   # 对话管理
│   │   ├── planner.py        # 任务规划器
│   │   └── context.py        # 上下文窗口管理
│   ├── memory/               # 记忆系统
│   │   ├── manager.py        # 记忆管理器（统一入口）
│   │   ├── short_term.py     # 短期记忆（会话内）
│   │   ├── long_term.py      # 长期记忆（跨会话，SQLite）
│   │   ├── retriever.py      # 记忆检索（向量 + 关键词混合）
│   │   └── summarizer.py     # 对话摘要生成
│   ├── tools/                # 工具系统
│   │   ├── base.py           # 工具基类与 ToolResult
│   │   ├── registry.py       # 工具注册中心
│   │   ├── executor.py       # 工具执行器
│   │   └── builtin/          # 内置工具
│   │       ├── file_ops.py   # 文件读写、目录列表
│   │       ├── shell.py      # Shell 命令执行
│   │       ├── web.py        # HTTP 网络请求
│   │       └── search.py     # 文件内容搜索
│   ├── llm/                  # LLM 适配层
│   │   ├── client.py         # 统一客户端
│   │   ├── prompts.py        # 系统提示词
│   │   └── providers/        # 模型提供商
│   │       ├── openai.py     # OpenAI / 兼容 API
│   │       └── local.py      # 本地模型（Ollama）
│   ├── ui/                   # 终端 UI
│   │   ├── renderer.py       # Rich 渲染器
│   │   ├── input.py          # Prompt Toolkit 输入处理
│   │   └── themes.py         # 主题配置
│   ├── config/               # 配置模块
│   │   ├── settings.py       # 配置加载与 Pydantic 验证
│   │   └── defaults.py       # 默认配置
│   └── utils/                # 工具函数
│       ├── logger.py         # 日志
│       └── exceptions.py     # 自定义异常
├── config/
│   └── default.yaml          # 默认配置文件
├── data/                     # 运行时数据（已 gitignore）
│   ├── memory.db             # SQLite 记忆数据库
│   └── chroma/               # 向量数据库
├── tests/                    # 测试（42 个用例）
│   ├── test_agent.py         # Agent 核心测试
│   ├── test_memory.py        # 记忆系统测试
│   └── test_tools.py         # 工具系统测试
├── docs/
│   └── development-design.md # 开发设计文档
├── pyproject.toml            # 项目配置
├── .env.example              # 环境变量模板
├── .gitignore
└── README.md
```

---

## 🧪 测试

```bash
# 运行所有测试
pytest tests/ -v

# 运行特定模块测试
pytest tests/test_agent.py -v
pytest tests/test_memory.py -v
pytest tests/test_tools.py -v
```

当前测试覆盖：

- **test_agent.py** (29 个) — 对话管理、上下文裁剪、Agent ReAct 循环、任务规划、复杂度估算
- **test_memory.py** (14 个) — 短期记忆增删、长期记忆 CRUD、关键词搜索、MemoryManager 集成
- **test_tools.py** (18 个) — 工具注册/执行、文件读写、目录列表、文件搜索
- **test_conversation_persistence.py** (9 个) — 会话持久化、消息存储、历史检索
- **test_plan_tracker.py** (6 个) — 计划追踪、步骤状态更新

---

## 🔒 安全设计

| 风险 | 防护措施 |
|------|---------|
| 命令注入 | 危险命令黑名单拦截（如 `rm -rf /`） |
| API 密钥泄露 | 通过 `.env` 环境变量管理，不写入代码或日志 |
| 文件越权读取 | 文件大小限制（100KB），路径安全检查 |
| 资源耗尽 | Shell 命令执行超时（默认 30s），输出长度截断 |
| 记忆投毒 | 记忆内容仅作为上下文注入，不直接作为系统指令 |

---

## 🛠️ 技术栈

| 组件 | 技术方案 |
|------|---------|
| 编程语言 | Python 3.11+ |
| LLM 接口 | OpenAI SDK（兼容多种 API） |
| 向量数据库 | ChromaDB |
| 结构化存储 | SQLite（aiosqlite 异步驱动） |
| 终端 UI | Rich + Prompt Toolkit |
| CLI 框架 | Click |
| 数据验证 | Pydantic v2 |
| 配置格式 | YAML + dotenv |
| 测试框架 | Pytest + pytest-asyncio |
| 代码检查 | Ruff |

---

## 🗺️ 后续规划

- [ ] 插件系统 — 支持用户自定义工具插件
- [ ] 多模态 — 支持图片输入分析
- [ ] Web UI — 可选的浏览器界面
- [ ] 多 Agent 协作 — 任务分发给专业子 Agent
- [ ] 知识库 — 接入本地文档作为 RAG 知识源
- [ ] 记忆遗忘机制 — 自动淘汰低价值过期记忆

---

## 📄 许可证

本项目采用 [MIT License](LICENSE) 开源。

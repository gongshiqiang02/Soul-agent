# LLM 适配模块

本文档描述 `soul_agent/llm/` 模块的内部结构。LLM 适配模块负责屏蔽不同模型提供商的差异，对 Core 层提供统一的 `chat()` 调用接口。

---

## 1. 模块组成

```
soul_agent/llm/
├── __init__.py
├── client.py              # 统一 LLM 客户端
├── prompts.py             # 系统提示词和记忆提取提示词
└── providers/
    ├── __init__.py
    ├── openai.py          # OpenAI / OpenAI 兼容 API 提供商
    └── local.py           # 本地模型提供商（Ollama 等）
```

| 文件 | 主要对象 | 职责 |
|------|----------|------|
| `client.py` | `LLMClient` | 对外统一入口，按配置选择 provider |
| `providers/openai.py` | `OpenAIProvider`, `LLMResponse` | 调用 OpenAI 兼容接口，解析工具调用 |
| `providers/local.py` | `LocalProvider` | 复用 OpenAIProvider，默认连接 Ollama |
| `prompts.py` | `SYSTEM_PROMPT`, `MEMORY_EXTRACTION_PROMPT` | Agent 系统提示词与记忆提取提示词 |

---

## 2. 设计目标

LLM 模块的目标是让核心模块只依赖一个稳定接口：

```python
response = await llm_client.chat(messages, tools=schemas, stream=False)
```

不管底层是 OpenAI、DeepSeek、智谱、Ollama，还是其他兼容 API，Core 层都只关心返回的 `LLMResponse`。

```
Agent
  │
  ▼
LLMClient.chat()
  │
  ├─ provider = openai ──→ OpenAIProvider
  │
  └─ provider = local ───→ LocalProvider ──→ Ollama OpenAI-compatible API
```

---

## 3. LLMClient 统一入口

`LLMClient` 位于 `client.py`。

### 3.1 初始化

```python
class LLMClient:
    def __init__(self, config: LLMConfig):
        self.config = config
        self.provider = self._init_provider(config)
```

根据 `config.provider` 选择具体 provider：

```python
providers = {
    "openai": OpenAIProvider,
    "local": LocalProvider,
}
provider_cls = providers.get(config.provider, OpenAIProvider)
return provider_cls(config)
```

如果配置了未知 provider，会默认使用 `OpenAIProvider`。

### 3.2 统一调用方法

```python
async def chat(self, messages, tools=None, stream=False) -> LLMResponse:
    try:
        return await self.provider.chat(messages, tools=tools, stream=stream)
    except Exception as e:
        logger.error(f"LLM调用失败: {e}")
        raise
```

职责：

1. 将请求转发给 provider。
2. 统一记录错误日志。
3. 返回标准 `LLMResponse`。

---

## 4. LLMResponse 数据结构

`LLMResponse` 位于 `providers/openai.py`。

```python
class LLMResponse:
    def __init__(self, content="", tool_calls=None, usage=None):
        self.content = content
        self.tool_calls = tool_calls or []
        self.usage = usage

    @property
    def has_tool_calls(self):
        return len(self.tool_calls) > 0
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `content` | `str` | 模型生成的文本内容 |
| `tool_calls` | `list[dict]` | 模型请求调用的工具列表 |
| `usage` | provider usage 对象 | token 使用量等统计信息 |
| `has_tool_calls` | `bool` | 是否存在工具调用 |

工具调用被统一解析为：

```python
{
    "id": "call_xxx",
    "name": "read_file",
    "arguments": {"path": "README.md"}
}
```

Core 层不需要关心 OpenAI SDK 原始对象结构。

---

## 5. OpenAIProvider

`OpenAIProvider` 是主要实现，支持 OpenAI 以及所有 OpenAI 兼容 API。

### 5.1 初始化

```python
self.client = AsyncOpenAI(
    api_key=config.api_key or "sk-placeholder",
    base_url=config.base_url,
)
self.model = config.model
```

说明：

- 使用 `AsyncOpenAI`，所有调用都是异步的。
- `base_url` 可为空，使用 OpenAI 默认地址。
- `api_key` 为空时使用占位字符串，方便本地兼容 API 场景。

### 5.2 chat 方法

```python
async def chat(self, messages, tools=None, stream=True) -> LLMResponse:
    kwargs = {
        "model": self.model,
        "messages": messages,
        "temperature": self.config.temperature,
        "max_tokens": self.config.max_tokens,
    }
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"

    if stream and not tools:
        return await self._stream_chat(**kwargs)
    else:
        return await self._normal_chat(**kwargs)
```

决策逻辑：

| 情况 | 调用方式 |
|------|----------|
| 有工具 schema | 普通非流式调用，便于解析 tool_calls |
| 无工具且 stream=True | 流式调用，收集所有 chunk 后返回 |
| 无工具且 stream=False | 普通调用 |

当前 UI 层还没有逐 token 输出，因此 `_stream_chat()` 会收集所有 chunk，最终返回完整 `LLMResponse`。

### 5.3 普通调用

```python
response = await self.client.chat.completions.create(**kwargs)
choice = response.choices[0]
return LLMResponse(
    content=choice.message.content or "",
    tool_calls=self._parse_tool_calls(choice.message.tool_calls),
    usage=response.usage,
)
```

### 5.4 流式调用

```python
kwargs["stream"] = True
chunks = []
async for chunk in await self.client.chat.completions.create(**kwargs):
    delta = chunk.choices[0].delta if chunk.choices else None
    if delta and delta.content:
        chunks.append(delta.content)
return LLMResponse(content="".join(chunks))
```

目前流式调用只处理文本内容，不处理流式工具调用。

### 5.5 工具调用解析

```python
def _parse_tool_calls(self, tool_calls):
    if not tool_calls:
        return []
    result = []
    for tc in tool_calls:
        result.append({
            "id": tc.id,
            "name": tc.function.name,
            "arguments": json.loads(tc.function.arguments),
        })
    return result
```

解析后的结构会被 Agent 直接传给 `ToolExecutor`。

---

## 6. LocalProvider

`LocalProvider` 位于 `providers/local.py`，继承 `OpenAIProvider`。

```python
class LocalProvider(OpenAIProvider):
    def __init__(self, config: LLMConfig):
        if not config.base_url:
            config = config.model_copy(update={"base_url": "http://localhost:11434/v1"})
        super().__init__(config)
```

设计含义：

- 本地模型只要暴露 OpenAI 兼容接口，就可以复用全部 OpenAIProvider 逻辑。
- 默认地址为 Ollama 的 OpenAI 兼容端点：`http://localhost:11434/v1`。
- 若用户在配置中显式设置 `base_url`，则使用用户配置。

配置示例：

```yaml
llm:
  provider: "local"
  model: "qwen2.5:7b"
  api_key: null
  base_url: null
```

---

## 7. Prompt 设计

### 7.1 SYSTEM_PROMPT

位于 `prompts.py`：

```text
你是 Soul-agent，一个运行在终端中的智能助手。

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
```

两个占位符由 Core 层填充：

| 占位符 | 来源 | 内容 |
|--------|------|------|
| `{memory_context}` | `Conversation.build_messages()` | 检索到的长期记忆 |
| `{tool_descriptions}` | `ToolRegistry.get_descriptions()` | 当前启用工具列表 |

### 7.2 MEMORY_EXTRACTION_PROMPT

该提示词定义了长期记忆提取规则：

```text
分析以下对话，提取值得长期记忆的信息。

提取规则：
1. 用户的个人信息（姓名、职业、偏好等）→ type: fact
2. 用户表达的偏好（喜欢/不喜欢）→ type: preference
3. 重要事件或决定 → type: event
4. 不提取临时性、无长期价值的信息
```

注意：当前实际 `MemoryManager` 使用的是 `manager.py` 中定义的 `EXTRACT_MEMORIES_PROMPT`，而 `prompts.py` 中的 `MEMORY_EXTRACTION_PROMPT` 可作为后续统一提示词管理的基础。

---

## 8. 与工具调用的关系

LLM 模块本身不执行工具，只负责：

1. 把工具 schema 发送给模型。
2. 接收模型返回的 `tool_calls`。
3. 将 SDK 原始结构解析为通用字典。

实际执行发生在 `tools/executor.py`。

```
ToolRegistry.schemas
        │
        ▼
LLMClient.chat(messages, tools=schemas)
        │
        ▼
OpenAIProvider
        │
        ▼
LLMResponse(tool_calls=[...])
        │
        ▼
Agent → ToolExecutor
```

---

## 9. 扩展新 Provider

如果新服务兼容 OpenAI API，只需继承 `OpenAIProvider`：

```python
class MyProvider(OpenAIProvider):
    def __init__(self, config):
        if not config.base_url:
            config = config.model_copy(update={"base_url": "https://api.example.com/v1"})
        super().__init__(config)
```

然后在 `LLMClient._init_provider()` 中注册：

```python
providers = {
    "openai": OpenAIProvider,
    "local": LocalProvider,
    "my": MyProvider,
}
```

如果不兼容 OpenAI API，则需要实现同样的接口：

```python
async def chat(self, messages, tools=None, stream=True) -> LLMResponse:
    ...
```

只要返回 `LLMResponse`，Core 层无需修改。

---

## 10. 当前限制与改进方向

1. **流式工具调用未实现**：当前有工具时强制走普通调用。
2. **usage 结构未标准化**：`usage` 直接透传 provider 原始对象。
3. **provider 注册为硬编码字典**：未来可改为插件式注册。
4. **记忆提取提示词分散**：`prompts.py` 和 `manager.py` 各有相关提示词，后续可统一。
5. **错误分类较粗**：当前 LLM 错误统一记录后抛出，未来可细分认证错误、限流、网络错误等。

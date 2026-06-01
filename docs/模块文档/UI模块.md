# UI 模块

本文档描述 `soul_agent/ui/` 模块的内部结构。UI 模块负责终端输入、终端渲染和主题管理，位于 CLI 层与 Core 层之间，只处理交互表现，不参与 Agent 推理逻辑。

---

## 1. 模块组成

```
soul_agent/ui/
├── __init__.py
├── renderer.py       # Rich 渲染器
├── input.py          # Prompt Toolkit 输入处理
└── themes.py         # 主题配置
```

| 文件 | 主要对象 | 职责 |
|------|----------|------|
| `renderer.py` | `Renderer` | 负责欢迎页、用户输入、助手回复、工具调用、错误、记忆表格等输出 |
| `input.py` | `InputHandler` | 负责异步读取用户输入、历史记录、自动建议 |
| `themes.py` | `THEMES`, `get_theme()` | 定义和获取终端配色主题 |

---

## 2. UI 模块在系统中的位置

```
用户终端
  │
  ├─ 输入 ──→ InputHandler ──→ app.run_chat() ──→ Agent.run()
  │
  └─ 输出 ←─ Renderer ←────── app.run_chat() ←── Agent 返回结果/工具事件
```

UI 模块不直接调用 LLM，也不直接执行工具。它只做两件事：

1. 把终端输入转换为字符串。
2. 把系统状态和 Agent 输出渲染到终端。

---

## 3. Renderer 渲染器

`Renderer` 位于 `renderer.py`，基于 Rich 实现。

### 3.1 初始化

```python
class Renderer:
    def __init__(self, theme_name: str = "monokai"):
        self.console = Console()
        self.theme = get_theme(theme_name)
```

初始化时创建一个 Rich `Console`，并根据主题名获取颜色配置。

### 3.2 欢迎界面

```python
def render_welcome(self):
    welcome = Text()
    welcome.append("🤖 Soul-agent", style="bold bright_cyan")
    ...
    self.console.print(Panel(welcome, border_style=self.theme["border_color"]))
```

欢迎界面使用：

- `Text` 拼接多段带样式文本
- `Panel` 绘制边框
- `border_style` 由主题控制

### 3.3 用户输入渲染

```python
def render_user_input(self, text: str):
    self.console.print(f"\n[{self.theme['user_color']}]👤 You:[/] {text}")
```

用户输入以固定前缀 `👤 You:` 展示。

### 3.4 助手回复渲染

```python
def render_assistant(self, text: str):
    self.console.print(f"\n[{self.theme['assistant_color']}]🤖 Soul-agent:[/]")
    try:
        md = Markdown(text)
        self.console.print(md)
    except Exception:
        self.console.print(text)
```

特点：

1. 默认将助手回复作为 Markdown 渲染。
2. 如果 Markdown 渲染失败，回退为普通文本。
3. 渲染颜色来自当前主题。

这允许模型输出代码块、列表、标题等 Markdown 内容，终端中仍能保持较好的可读性。

### 3.5 工具调用渲染

```python
def render_tool_call(self, tool_name: str, args: dict):
    self.console.print(
        f"  [{self.theme['tool_color']}]🔧 调用工具: {tool_name}[/]",
        style="dim",
    )
```

该方法由 Agent 的 `on_tool_call` 回调触发：

```python
agent.set_callbacks(
    on_tool_call=lambda name, args: renderer.render_tool_call(name, args),
)
```

当前只显示工具名称，没有展示完整参数，避免终端输出过长。

### 3.6 错误与提示信息

```python
def render_error(self, message: str):
    self.console.print(f"[{self.theme['error_color']}]❌ {message}[/]")


def render_info(self, message: str):
    self.console.print(f"[{self.theme['info_color']}]{message}[/]")
```

错误信息和普通提示信息由不同颜色区分。

### 3.7 记忆列表渲染

```python
def render_memory_list(self, memories: list):
    table = Table(title="📝 记忆列表", show_header=True, header_style="bold bright_cyan")
    table.add_column("类型", style="yellow", width=12)
    table.add_column("内容", style="white")
    table.add_column("重要性", style="green", width=8)
```

输出字段：

| 列 | 来源 | 处理方式 |
|----|------|----------|
| 类型 | `m.memory_type` | 原样展示 |
| 内容 | `m.content` | 超过 60 字符截断加 `...` |
| 重要性 | `m.importance` | 保留 1 位小数 |

如果没有记忆，则显示：

```text
暂无记忆
```

### 3.8 帮助信息渲染

`render_help()` 使用 Rich `Panel` 输出交互命令说明：

- `/help`
- `/memory`
- `/clear`
- `/config`
- `/quit`

虽然这属于用户交互文本，但实现上仍是 UI 模块的一部分。

---

## 4. InputHandler 输入处理

`InputHandler` 位于 `input.py`，基于 Prompt Toolkit 实现。

### 4.1 初始化

```python
history_dir = Path("data")
history_dir.mkdir(parents=True, exist_ok=True)
history_file = history_dir / ".input_history"
```

输入历史存储在：

```text
data/.input_history
```

该目录会自动创建。

### 4.2 PromptSession 配置

```python
self.session = PromptSession(
    history=FileHistory(str(history_file)),
    auto_suggest=AutoSuggestFromHistory(),
    style=self.style,
)
```

启用能力：

| 能力 | 实现 |
|------|------|
| 历史记录 | `FileHistory` |
| 历史自动建议 | `AutoSuggestFromHistory` |
| 提示符样式 | `Style.from_dict()` |
| 异步输入 | `prompt_async()` |

提示符样式：

```python
self.style = Style.from_dict({
    "prompt": "ansicyan bold",
})
```

### 4.3 异步输入

```python
async def get_input(self, prompt_text: str = ">>> ") -> str:
    try:
        result = await self.session.prompt_async(
            [("class:prompt", prompt_text)],
        )
        return result.strip()
    except (EOFError, KeyboardInterrupt):
        return "/quit"
```

设计点：

1. 使用异步输入，便于与异步 Agent/LLM 调用共存。
2. 输入自动 `strip()`，避免空格影响命令判断。
3. `EOFError` 和 `KeyboardInterrupt` 会被转换为 `/quit`，由上层统一退出。

---

## 5. 主题系统

`themes.py` 中定义了 `THEMES` 字典。

### 5.1 主题结构

每个主题包含以下颜色键：

```python
{
    "user_color": "bright_green",
    "assistant_color": "bright_cyan",
    "system_color": "yellow",
    "error_color": "bright_red",
    "tool_color": "bright_magenta",
    "info_color": "dim",
    "border_color": "bright_blue",
}
```

| 键 | 用途 |
|----|------|
| `user_color` | 用户输入前缀 |
| `assistant_color` | 助手回复前缀 |
| `system_color` | 系统信息，当前预留 |
| `error_color` | 错误消息 |
| `tool_color` | 工具调用提示 |
| `info_color` | 普通提示 |
| `border_color` | Panel 边框 |

### 5.2 内置主题

当前内置 3 个主题：

| 主题 | 风格 |
|------|------|
| `monokai` | 高亮、鲜艳，默认主题 |
| `dracula` | 暗色紫色系 |
| `default` | 简洁默认色 |

### 5.3 获取主题

```python
def get_theme(name: str) -> dict:
    return THEMES.get(name, THEMES["default"])
```

如果主题不存在，则回退到 `default`。

---

## 6. 与 app.py 的集成

`app.run_chat()` 中创建 UI 组件：

```python
config = load_config()
renderer = Renderer(config.ui.theme)
input_handler = InputHandler()
```

交互主循环：

```python
while True:
    user_input = await input_handler.get_input()
    ...
    renderer.render_user_input(user_input)
    response = await agent.run(user_input)
    renderer.render_assistant(response)
```

系统命令也由 `app.py` 调用 Renderer 输出：

```python
if cmd == "/memory":
    memories = await agent.memory.list_all()
    renderer.render_memory_list(memories)
```

---

## 7. 设计特点

### 7.1 表现层独立

UI 模块不包含业务逻辑。它不知道 LLM、工具、记忆如何工作，只负责显示。

### 7.2 Rich 与 Prompt Toolkit 分工清晰

| 库 | 用途 |
|----|------|
| Rich | 输出渲染、Markdown、Panel、Table |
| Prompt Toolkit | 输入、历史、自动建议、异步 prompt |

### 7.3 异步友好

`InputHandler.get_input()` 是异步方法，和异步 LLM、数据库、工具调用保持一致。

### 7.4 可配置主题

主题名来自配置项：

```yaml
ui:
  theme: "monokai"
```

UI 层无需修改代码即可切换配色。

---

## 8. 当前限制与改进方向

1. **未实现真正流式渲染**：`render_assistant()` 当前一次性输出完整回复。
2. **工具参数未显示**：`render_tool_call()` 只显示工具名，未来可折叠显示参数。
3. **帮助文本硬编码**：交互命令变化时需手动更新 `render_help()`。
4. **主题字段未完全使用**：`system_color` 当前基本预留。
5. **缺少进度动画**：长时间 LLM 调用或工具执行时没有 spinner/progress。

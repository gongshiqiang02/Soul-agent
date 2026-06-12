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

`Renderer` 位于 `renderer.py`，基于 Rich 实现。采用 Claude Code 紧凑风格。

### 3.1 初始化

```python
class Renderer:
    def __init__(self, theme_name: str = "monokai"):
        self.console = Console()
        self.theme = get_theme(theme_name)
        self._live: Live | None = None  # 统一的底部Live区域
        self._plan_tracker = None  # 当前计划
        self._status_text: str = ""  # spinner状态文本
        self._stream_buffer: str = ""  # 流式回复缓冲
        self._stream_active: bool = False  # 本轮是否有流式输出
```

初始化时创建一个 Rich `Console`，并根据主题名获取颜色配置。维护统一的 Live 实例用于底部动态显示。

### 3.2 欢迎界面

```python
def render_welcome(self, config=None, tool_count=0, memory_enabled=False):
    welcome = Text()
    welcome.append("🤖 Soul-agent", style="bold bright_cyan")
    ...
    if config:
        welcome.append("模型: ", style="dim")
        welcome.append(f"{config.llm.model}\n", style="bright_cyan")
        # 显示 provider、工作目录、工具数、记忆状态
    self.console.print(Panel(welcome, border_style=self.theme["border_color"]))
```

欢迎界面使用：

- `Text` 拼接多段带样式文本
- `Panel` 绘制边框
- `border_style` 由主题控制
- **新增**：显示模型、provider、工作目录、已启用工具数量、记忆系统状态（信息化）

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
    if not text or not text.strip():
        self.console.print("  [dim](Agent 无输出)[/]")
        return
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
4. 空内容防御：当 Agent 返回空白（如 max_iterations 耗尽）时显示 `(Agent 无输出)` 而非空白行。

这允许模型输出代码块、列表、标题等 Markdown 内容，终端中仍能保持较好的可读性。

### 3.5 工具调用渲染

```python
def render_tool_call(self, tool_name: str, args: dict):
    # 流式回复中若有缓冲,先输出它
    if self._stream_buffer:
        self._flush_stream_buffer()
    
    # 格式化参数摘要
    param_str = self._format_tool_params(tool_name, args)
    line = f"⏺ [{self.theme['tool_color']}]{tool_name}[/]({param_str})"
    if len(line) > 120:
        line = line[:117] + "..."
    self.console.print(line)
```

该方法由 Agent 的 `on_tool_call` 回调触发。**Claude Code 紧凑风格**：

- 格式：`⏺ tool_name(参数摘要)`
- 内置工具智能格式化（见 `_format_tool_params`）：
  - `read_file` → 显示 path
  - `write_file` → 显示 path + content 大小（如 `1.2KB`）
  - `list_directory` → 显示 path，recursive 时加标记
  - `run_command` → 显示 command
  - `web_request` → 显示 method + url
  - `search_files` → 显示 pattern + path
  - 未知工具 → fallback 为 `k=v` 序列，值截断 60 字符
- 整行截断 120 字符
- **修复核心问题**：之前只显示工具名，现在参数可见

### 3.6 工具结果渲染

```python
def render_tool_result(self, tool_name: str, success: bool, output: str, error: str | None = None):
    """渲染工具执行结果 - 连接符风格"""
    connector = f"[{self.theme['connector_color']}]  ⎿[/] "
    
    if not success:
        self.console.print(f"{connector}[{self.theme['error_color']}]错误: {error or output}[/]")
        return
    
    # 成功结果 - 特殊处理read_file
    if tool_name == "read_file":
        lines = output.count("\n") + 1
        self.console.print(f"{connector}读取 {lines} 行")
        return
    
    # 其他工具 - 显示前3行
    lines = output.split("\n")
    for i, line in enumerate(lines[:3]):
        if i == 0:
            self.console.print(f"{connector}{line}")
        else:
            self.console.print(f"    {line}")
    
    if len(lines) > 3:
        extra = len(lines) - 3
        self.console.print(f"    [{self.theme['stats_color']}]… +{extra} 行[/]")
```

该方法由 Agent 的 `on_tool_result` 回调触发：

- **连接符风格**：使用 `⎿` 连接符（类似 Claude Code 的 tree 风格）
- **read_file 优化**：成功时只显示 `⎿ 读取 N 行`，不倾倒全部内容
- **其他工具**：显示前 3 行，超出显示 `… +N 行`（dim 颜色）
- **失败**：红色 `⎿ 错误: xxx`
- **解决了之前问题**：不再截断 300 字符挤在一行，可读性大幅提升

### 3.7 统一 Live 管理与流式渲染

```python
def _build_live_content(self):
    """构建统一Live区域的内容"""
    parts = []
    if self._plan_tracker and self._plan_tracker.steps:
        parts.append(self._build_plan_panel(self._plan_tracker))
    if self._stream_buffer:
        parts.append(Markdown(self._stream_buffer + " ▌"))
    elif self._status_text:
        spinner = Spinner("dots", text=self._status_text, style=self.theme["info_color"])
        parts.append(spinner)
    return Group(*parts) if parts else Text("")

def begin_turn(self):
    """开始新的对话轮次,启动Live"""
    self._stream_buffer = ""
    self._stream_active = False
    if self._live is None:
        self._live = Live(
            self._build_live_content(),
            console=self.console,
            auto_refresh=True,
            transient=True,
            screen=False,
        )
        self._live.start()

def update_status(self, text: str):
    """更新状态文本(spinner)"""
    self._status_text = text
    if self._live:
        self._live.update(self._build_live_content())

def on_stream_chunk(self, chunk: str):
    """接收流式回复块"""
    self._stream_buffer += chunk
    self._stream_active = True
    if self._live:
        self._live.update(self._build_live_content())

def end_turn(self, stats: dict | None = None, final_text: str = ""):
    """结束对话轮次,停止Live并输出最终内容"""
    if self._live:
        self._live.stop()
        self._live = None
    
    # 输出最终回复
    if final_text:
        self.render_assistant(final_text)
    
    # 输出统计行
    if stats:
        parts = [f"[{self.theme['success_color']}]✓ 完成[/]"]
        if stats.get("tool_calls", 0) > 0:
            parts.append(f"{stats['tool_calls']} 次工具调用")
        if stats.get("elapsed"):
            parts.append(f"{stats['elapsed']:.1f}s")
        if stats.get("tokens"):
            tokens = stats["tokens"]
            parts.append(f"{tokens/1000:.1f}k tokens" if tokens >= 1000 else f"{tokens} tokens")
        self.console.print(f"[{self.theme['stats_color']}]{' · '.join(parts)}[/]\n")
```

**核心架构改进**：

- **统一 Live 实例**：Rich 只允许一个活动 Live，计划面板/spinner/流式输出必须合并
- **动态内容组合**：`_build_live_content()` 用 `Group` 组合多个元素
- **三种状态**：
  1. 思考中 → 显示 Spinner + 状态文本（如 `✻ 思考中… (第 N 轮)`）
  2. 流式回复 → 显示 Markdown(缓冲 + "▌" 光标)
  3. 计划执行 → 同时显示计划面板和状态
- **离散事件**：工具调用/结果用 `console.print()` 直接输出，自动滚动到 Live 上方
- **流式渲染**：`on_stream_chunk` 逐块累积，Live 实时更新 Markdown
- **回合统计**：`end_turn` 输出 `✓ 完成 · N 次工具调用 · X.Xs · Xk tokens`
- **transient 模式**：Live 停止后不留痕迹

### 3.8 错误与提示信息

```python
def render_error(self, message: str):
    self.console.print(f"[{self.theme['error_color']}]❌ {message}[/]")


def render_info(self, message: str):
    self.console.print(f"[{self.theme['info_color']}]{message}[/]")
```

错误信息和普通提示信息由不同颜色区分。

### 3.9 记忆列表渲染

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

### 3.10 帮助信息渲染

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
    "connector_color": "dim",          # 新增：⎿ 连接符
    "success_color": "bright_green",   # 新增：成功提示
    "stats_color": "dim",              # 新增：统计行
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
| `connector_color` | 工具结果连接符 `⎿` |
| `success_color` | 成功提示（如统计行的 `✓`） |
| `stats_color` | 统计行文本 |

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
    """获取主题,与default主题合并返回,确保所有key存在"""
    base = THEMES["default"].copy()
    selected = THEMES.get(name, {})
    base.update(selected)
    return base
```

如果主题不存在，则回退到 `default`。**改进**：与 default 主题合并返回，确保新增的颜色 key 在旧主题中也存在，避免 KeyError。

---

## 6. 与 app.py 的集成

`app.run_chat()` 中创建 UI 组件：

```python
config = load_config()
renderer = Renderer(config.ui.theme)
input_handler = InputHandler()

# 显示欢迎界面(在agent创建成功后)
renderer.render_welcome(
    config=config,
    tool_count=len(agent.tools.names),
    memory_enabled=config.memory.enabled,
)
```

交互主循环：

```python
agent.set_callbacks(
    on_tool_call=lambda name, args: renderer.render_tool_call(name, args),
    on_plan_progress=lambda tracker: renderer.render_plan_steps(tracker),
    on_tool_result=lambda name, success, output, error: renderer.render_tool_result(name, success, output, error),
    on_stream=renderer.on_stream_chunk,      # 新增：流式回调
    on_status=renderer.update_status,        # 新增：状态回调
)

while True:
    user_input = await input_handler.get_input()
    ...
    renderer.clear_plan_live()  # 清除上一轮Live
    renderer.render_user_input(user_input)
    
    try:
        renderer.begin_turn()  # 启动Live
        response = await agent.run(user_input)
        renderer.end_turn(agent.last_run_stats, response)  # 停止Live并输出统计
    except Exception as e:
        renderer.end_turn()  # 确保Live被停止
        renderer.render_error(f"处理失败: {e}")
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

1. ~~**未实现真正流式渲染**~~ **已完成** — `on_stream_chunk()` + Live 实时更新 Markdown
2. ~~**工具参数未显示**~~ **已完成** — `_format_tool_params()` 智能格式化 6 个内置工具参数
3. **帮助文本硬编码**：交互命令变化时需手动更新 `render_help()`
4. **主题字段未完全使用**：`system_color` 当前基本预留
5. ~~**缺少进度动画**~~ **已完成** — 统一 Live 区域显示 spinner/计划面板/流式输出
6. ~~**工具结果不显示**~~ **已完成** — `render_tool_result()` 连接符风格显示摘要
7. ~~**空内容不提示**~~ **已完成** — `render_assistant()` 检测空内容并显示提示
8. ~~**无回合统计**~~ **已完成** — `end_turn()` 输出统计行（工具次数、耗时、tokens）
9. ~~**欢迎界面信息少**~~ **已完成** — 显示模型、provider、工作目录、工具数、记忆状态
10. **可配置详细度**：未来可添加 `verbose` 模式，显示完整参数和完整输出

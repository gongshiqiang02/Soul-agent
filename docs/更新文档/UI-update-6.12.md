# UI 更新：参考 Claude Code 的终端界面优化

**更新日期**: 2026-06-12

## 📋 概览

本次更新全面改进了 Soul-agent 的终端 UI，参考 Claude Code 的设计风格，实现紧凑、信息密集、视觉清晰的交互体验。

## ✨ 主要改进

### 1. 工具调用参数可见化 ✅

**问题**: 原先 `render_tool_call` 只显示工具名称，用户看不到 Agent 在调用什么参数。

**解决方案**: 
- 格式：`● tool_name(参数摘要)`
- 针对 6 个内置工具实现智能参数格式化：
  - `read_file(path)` → `● read_file(README.md)`
  - `write_file(path, content)` → `● write_file(report.md, 1.2KB)`
  - `list_directory(path)` → `● list_directory(., recursive)`
  - `run_command(command)` → `● run_command(git log --oneline -5)`
  - `web_request(method, url)` → `● web_request(GET https://api.example.com)`
  - `search_files(pattern, path)` → `● search_files("TODO", path: src/)`
- 未知工具自动 fallback 为 `k=v` 序列，值超长自动截断

**代码位置**: `soul_agent/ui/renderer.py:69-116`

### 2. 工具结果紧凑显示 ✅

**问题**: 原先工具结果截断 300 字符后直接拼接到一行，不便阅读。

**解决方案**:
- 使用 `⎿` 连接符风格（类似 Claude Code 的 tree 连接符）
- 特殊优化 `read_file`：成功时显示 `⎿ 读取 N 行`（而非倾倒全部内容）
- 其他工具：显示前 3 行，超出显示 `… +N 行`
- 失败时红色高亮：`⎿ 错误: xxx`

**示例输出**:
```
● list_directory(.)
  ⎿ [目录] soul_agent
    [文件] README.md
    [文件] pyproject.toml
    … +8 行
```

**代码位置**: `soul_agent/ui/renderer.py:125-151`

### 3. LLM 思考状态 Spinner ✅

**问题**: LLM 调用期间终端完全静默，用户不知道 Agent 是否在工作。

**解决方案**:
- 底部显示动态 spinner：`✻ 思考中… (第 N 轮)`
- 使用 Rich Live 的 `transient=True` 模式，完成后自动消失
- 与计划面板共享统一 Live 区域，不冲突

**代码位置**: 
- `soul_agent/ui/renderer.py:208-225` (Live 内容构建)
- `soul_agent/core/agent.py:108-111` (状态回调)

### 4. 最终回复流式输出 ✅

**问题**: 原先等待 LLM 全部生成完才显示，长回复等待时间长。

**解决方案**:
- 实现完整的流式渲染：LLM 生成一块，UI 立即显示一块
- 底部 Live 区域实时显示 Markdown(缓冲 + "▌" 光标)
- 支持**带 tools 的流式调用**：
  - `OpenAIProvider._stream_chat` 重写，逐 chunk 累积 `content` 和 `tool_calls`
  - tool_calls 按 index 分组累积，流结束后统一 JSON 解析
  - 尝试获取 `stream_options.include_usage`，不支持时降级
- 工具调用前若有流式缓冲，先永久输出（保留思考过程文本）

**代码位置**:
- `soul_agent/llm/providers/openai.py:56-110` (流式实现)
- `soul_agent/ui/renderer.py:246-251` (流式回调)
- `soul_agent/core/agent.py:108-112` (接入流式)

### 5. 回合统计信息 ✅

**问题**: 无法直观看到一次对话的性能指标。

**解决方案**:
- 每轮对话结束显示统计行：`✓ 完成 · N 次工具调用 · X.Xs · Xk tokens`
- Agent 自动记录：迭代次数、工具调用次数、耗时、tokens（从 `usage` 累积）
- 防御性处理：测试环境的 MagicMock 不会导致崩溃

**代码位置**:
- `soul_agent/core/agent.py:52-59, 194-200` (统计收集)
- `soul_agent/ui/renderer.py:265-283` (统计显示)

### 6. 信息化欢迎界面 ✅

**问题**: 原先欢迎界面信息量少，用户不知道当前运行状态。

**解决方案**:
- Panel 中显示：
  - 模型名称和 provider
  - 工作目录
  - 已启用工具数量
  - 记忆系统状态
- 启动时清晰了解当前配置

**代码位置**: `soul_agent/ui/renderer.py:27-51`

## 🏗️ 架构改进

### 统一 Live 管理

**挑战**: Rich 只允许一个活动 Live 实例，计划面板、spinner、流式输出需要合并。

**方案**:
- `Renderer` 维护单一 `_live` 实例（替代原 `_plan_live`）
- `_build_live_content()` 动态组合 `Group(计划面板?, spinner/流式Markdown)`
- `begin_turn()` → 启动 Live；`end_turn()` → 停止 Live + 输出最终内容 + 统计行
- 离散事件（工具调用/结果）用 `console.print()` 自动滚动到 Live 上方

**代码位置**: `soul_agent/ui/renderer.py:208-289`

### 主题系统扩展

新增 3 个颜色 token:
- `connector_color` — `⎿` 连接符（dim）
- `success_color` — 成功提示（#00d700，工具成功圆点和统计行对勾）
- `stats_color` — 统计行（dim）

`get_theme()` 改为与 default 主题合并，确保缺失 key 不崩溃。

**代码位置**: `soul_agent/ui/themes.py`

### LLM 层改进

- `chat()` 签名新增 `on_delta` 回调参数，逐层透传
- `OpenAIProvider._stream_chat` 完整重写：
  - 支持 tools 的流式累积
  - tool_calls delta 按 index 分组，arguments 字符串拼接，流结束后解析
  - 尝试获取 usage，失败时捕获并重试
- 不影响 planner、memory summarizer 的 `stream=False` 调用

**代码位置**:
- `soul_agent/llm/providers/openai.py`
- `soul_agent/llm/client.py`

### Agent 回调扩展

- `set_callbacks()` 新增 `on_status` 参数
- `run()` 中：
  - 每轮前调用 `on_status("思考中… (第 N 轮)")`
  - LLM 调用改为 `stream=True, on_delta=self._on_stream`
  - 累积 usage.total_tokens（防御 MagicMock）
  - 记录 `last_run_stats`

**代码位置**: `soul_agent/core/agent.py`

## 📊 测试覆盖

所有现有 **76 个测试全部通过**:
- Agent 层新增 `on_stream`/`on_status` 回调对 AsyncMock 无影响
- LLM `chat()` 签名兼容（kwarg 可选）
- usage 累积做 `isinstance(int)` 防御，MagicMock 不会导致类型错误

运行结果:
```bash
$ pytest tests/ -v
76 passed in 4.66s
```

代码检查:
```bash
$ ruff check .
All checks passed!
```

## 🎯 效果对比

### 优化前
```
>>> 查看当前目录

  🔧 调用工具: list_directory
  ✅ list_directory [目录] soul_agent
[文件] README.md
[文件] pyproject.toml...

🤖 Soul-agent:
当前目录包含...
```

### 优化后
```
>>> 查看当前目录

✻ 思考中… (第 1 轮)

● list_directory(.)
  ⎿ [目录] soul_agent
    [文件] README.md
    [文件] pyproject.toml
    … +8 行

● (流式逐字显示)
当前目录包含以下内容：
- **soul_agent/** - 主程序包目录
...

✓ 完成 · 1 次工具调用 · 3.2s · 1.5k tokens
```

## 📝 修改文件列表

1. `soul_agent/ui/themes.py` — 新增 3 个颜色 token，改进 `get_theme`
2. `soul_agent/ui/renderer.py` — 核心重写（统一 Live、工具显示、流式、统计）
3. `soul_agent/llm/providers/openai.py` — 流式支持 tools + usage
4. `soul_agent/llm/client.py` — 透传 `on_delta`
5. `soul_agent/core/agent.py` — 接通回调、统计、流式
6. `soul_agent/app.py` — 接线回调、调整流程
7. 测试文件 — 自动修复 unused imports (ruff --fix)

## 🔗 参考资料

- [Claude Code 终端 UI](https://claude.ai/code)
- [Rich Live 文档](https://rich.readthedocs.io/en/stable/live.html)
- [OpenAI Streaming with Tools](https://platform.openai.com/docs/api-reference/chat/create#chat-create-stream)

## 🚀 后续增强方向

- [ ] 支持 verbose 模式配置（完整参数/输出显示）
- [ ] 添加工具调用耗时统计
- [ ] 支持工具调用失败自动重试的 UI 显示
- [ ] 添加 Ctrl+C 优雅中断（停止当前工具调用但保留历史）

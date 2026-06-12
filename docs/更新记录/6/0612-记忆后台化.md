# 记忆更新后台化：修复首轮回复后卡顿

**更新日期**: 2026-06-12

## 背景

终端中第一次回答完成后，界面会停留在类似下面的统计行附近较久：

```text
✓ 完成 · 3 次工具调用 · 60.8s · 7.1k tokens
```

用户已经看到最终回复，但程序没有马上回到下一次输入。排查后确认，`Agent.run()` 在生成最终回复后仍同步等待长期记忆维护：

1. 调用 `MemoryManager.process_turn()`。
2. 再发起一次 LLM 请求提取长期记忆。
3. 如果提取到记忆，写入 SQLite，并同步调用 ChromaDB `upsert()` 建立向量索引。

这部分属于后台维护，不应该阻塞用户可见的回答完成流程。

## 改动目标

- 最终回复生成后尽快返回给 UI。
- `renderer.end_turn()` 输出统计行后可以立即进入下一次输入。
- 长期记忆提取仍然保留，但从主响应路径移到后台任务。
- ChromaDB 的同步 API 不直接阻塞 asyncio 事件循环。

## 核心改动

### 1. Agent 后台调度长期记忆更新

`Agent.run()` 现在先完成用户可见流程：

1. 最终回复写入 `Conversation`。
2. 调度助手消息持久化。
3. 裁剪过长消息。
4. 记录 `last_run_stats`。
5. 调度后台记忆更新。
6. 返回 `final_content`。

对应代码：

```python
self._schedule_memory_update(user_input, final_content)
return final_content
```

后台任务通过 `asyncio.create_task()` 创建，并记录到 `_background_tasks` 集合。任务结束后自动移除，异常会被消费并写入日志，避免出现未处理的 task exception。

新增辅助方法：

| 方法 | 作用 |
|------|------|
| `_schedule_memory_update()` | 创建后台记忆更新任务 |
| `_process_memory_update()` | 执行 `memory.process_turn()` 并捕获异常 |
| `_consume_background_task_result()` | 消费后台任务结果，避免未处理异常 |
| `drain_background_tasks()` | 测试或退出前等待后台任务完成 |

### 2. ChromaDB 同步调用线程化

ChromaDB 的 `collection.upsert()`、`collection.delete()`、`collection.query()` 是同步 API。它们可能包含 embedding、磁盘 IO 或索引操作，直接在事件循环中执行会阻塞交互。

现在这些调用通过 `asyncio.to_thread()` 放入线程执行：

```python
await asyncio.to_thread(self._upsert_embedding, memory_id, content, metadata)
await asyncio.to_thread(self._delete_embedding, memory_id)
results = await asyncio.to_thread(self._query_collection, query, top_k)
```

同一个 `MemoryRetriever` 内部增加 `RLock`，串行化同一个 ChromaDB collection 上的 `upsert/delete/query`。

### 3. MemoryManager 适配异步向量索引

`MemoryRetriever.add_embedding()` 和 `delete_embedding()` 改为异步方法后，`MemoryManager.store()` / `forget()` 同步更新为：

```python
await self.retriever.add_embedding(...)
await self.retriever.delete_embedding(memory_id)
```

### 4. 应用入口退出路径收尾

记忆更新后台化后，如果事件循环在后台任务完成前关闭，任务会被取消、本轮记忆丢失。`app.py` 的两条退出路径补充了收尾逻辑：

- `run_chat()`：聊天循环主体拆出为 `_chat_loop()`，外层 `try/finally` 在退出时（`/quit`、`/exit` 或输入流结束）执行 `await agent.drain_background_tasks()`。
- `run_ask()`：单次模式回复输出后立即 `await agent.drain_background_tasks()`——否则 `asyncio.run()` 随即返回，记忆提取（含一次 LLM 请求）几乎必然被取消。统计行仍先于等待输出，用户体验不受影响。

## 当前记忆流程

```text
用户输入
  │
  ▼
Agent.run()
  │
  ├─ memory.retrieve(user_input)
  │    ├─ ChromaDB 向量检索（线程中执行）
  │    └─ 失败时回退 SQLite 关键词检索
  │
  ├─ 构建消息并注入记忆上下文
  ├─ ReAct 推理 / 工具调用 / 最终回复
  ├─ 最终回复写入 Conversation
  ├─ 记录 last_run_stats
  ├─ 调度后台 memory.process_turn()
  └─ 返回 final_content

后台 memory.process_turn()
  ├─ 写入 ShortTermMemory
  ├─ LLM 提取长期记忆
  ├─ importance 过滤
  ├─ SQLite 写入 memories 表
  └─ ChromaDB upsert（线程中执行）
```

## 用户体验变化

优化前：

```text
模型回复完成
  → 等待记忆提取 LLM 请求
  → 等待 ChromaDB 写入
  → 输出统计行 / 回到输入
```

优化后：

```text
模型回复完成
  → 记录统计并输出统计行
  → 立即回到输入
  → 后台继续处理长期记忆
```

## 测试覆盖

新增回归测试：

```text
tests/test_agent.py::TestAgent::test_memory_update_does_not_block_response
```

该测试构造一个会阻塞的 `SlowMemory.process_turn()`，验证 `Agent.run()` 仍能在短时间内返回最终回复。

验证结果：

```text
77 passed
ruff: All checks passed
```

## 修改文件

| 文件 | 改动 |
|------|------|
| `soul_agent/core/agent.py` | 长期记忆更新改为后台任务，新增后台任务管理方法 |
| `soul_agent/memory/retriever.py` | ChromaDB `upsert/delete/query` 改为 `asyncio.to_thread()` 执行 |
| `soul_agent/memory/manager.py` | 适配异步向量索引接口 |
| `soul_agent/app.py` | `run_chat()` / `run_ask()` 退出路径调用 `drain_background_tasks()` 收尾 |
| `tests/test_agent.py` | 新增慢记忆更新不阻塞响应的回归测试 |
| `docs/模块文档/核心模块.md` | 更新 Agent 单轮流程和后台任务说明 |
| `docs/模块文档/记忆系统.md` | 更新端到端记忆流程、ChromaDB 线程化说明 |
| `docs/API参考.md` | 更新 Agent 和 MemoryManager API 说明 |
| `docs/模块文档/应用入口模块.md` | 更新交互主循环行为说明 |
| `docs/全功能模块测试指南.md` | 更新测试覆盖描述 |

## 注意事项

- 后台记忆更新是最终一致的：刚完成的一轮对话提取出的新长期记忆，可能要到后台任务结束后才会在后续检索中出现。
- `ShortTermMemory` 也在 `process_turn()` 内更新，因此它同样跟随后台任务执行。
- 程序退出前的记忆收尾已在 `app.py` 的退出路径实现：`run_chat()` 退出聊天循环、`run_ask()` 输出回复后都会 `await agent.drain_background_tasks()`，确保所有记忆在事件循环关闭前写入。
- ChromaDB 查询仍然会影响当前回答前的记忆检索耗时，但不会阻塞事件循环；后续可继续优化为按 ID 批量读取 SQLite，减少 `_vector_search()` 中全量 `get_all()` 的开销。

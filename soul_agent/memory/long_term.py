"""长期记忆 - 跨会话持久存储"""
import uuid
import json
from datetime import datetime
from dataclasses import dataclass, field
from pathlib import Path

import aiosqlite


@dataclass
class MemoryEntry:
    id: str
    content: str
    memory_type: str  # fact/preference/event/summary
    importance: float
    created_at: datetime
    last_accessed: datetime
    access_count: int
    metadata: dict = field(default_factory=dict)
    similarity: float = 0.0  # Set during retrieval


@dataclass
class ConversationEntry:
    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int = 0


class LongTermMemory:
    def __init__(self, db_path: str):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    async def initialize(self):
        """Create tables if not exist"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.executescript('''
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    memory_type TEXT NOT NULL,
                    importance REAL DEFAULT 0.5,
                    embedding_id TEXT,
                    source_conversation_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    access_count INTEGER DEFAULT 0,
                    metadata TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_memories_type ON memories(memory_type);
                CREATE INDEX IF NOT EXISTS idx_memories_importance ON memories(importance);

                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    title TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    conversation_id TEXT REFERENCES conversations(id),
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    tool_calls TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id);
            ''')

    async def store(self, content: str, memory_type: str, importance: float = 0.5,
                    metadata: dict | None = None) -> str:
        memory_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO memories (id, content, memory_type, importance, created_at, last_accessed, access_count, metadata) VALUES (?, ?, ?, ?, ?, ?, 0, ?)",
                (memory_id, content, memory_type, importance, now, now, json.dumps(metadata or {}))
            )
            await db.commit()
        return memory_id

    async def get_all(self, memory_type: str | None = None) -> list[MemoryEntry]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            if memory_type:
                cursor = await db.execute("SELECT * FROM memories WHERE memory_type = ? ORDER BY importance DESC", (memory_type,))
            else:
                cursor = await db.execute("SELECT * FROM memories ORDER BY importance DESC")
            rows = await cursor.fetchall()
            return [self._row_to_entry(r) for r in rows]

    async def search_by_keyword(self, keyword: str, top_k: int = 10) -> list[MemoryEntry]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM memories WHERE content LIKE ? ORDER BY importance DESC LIMIT ?",
                (f"%{keyword}%", top_k)
            )
            rows = await cursor.fetchall()
            return [self._row_to_entry(r) for r in rows]

    async def update_access(self, memory_id: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE memories SET last_accessed = ?, access_count = access_count + 1 WHERE id = ?",
                (datetime.now().isoformat(), memory_id)
            )
            await db.commit()

    async def delete(self, memory_id: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
            await db.commit()

    def _row_to_entry(self, row) -> MemoryEntry:
        return MemoryEntry(
            id=row["id"],
            content=row["content"],
            memory_type=row["memory_type"],
            importance=row["importance"],
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else datetime.now(),
            last_accessed=datetime.fromisoformat(row["last_accessed"]) if row["last_accessed"] else datetime.now(),
            access_count=row["access_count"],
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
        )

    # ── Conversation CRUD ──────────────────────────────────────────

    async def create_conversation(self, title: str = "") -> str:
        """创建新会话，返回 conversation_id"""
        conv_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        display_title = title or "新对话"
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO conversations (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (conv_id, display_title, now, now),
            )
            await db.commit()
        return conv_id

    async def create_conversation_with_id(self, conversation_id: str,
                                          title: str = "") -> str:
        """使用指定 ID 创建会话（用于 Conversation 自行生成 ID 的场景）"""
        now = datetime.now().isoformat()
        display_title = title or "新对话"
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR IGNORE INTO conversations (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (conversation_id, display_title, now, now),
            )
            await db.commit()
        return conversation_id

    async def save_message(self, conversation_id: str, role: str,
                           content: str, tool_calls: str | None = None) -> str:
        """保存一条消息到指定会话，返回 message_id"""
        msg_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO messages (id, conversation_id, role, content, tool_calls, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (msg_id, conversation_id, role, content, tool_calls, now),
            )
            await db.execute(
                "UPDATE conversations SET updated_at = ? WHERE id = ?",
                (now, conversation_id),
            )
            await db.commit()
        return msg_id

    async def list_conversations(self, limit: int = 50) -> list[ConversationEntry]:
        """列出所有会话（按更新时间倒序），含消息数"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """SELECT c.id, c.title, c.created_at, c.updated_at,
                          (SELECT COUNT(*) FROM messages m WHERE m.conversation_id = c.id) as message_count
                   FROM conversations c
                   ORDER BY c.updated_at DESC
                   LIMIT ?""",
                (limit,),
            )
            rows = await cursor.fetchall()
            return [
                ConversationEntry(
                    id=row["id"],
                    title=row["title"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                    updated_at=datetime.fromisoformat(row["updated_at"]),
                    message_count=row["message_count"],
                )
                for row in rows
            ]

    async def get_conversation_messages(self, conversation_id: str) -> list[dict]:
        """获取某个会话的全部消息"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT role, content, tool_calls FROM messages WHERE conversation_id = ? ORDER BY created_at ASC",
                (conversation_id,),
            )
            rows = await cursor.fetchall()
            messages = []
            for row in rows:
                msg = {"role": row["role"], "content": row["content"]}
                if row["tool_calls"]:
                    msg["tool_calls"] = json.loads(row["tool_calls"])
                messages.append(msg)
            return messages

    async def update_conversation_title(self, conversation_id: str, title: str):
        """重命名会话"""
        now = datetime.now().isoformat()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?",
                (title, now, conversation_id),
            )
            await db.commit()

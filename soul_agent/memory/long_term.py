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

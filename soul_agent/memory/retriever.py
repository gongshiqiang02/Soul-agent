"""记忆检索器 - 混合评分检索"""
import math
from datetime import datetime

from soul_agent.utils.logger import logger
from soul_agent.memory.long_term import LongTermMemory, MemoryEntry

try:
    import chromadb
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False
    logger.warning("ChromaDB not installed, falling back to keyword search only")


class MemoryRetriever:
    """混合检索：向量相似度 + 重要性 + 时间衰减"""

    def __init__(self, long_term: LongTermMemory, vector_db_path: str | None = None):
        self.long_term = long_term
        self._collection = None
        self._chroma_client = None

        if CHROMADB_AVAILABLE:
            try:
                if vector_db_path:
                    self._chroma_client = chromadb.PersistentClient(path=vector_db_path)
                else:
                    self._chroma_client = chromadb.Client()
                self._collection = self._chroma_client.get_or_create_collection(
                    name="soul_memories",
                    metadata={"hnsw:space": "cosine"},
                )
                logger.info("ChromaDB initialized successfully")
            except Exception as e:
                logger.warning(f"Failed to initialize ChromaDB: {e}, falling back to keyword search")
                self._collection = None
                self._chroma_client = None

    @property
    def has_vector_search(self) -> bool:
        return self._collection is not None

    def add_embedding(self, memory_id: str, content: str, metadata: dict | None = None):
        """Add a memory's embedding to ChromaDB."""
        if not self.has_vector_search:
            return
        try:
            self._collection.upsert(
                ids=[memory_id],
                documents=[content],
                metadatas=[metadata or {}],
            )
        except Exception as e:
            logger.warning(f"Failed to add embedding: {e}")

    def delete_embedding(self, memory_id: str):
        """Remove a memory's embedding from ChromaDB."""
        if not self.has_vector_search:
            return
        try:
            self._collection.delete(ids=[memory_id])
        except Exception as e:
            logger.warning(f"Failed to delete embedding: {e}")

    def check_duplicate(self, content: str, threshold: float = 0.80) -> tuple[bool, str | None]:
        """通过向量相似度检查是否存在近似重复记忆。

        返回 (是否重复, 已有记忆的 ID)。
        """
        if not self.has_vector_search:
            return False, None

        try:
            results = self._collection.query(
                query_texts=[content],
                n_results=1,
            )
            if not results["ids"] or not results["ids"][0]:
                return False, None

            distance = results["distances"][0][0]
            similarity = max(0.0, 1.0 - distance)
            if similarity >= threshold:
                return True, results["ids"][0][0]
            return False, None
        except Exception as e:
            logger.warning(f"重复检查失败: {e}")
            return False, None

    async def retrieve(self, query: str, top_k: int = 5) -> list[MemoryEntry]:
        """Retrieve top-k memories using hybrid scoring."""
        candidates = await self._get_candidates(query, top_k=top_k * 3)

        if not candidates:
            return []

        # Score and rank
        scored = []
        now = datetime.now()
        for entry in candidates:
            sim = entry.similarity  # Set by vector search, or 0.5 for keyword fallback
            imp = entry.importance
            rec = self._recency_score(entry.last_accessed, now)

            final_score = sim * 0.5 + imp * 0.3 + rec * 0.2
            scored.append((final_score, entry))

        scored.sort(key=lambda x: x[0], reverse=True)

        results = []
        for _, entry in scored[:top_k]:
            await self.long_term.update_access(entry.id)
            results.append(entry)
        return results

    async def _get_candidates(self, query: str, top_k: int) -> list[MemoryEntry]:
        """Get candidate memories via vector search with keyword fallback."""
        if self.has_vector_search:
            try:
                return await self._vector_search(query, top_k)
            except Exception as e:
                logger.warning(f"Vector search failed: {e}, falling back to keyword search")

        return await self._keyword_search(query, top_k)

    async def _vector_search(self, query: str, top_k: int) -> list[MemoryEntry]:
        """Search using ChromaDB vector similarity."""
        results = self._collection.query(
            query_texts=[query],
            n_results=top_k,
        )

        if not results["ids"] or not results["ids"][0]:
            return []

        ids = results["ids"][0]
        distances = results["distances"][0] if results.get("distances") else [0.0] * len(ids)

        # ChromaDB cosine distance -> similarity (distance is 0..2 for cosine, similarity = 1 - distance/2)
        entries = []
        all_memories = await self.long_term.get_all()
        memory_map = {m.id: m for m in all_memories}

        for memory_id, distance in zip(ids, distances):
            if memory_id in memory_map:
                entry = memory_map[memory_id]
                entry.similarity = max(0.0, 1.0 - distance)
                entries.append(entry)

        return entries

    async def _keyword_search(self, query: str, top_k: int) -> list[MemoryEntry]:
        """Fallback: keyword-based search."""
        # Split query into keywords and search for each
        keywords = query.split()
        seen_ids = set()
        entries = []

        for keyword in keywords:
            if len(keyword) < 2:
                continue
            results = await self.long_term.search_by_keyword(keyword, top_k=top_k)
            for entry in results:
                if entry.id not in seen_ids:
                    entry.similarity = 0.5  # Default similarity for keyword matches
                    entries.append(entry)
                    seen_ids.add(entry.id)

        # If no keyword matches, return most important memories
        if not entries:
            all_memories = await self.long_term.get_all()
            for entry in all_memories[:top_k]:
                entry.similarity = 0.3
                entries.append(entry)

        return entries

    @staticmethod
    def _recency_score(last_accessed: datetime, now: datetime) -> float:
        """Exponential decay based on hours since last access."""
        hours_ago = (now - last_accessed).total_seconds() / 3600.0
        # Half-life of 72 hours (3 days)
        decay_rate = math.log(2) / 72.0
        return math.exp(-decay_rate * hours_ago)

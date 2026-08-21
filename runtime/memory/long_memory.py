"""
长期记忆模块（LongMemory）
==========================
跨会话的长期记忆条目库，按时间与关键词组织。

与 VectorMemory 的分工：
- VectorMemory：语义联想（"这话题跟那话题有关"）
- LongMemory：时间线回溯（"上次什么时候、当时发生了什么"）

存储：SQLite（id / content / type / metadata / timestamp）
"""

import json
import sqlite3
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import BaseMemory, MemoryItem

__all__ = ["LongMemory"]


class LongMemory(BaseMemory):
    """长期记忆库（时间线式）。"""

    def __init__(self, config: Dict) -> None:
        super().__init__(config)
        db_path = config.get("db_path", "storage/sqlite/long_memory.db")
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.max_items = int(config.get("max_items", 1000))
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self) -> None:
        with self._lock, sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS long_memory (
                    id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    type TEXT DEFAULT 'long',
                    metadata TEXT DEFAULT '{}',
                    timestamp REAL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_lm_time ON long_memory(timestamp)"
            )

    async def store(self, item: MemoryItem) -> bool:
        if not item.id:
            item.id = f"long_{uuid.uuid4().hex[:12]}"
        with self._lock, sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO long_memory
                    (id, content, type, metadata, timestamp)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    item.id,
                    item.content,
                    item.type,
                    json.dumps(item.metadata, ensure_ascii=False),
                    item.timestamp,
                ),
            )
            # 超过上限时清理最旧条目
            cur = conn.execute("SELECT COUNT(*) FROM long_memory")
            if int(cur.fetchone()[0]) > self.max_items:
                conn.execute(
                    "DELETE FROM long_memory WHERE id IN ("
                    "SELECT id FROM long_memory ORDER BY timestamp ASC LIMIT ?)",
                    (int(cur.fetchone()[0]) - self.max_items,),
                )
        return True

    async def retrieve(self, query: str = "", top_k: int = 5) -> List[MemoryItem]:
        """按时间倒序取最近记忆；有 query 时叠加关键词过滤。"""
        with self._lock, sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            if query:
                like = f"%{query}%"
                cur = conn.execute(
                    "SELECT * FROM long_memory WHERE content LIKE ? "
                    "ORDER BY timestamp DESC LIMIT ?",
                    (like, top_k),
                )
            else:
                cur = conn.execute(
                    "SELECT * FROM long_memory ORDER BY timestamp DESC LIMIT ?",
                    (top_k,),
                )
            rows = [dict(r) for r in cur.fetchall()]
        return [
            MemoryItem(
                id=r["id"],
                content=r["content"],
                type=r["type"],
                timestamp=r["timestamp"],
                metadata=json.loads(r["metadata"] or "{}"),
            )
            for r in rows
        ]

    async def delete(self, item_id: str) -> bool:
        with self._lock, sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM long_memory WHERE id = ?", (item_id,))
        return True

    async def clear(self) -> bool:
        with self._lock, sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM long_memory")
        return True

    def count(self) -> int:
        with self._lock, sqlite3.connect(self.db_path) as conn:
            cur = conn.execute("SELECT COUNT(*) FROM long_memory")
            return int(cur.fetchone()[0])

    def __repr__(self) -> str:
        return f"LongMemory(db={self.db_path}, n={self.count()})"

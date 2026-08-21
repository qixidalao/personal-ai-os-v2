"""
向量记忆模块（VectorMemory）
============================
类人脑记忆的核心：语义联想检索。

- 记忆以"语义向量"形式存储（embedding）
- 遇到新输入时，系统自动用当前语境做向量检索，捞出语义相关的历史记忆
- 整个过程模型无感：不需要 LLM 调用任何工具，记忆"自动浮现"

存储：SQLite（id / content / type / metadata / embedding / timestamp）
检索：余弦相似度 top-k（纯 Python 实现，无 numpy 依赖）

embedding 来源（注入式，可降级）：
- 优先：外部 embed_fn（如 OpenAI embeddings API）
- 降级：无 embed 时退化为字符/关键词重合度打分（保证能跑）

用法::

    from runtime.memory.vector_memory import VectorMemory
    vm = VectorMemory({"db_path": "storage/sqlite/memory.db"}, embed_fn=my_embed)
    await vm.store(MemoryItem(id="m1", content="...", type="long"))
    hits = await vm.retrieve("部署端口冲突", top_k=5)
"""

import json
import math
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from . import BaseMemory, MemoryItem

__all__ = ["VectorMemory"]

# 无 embedding 时的降级词元化
_TOKEN_CHARS = set(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_"
)


def _tokenize(text: str) -> List[str]:
    """简单中文/英文词元化（无分词库依赖）。"""
    tokens: List[str] = []
    buf = ""
    for ch in text:
        if ch in _TOKEN_CHARS:
            buf += ch
        else:
            if buf:
                tokens.append(buf.lower())
                buf = ""
            if ch.strip() and ord(ch) > 127:  # 单字 CJK 作为独立 token
                tokens.append(ch)
    if buf:
        tokens.append(buf.lower())
    return tokens


def cosine_similarity(a: List[float], b: List[float]) -> float:
    """余弦相似度（纯 Python，零依赖）。"""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


class VectorMemory(BaseMemory):
    """语义联想记忆库。"""

    def __init__(
        self,
        config: Dict,
        embed_fn: Optional[Callable[[List[str]], Any]] = None,
    ) -> None:
        super().__init__(config)
        db_path = config.get("db_path", "storage/sqlite/memory.db")
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.dimension = int(config.get("dimension", 1536))
        self.top_k = int(config.get("top_k", 5))
        self.similarity = config.get("similarity", "cosine")
        self.embed_fn = embed_fn  # async (texts) -> List[List[float]]
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self) -> None:
        with self._lock, sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS vector_memory (
                    id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    type TEXT DEFAULT 'long',
                    metadata TEXT DEFAULT '{}',
                    embedding TEXT,
                    timestamp REAL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_vm_type ON vector_memory(type)"
            )

    # ─── 写入 ────────────────────────────────────────────────
    async def store(self, item: MemoryItem) -> bool:
        """存储一条记忆，自动生成 embedding。"""
        embedding = None
        if self.embed_fn is not None and item.embedding is None:
            try:
                vectors = await self.embed_fn([item.content])
                if vectors:
                    item.embedding = list(vectors[0])
            except Exception:
                item.embedding = None  # 降级：无向量也可存
        embedding = item.embedding
        with self._lock, sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO vector_memory
                    (id, content, type, metadata, embedding, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    item.id,
                    item.content,
                    item.type,
                    json.dumps(item.metadata, ensure_ascii=False),
                    json.dumps(embedding) if embedding else None,
                    item.timestamp,
                ),
            )
        return True

    # ─── 检索（联想自取） ────────────────────────────────────
    async def retrieve(self, query: str, top_k: int = 5) -> List[MemoryItem]:
        """用查询语境联想检索最相关的记忆。

        优先向量相似度；embedding 不可用时退化为词元重合度打分。
        """
        k = top_k or self.top_k
        q_vec = None
        if self.embed_fn is not None:
            try:
                vectors = await self.embed_fn([query])
                if vectors:
                    q_vec = list(vectors[0])
            except Exception:
                q_vec = None

        rows = self._load_all()
        if not rows:
            return []

        q_tokens = _tokenize(query)
        scored: List[tuple] = []
        for row in rows:
            emb = json.loads(row["embedding"]) if row["embedding"] else None
            score = 0.0
            if q_vec is not None and emb:
                score = cosine_similarity(q_vec, emb)
            elif q_tokens:
                # 降级：词元重合率（Jaccard 风格）
                r_tokens = set(_tokenize(row["content"]))
                if r_tokens:
                    inter = len(set(q_tokens) & r_tokens)
                    union = len(set(q_tokens) | r_tokens)
                    score = inter / union if union else 0.0
            if score > 0.0:
                scored.append((score, row))

        scored.sort(key=lambda x: x[0], reverse=True)
        items: List[MemoryItem] = []
        for score, row in scored[:k]:
            items.append(
                MemoryItem(
                    id=row["id"],
                    content=row["content"],
                    type=row["type"],
                    timestamp=row["timestamp"],
                    metadata=json.loads(row["metadata"] or "{}"),
                    score=score,
                )
            )
        return items

    # ─── 其他 ────────────────────────────────────────────────
    def _load_all(self) -> List[Dict]:
        with self._lock, sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.execute(
                "SELECT * FROM vector_memory ORDER BY timestamp DESC LIMIT 5000"
            )
            return [dict(r) for r in cur.fetchall()]

    async def delete(self, item_id: str) -> bool:
        with self._lock, sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM vector_memory WHERE id = ?", (item_id,))
        return True

    async def clear(self) -> bool:
        with self._lock, sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM vector_memory")
        return True

    def count(self) -> int:
        with self._lock, sqlite3.connect(self.db_path) as conn:
            cur = conn.execute("SELECT COUNT(*) FROM vector_memory")
            return int(cur.fetchone()[0])

    def __repr__(self) -> str:
        return f"VectorMemory(db={self.db_path}, dim={self.dimension}, n={self.count()})"

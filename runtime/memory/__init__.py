"""
Memory 运行时 — 多级记忆系统
SessionMemory / ConversationSummary / LongMemory / VectorMemory / FactMemory
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from datetime import datetime
import json


@dataclass
class MemoryItem:
    """记忆项"""
    id: str
    content: str
    type: str  # session / summary / long / vector / fact
    timestamp: float = field(default_factory=lambda: datetime.now().timestamp())
    metadata: Dict = field(default_factory=dict)
    embedding: Optional[List[float]] = None
    score: float = 0.0


class BaseMemory:
    """记忆基类"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.enabled = config.get("enabled", True)
    
    async def store(self, item: MemoryItem) -> bool:
        raise NotImplementedError
    
    async def retrieve(self, query: str, top_k: int = 5) -> List[MemoryItem]:
        raise NotImplementedError
    
    async def delete(self, item_id: str) -> bool:
        raise NotImplementedError
    
    async def clear(self) -> bool:
        raise NotImplementedError


class SessionMemory(BaseMemory):
    """会话记忆 — 短期上下文"""
    
    def __init__(self, config: Dict):
        super().__init__(config)
        self.max_messages = config.get("max_messages", 100)
        self._messages: List[Dict] = []
    
    async def store(self, item: MemoryItem) -> bool:
        self._messages.append({
            "role": item.metadata.get("role", "user"),
            "content": item.content,
            "timestamp": item.timestamp,
        })
        # 超出限制时丢弃最早的
        if len(self._messages) > self.max_messages:
            self._messages = self._messages[-self.max_messages:]
        return True
    
    async def retrieve(self, query: str = "", top_k: int = 0) -> List[MemoryItem]:
        # SessionMemory 返回全部消息（最多 max_messages）
        items = []
        for msg in self._messages[-self.max_messages:]:
            items.append(MemoryItem(
                id=f"session_{msg['timestamp']}",
                content=msg["content"],
                type="session",
                timestamp=msg["timestamp"],
                metadata={"role": msg["role"]},
            ))
        return items
    
    async def get_messages(self) -> List[Dict]:
        """获取所有消息"""
        return self._messages
    
    async def clear(self) -> bool:
        self._messages.clear()
        return True

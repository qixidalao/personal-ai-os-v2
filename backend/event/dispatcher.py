"""
事件分发器 — 将事件转化为 SSE 流输出
"""
import asyncio
import json
from typing import Any, AsyncGenerator, Optional
from backend.event.event_bus import EventBus, Event


class EventDispatcher:
    """事件分发器 — 将事件流转为 SSE 格式"""

    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self._filters: list = []
        self._event_types: set = set()

    def add_filter(self, event_type: str):
        """添加要分发的 event type"""
        self._event_types.add(event_type)

    def remove_filter(self, event_type: str):
        """移除 event type"""
        self._event_types.discard(event_type)

    def set_types(self, event_types: list):
        """设置要分发的 event types"""
        self._event_types = set(event_types)

    def should_dispatch(self, event: Event) -> bool:
        """检查事件是否需要分发"""
        if not self._event_types:
            return True  # 无过滤时全量分发
        return event.type in self._event_types

    async def dispatch(self, event: Event) -> Optional[str]:
        """将单个事件编码为 SSE 行"""
        if not self.should_dispatch(event):
            return None

        data = {
            "event": event.type,
            "id": event.id,
            "timestamp": event.timestamp,
            "data": event.data,
            "source": event.source,
            "metadata": event.metadata,
        }

        return f"event: {event.type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

    async def stream(self) -> AsyncGenerator[str, None]:
        """持续分发事件流"""
        queue = asyncio.Queue()
        
        async def handler(event: Event):
            if self.should_dispatch(event):
                await queue.put(event)

        self.event_bus.subscribe("*", handler)

        try:
            while True:
                event = await queue.get()
                sse = await self.dispatch(event)
                if sse:
                    yield sse
        except asyncio.CancelledError:
            pass
        finally:
            self.event_bus.unsubscribe("*", handler)

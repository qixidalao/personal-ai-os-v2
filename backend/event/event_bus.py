"""
事件总线 — 万物皆事件的核心引擎
支持异步发布/订阅、事件过滤、优先级
"""
import asyncio
import inspect
import time
import uuid
from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum


class EventPriority(Enum):
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


@dataclass
class Event:
    """统一事件对象"""

    type: str
    data: Any = None
    source: str = ""
    timestamp: float = field(default_factory=time.time)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    priority: EventPriority = EventPriority.NORMAL
    metadata: Dict = field(default_factory=dict)


class EventBus:
    """异步事件总线 — 系统的神经中枢"""

    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = {}
        self._history: List[Event] = []
        self._max_history = 1000
        self._filters: Dict[str, List[Callable]] = {}

    async def emit(self, event_type: str, data: Any = None, **kwargs) -> Event:
        """发布事件"""
        event = Event(type=event_type, data=data, **kwargs)

        self._history.append(event)
        if len(self._history) > self._max_history:
            self._history.pop(0)

        subscribers = (
            self._subscribers.get(event_type, [])
            + self._subscribers.get("*", [])
        )
        if not subscribers:
            return event

        tasks = []
        for subscriber in subscribers:
            if self._should_filter(event_type, event):
                continue
            tasks.append(self._safe_dispatch(subscriber, event))

        await asyncio.gather(*tasks)
        return event

    def on(self, event_type: str):
        """装饰器方式订阅事件"""

        def decorator(func):
            self.subscribe(event_type, func)
            return func

        return decorator

    def subscribe(self, event_type: str, callback: Callable):
        """订阅事件"""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(callback)

    def unsubscribe(self, event_type: str, callback: Callable):
        """取消订阅事件"""
        if event_type in self._subscribers:
            self._subscribers[event_type].remove(callback)

    def add_filter(self, event_type: str, filter_func: Callable):
        """添加事件过滤器"""
        if event_type not in self._filters:
            self._filters[event_type] = []
        self._filters[event_type].append(filter_func)

    def get_history(
        self,
        event_type: Optional[str] = None,
        limit: int = 50,
    ) -> List[Event]:
        """获取事件历史"""
        if event_type:
            return [e for e in self._history[-limit:] if e.type == event_type]
        return self._history[-limit:]

    def clear_history(self):
        """清空历史"""
        self._history.clear()

    def _should_filter(self, event_type: str, event: Event) -> bool:
        """检查是否应该过滤该事件"""
        filters = self._filters.get(event_type, []) + self._filters.get("*", [])
        return any(filter_func(event) for filter_func in filters)

    async def _safe_dispatch(self, callback: Callable, event: Event):
        """安全派发事件"""
        try:
            if inspect.iscoroutinefunction(callback):
                await callback(event)
            else:
                callback(event)
        except Exception as exc:
            # 派发异常不中断主流程。
            await self.emit(
                "error",
                {
                    "source": "event_bus.dispatch",
                    "error": str(exc),
                    "event_type": event.type,
                },
            )

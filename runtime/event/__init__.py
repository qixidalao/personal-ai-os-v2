"""
Event 运行时 — 事件驱动引擎
事件总线、事件分发器、流编码器/解码器
"""
# 引用 backend/event 中的实现
from backend.event import EventBus, Event, EventDispatcher, StreamEncoder, StreamDecoder

__all__ = ["EventBus", "Event", "EventDispatcher", "StreamEncoder", "StreamDecoder"]

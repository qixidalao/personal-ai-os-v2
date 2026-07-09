"""
Event 模块 — 万物皆事件的核心实现
包含 EventBus、Dispatcher、StreamEncoder/Decoder
"""
from backend.event.event_bus import EventBus, Event
from backend.event.dispatcher import EventDispatcher
from backend.event.stream_encoder import StreamEncoder
from backend.event.stream_decoder import StreamDecoder

__all__ = ["EventBus", "Event", "EventDispatcher", "StreamEncoder", "StreamDecoder"]

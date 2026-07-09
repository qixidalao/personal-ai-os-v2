"""
Stream 编码器 — 将事件编码为五流格式
五流：System / Thinking / Tool / Observation / Answer
"""
import json
from typing import Any, AsyncGenerator, Optional
from backend.event.event_bus import Event


class StreamEncoder:
    """
    SSE 流编码器
    将所有事件编码为统一的 SSE 协议格式
    """

    # 事件类型到流类型的映射
    STREAM_TYPE_MAP = {
        "system.*": "system",
        "thinking.*": "thinking",
        "tool.*": "tool",
        "observation": "observation",
        "rag.retrieve": "observation",
        "memory.*": "system",
        "message.assistant": "answer",
        "message.user": "system",
        "error": "system",
        "warning": "system",
        "info": "system",
    }

    @classmethod
    def encode(cls, event_type: str, data: Any = None, **kwargs) -> str:
        """编码为 SSE 格式"""
        lines = []
        lines.append(f"event: {event_type}")
        if data is not None:
            lines.append(f"data: {json.dumps(data, ensure_ascii=False)}")
        lines.append("")
        return "\n".join(lines)

    @classmethod
    def encode_delta(cls, event_type: str, content: str, done: bool = False) -> str:
        """编码增量内容"""
        payload = {
            "content": content,
            "done": done,
        }
        return cls.encode(event_type, payload)

    @classmethod
    def get_stream_type(cls, event_type: str) -> str:
        """获取事件对应的流类型"""
        for pattern, stream_type in cls.STREAM_TYPE_MAP.items():
            if pattern.endswith("*"):
                if event_type.startswith(pattern[:-1]):
                    return stream_type
            elif event_type == pattern:
                return stream_type
        return "system"  # 默认

    @classmethod
    def encode_message(cls, role: str, content: str, **metadata) -> str:
        """编码完整消息"""
        payload = {
            "role": role,
            "content": content,
            **metadata
        }
        return cls.encode(f"message.{role}", payload)

    @classmethod
    async def stream_generator(cls, events) -> AsyncGenerator[str, None]:
        """流式生成 SSE 事件"""
        async for event in events:
            if isinstance(event, str):
                yield cls.encode("message.assistant", {"content": event})
            else:
                yield cls.encode(event.type, event.data)

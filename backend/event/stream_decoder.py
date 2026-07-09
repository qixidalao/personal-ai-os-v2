"""
Stream 解码器 — 将 SSE 流解析为事件
"""
import json
from typing import Any, AsyncGenerator, Dict, Optional
from backend.event.event_bus import Event


class StreamDecoder:
    """
    SSE 流解码器
    将 Server-Sent Events 原始数据解析为结构化事件
    """

    @classmethod
    def decode_line(cls, line: str) -> Optional[Dict]:
        """解码单行 SSE 数据"""
        line = line.strip()
        if not line:
            return None

        if line.startswith("event:"):
            return {"type": "event", "value": line[6:].strip()}
        elif line.startswith("data:"):
            raw = line[5:].strip()
            try:
                return {"type": "data", "value": json.loads(raw)}
            except json.JSONDecodeError:
                return {"type": "text", "value": raw}
        elif line.startswith("id:"):
            return {"type": "id", "value": line[3:].strip()}
        elif line.startswith("retry:"):
            return {"type": "retry", "value": int(line[6:].strip())}

        return None

    @classmethod
    def decode_event(cls, event_type: str, data_str: str) -> Event:
        """将 SSE event 行解码为 Event 对象"""
        try:
            data = json.loads(data_str)
        except json.JSONDecodeError:
            data = {"content": data_str}

        return Event(
            type=event_type,
            data=data,
            source="stream",
        )

    @classmethod
    async def decode_stream(cls, raw_stream) -> AsyncGenerator[Event, None]:
        """解码完整的 SSE 流"""
        current_event = None
        current_data = []

        async for line in raw_stream:
            if line.startswith("event:"):
                # 保存上一个事件
                if current_event and current_data:
                    yield cls.decode_event(
                        current_event,
                        "\n".join(current_data)
                    )
                current_event = line[6:].strip()
                current_data = []
            elif line.startswith("data:"):
                current_data.append(line[5:].strip())
            elif line.strip() == "":
                # 空行 = 事件结束
                if current_event and current_data:
                    yield cls.decode_event(
                        current_event,
                        "\n".join(current_data)
                    )
                    current_event = None
                    current_data = []

        # 最后的事件
        if current_event and current_data:
            yield cls.decode_event(
                current_event,
                "\n".join(current_data)
            )

    @classmethod
    def parse_messages(cls, events: list) -> list:
        """解析事件列表为消息列表"""
        messages = []
        for event in events:
            if event.type.startswith("message."):
                role = event.type.split(".")[1]
                content = event.data.get("content", "") if isinstance(event.data, dict) else str(event.data)
                messages.append({
                    "role": role,
                    "content": content,
                })
        return messages

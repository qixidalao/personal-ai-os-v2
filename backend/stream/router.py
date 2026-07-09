"""
SSE Stream 路由 — 统一事件流出口
"""
import asyncio
import json
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse

router = APIRouter()


@router.get("/chat")
async def stream_chat(request: Request):
    """对话 SSE 流"""
    event_bus = request.app.state.event_bus

    async def event_generator():
        queue = asyncio.Queue()

        async def handler(event):
            await queue.put(event)

        event_bus.subscribe("*", handler)
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30)
                    sse_data = {
                        "event": event.type,
                        "data": event.data,
                        "id": event.id,
                        "timestamp": event.timestamp,
                    }
                    yield f"event: {event.type}\ndata: {json.dumps(sse_data, ensure_ascii=False)}\n\n"
                except asyncio.TimeoutError:
                    yield f": keepalive\n\n"  # SSE keepalive
        finally:
            event_bus.unsubscribe("*", handler)

    return EventSourceResponse(event_generator())


@router.get("/events")
async def stream_events(request: Request):
    """全部事件流"""
    return await stream_chat(request)


@router.get("/thinking")
async def stream_thinking(request: Request):
    """Thinking 事件流"""
    event_bus = request.app.state.event_bus

    async def event_generator():
        queue = asyncio.Queue()

        async def handler(event):
            if event.type.startswith("thinking."):
                await queue.put(event)

        event_bus.subscribe("*", handler)
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30)
                    yield f"event: {event.type}\ndata: {json.dumps(event.data, ensure_ascii=False)}\n\n"
                except asyncio.TimeoutError:
                    yield f": keepalive\n\n"
        finally:
            event_bus.unsubscribe("*", handler)

    return EventSourceResponse(event_generator())

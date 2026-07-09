# WebSocket 模块
from fastapi import APIRouter

router = APIRouter()


@router.websocket("/chat")
async def websocket_chat(websocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(f"Echo: {data}")
    except Exception:
        pass
    finally:
        await websocket.close()

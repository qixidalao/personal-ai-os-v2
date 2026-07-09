"""
OneBot 11 协议适配器 — QQ 机器人接入层
让 NapCat 通过反向 WebSocket 连接 hhs，实现 QQ ↔ AI 互通
"""
from backend.onebot.adapter import router, register_event_handlers, OneBotChatWorker

__all__ = ["router", "register_event_handlers", "OneBotChatWorker"]

"""
OneBot 11 协议适配器核心
- 反向 WebSocket 服务端（NapCat 主动连接 hhs）
- 接收 QQ 消息 → 转为 EventBus 事件
- 监听 EventBus 回复 → 发送 QQ 消息
"""
import asyncio
import json
import time
import uuid
from typing import Any, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from loguru import logger

from backend.event import EventBus

# ─── 路由器 ─────────────────────────────────────────────
router = APIRouter()

# ─── 全局状态 ───────────────────────────────────────────
_event_bus: Optional[EventBus] = None  # 在 register_event_handlers 时注入
_active_connections: dict[int, WebSocket] = {}  # qq_id → ws
_active_groups: dict[int, WebSocket] = {}        # group_id → ws (取最新连接)


# ═══════════════════════════════════════════════════════════
# OneBot 工具函数
# ═══════════════════════════════════════════════════════════

def _build_send_msg(action: str, params: dict) -> str:
    """构建 OneBot API 调用 JSON"""
    return json.dumps({
        "action": action,
        "params": params,
        "echo": str(uuid.uuid4()),
    })


async def send_private_msg(ws: WebSocket, user_id: int, message: str):
    """发送私聊消息"""
    await ws.send_text(_build_send_msg("send_private_msg", {
        "user_id": user_id,
        "message": message,
    }))


async def send_group_msg(ws: WebSocket, group_id: int, message: str):
    """发送群消息"""
    await ws.send_text(_build_send_msg("send_group_msg", {
        "group_id": group_id,
        "message": message,
    }))


def _parse_onebot_event(raw: str) -> Optional[dict]:
    """解析 OneBot 事件 JSON"""
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.warning(f"[OneBot] 收到非法 JSON: {raw[:200]}")
        return None


def _extract_message_text(event: dict) -> str:
    """从 OneBot 事件中提取纯文本消息（支持 CQ 码和 Array 格式）"""
    msg = event.get("message", "")
    if isinstance(msg, list):
        # Array 格式：提取所有 text 段
        texts = []
        for seg in msg:
            if isinstance(seg, dict) and seg.get("type") == "text":
                texts.append(seg.get("data", {}).get("text", ""))
        return "".join(texts).strip()
    if isinstance(msg, str):
        # 字符串格式：直接返回
        return msg.strip()
    return str(msg).strip()


# ═══════════════════════════════════════════════════════════
# WebSocket 端点 — NapCat 反向连接入口
# ═══════════════════════════════════════════════════════════

@router.websocket("/ws/onebot")
async def onebot_ws(websocket: WebSocket):
    """
    NapCat 反向 WebSocket 连接端点
    配置 NapCat 的 反向 WebSocket 地址为 ws://hhs_host:8080/ws/onebot
    """
    await websocket.accept()
    logger.info("[OneBot] 🟢 NapCat 反向 WS 已连接")

    # 当前连接的绑定信息
    bot_qq: Optional[int] = None

    try:
        while True:
            raw = await websocket.receive_text()
            event = _parse_onebot_event(raw)
            if not event:
                continue

            post_type = event.get("post_type", "")

            # ─── 处理心跳 ───────────────────────────
            if post_type == "meta_event" and event.get("meta_event_type") == "heartbeat":
                status = event.get("status", {})
                if status.get("online"):
                    logger.debug("[OneBot] ❤️ 心跳正常")
                continue

            # ─── 处理生命周期 ───────────────────────
            if post_type == "meta_event" and event.get("meta_event_type") == "lifecycle":
                logger.info(f"[OneBot] 🔄 NapCat 生命周期事件: {event.get('sub_type', 'connect')}")
                continue

            # ─── 获取机器人 QQ ─────────────────────
            if "self_id" in event:
                bot_qq = event["self_id"]
                logger.info(f"[OneBot] 🤖 机器人 QQ: {bot_qq}")

            # ─── 处理消息 ───────────────────────────
            if post_type == "message":
                await _handle_message(websocket, event)

    except WebSocketDisconnect:
        logger.warning("[OneBot] 🔴 NapCat 反向 WS 已断开")
    except Exception as e:
        logger.error(f"[OneBot] ⚠️ WS 异常: {e}")
    finally:
        # 清理连接记录
        for uid, ws in list(_active_connections.items()):
            if ws == websocket:
                del _active_connections[uid]
        for gid, ws in list(_active_groups.items()):
            if ws == websocket:
                del _active_groups[gid]
        try:
            await websocket.close()
        except Exception:
            pass
        logger.info("[OneBot] 连接已清理")


# ═══════════════════════════════════════════════════════════
# 消息处理
# ═══════════════════════════════════════════════════════════

async def _handle_message(ws: WebSocket, event: dict):
    """处理收到的 QQ 消息"""
    msg_type = event.get("message_type", "")
    user_id = event.get("user_id", 0)
async def _handle_message(ws: WebSocket, event: dict):
    """处理收到的 QQ 消息"""
    msg_type = event.get("message_type", "")
    user_id = event.get("user_id", 0)
    group_id = event.get("group_id", 0)
    raw_message = event.get("raw_message", "")
    text = _extract_message_text(event)
    self_id = event.get("self_id", 0)

    if not text:
        return

    # 注册连接（用于后续主动发送）
    if user_id:
        _active_connections[user_id] = ws
    if group_id:
        _active_groups[group_id] = ws

    logger.info(f"[OneBot] 💬 {'群' if msg_type == 'group' else '私'}聊 "
                f"<{user_id}>: {text[:60]}")

    # 通过 EventBus 派发消息事件
    if _event_bus:
        await _event_bus.emit("onebot.message", {
            "ws": ws,
            "msg_type": msg_type,
            "user_id": user_id,
            "group_id": group_id,
            "self_id": self_id,
            "text": text,
            "raw": raw_message,
            "event": event,
        })
    else:
        logger.warning("[OneBot] EventBus 未就绪，消息无法处理")
    return None


# ═══════════════════════════════════════════════════════════
# 事件总线订阅 — 将 AI 回复发回 QQ
# ═══════════════════════════════════════════════════════════

def register_event_handlers(event_bus: EventBus):
    """注册 OneBot 相关的事件处理器到 EventBus"""
    global _event_bus
    _event_bus = event_bus  # 保存引用，供 WebSocket 处理器使用

    @event_bus.on("onebot.send.private")
    async def _send_private(event):
        """发送私聊消息"""
        data = event.data
        ws = data.get("ws")
        user_id = data.get("user_id")
        message = data.get("message", "")
        if ws and user_id and message:
            await send_private_msg(ws, user_id, message)

    @event_bus.on("onebot.send.group")
    async def _send_group(event):
        """发送群消息"""
        data = event.data
        ws = data.get("ws")
        group_id = data.get("group_id")
        message = data.get("message", "")
        if ws and group_id and message:
            await send_group_msg(ws, group_id, message)

    @event_bus.on("onebot.message")
    async def _on_qq_message(event):
        """
        收到 QQ 消息 → 调用 AI 对话 → 回复
        这是最核心的流程：QQ消息 → AI思考 → 回复QQ
        """
        data = event.data
        ws = data["ws"]
        msg_type = data["msg_type"]
        user_id = data["user_id"]
        group_id = data["group_id"]
        text = data["text"]

        # 构造 AI 对话（实际 AI 调用由 chat_worker 处理）
        await event_bus.emit("onebot.ai_request", {
            "ws": ws,
            "msg_type": msg_type,
            "user_id": user_id,
            "group_id": group_id,
            "text": text,
            "source": "onebot",
        })

    logger.info("[OneBot] ✅ 事件处理器已注册")


# ═══════════════════════════════════════════════════════════
# AI 对话工作器 — 真正调用 LLM 并回复
# ═══════════════════════════════════════════════════════════

class OneBotChatWorker:
    """
    QQ 消息 AI 对话工作器
    订阅 onebot.ai_request 事件 → 调用 LLM → 发回 QQ
    """

    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        # 会话记忆 { session_key: [messages] }
        self.sessions: dict[str, list[dict]] = {}
        self.max_history = 20

    async def start(self):
        """启动监听"""
        self.event_bus.subscribe("onebot.ai_request", self._handle_ai_request)
        logger.info("[OneBotChat] 🤖 AI 对话工作器已启动")

    async def _handle_ai_request(self, event):
        """处理 AI 请求"""
        data = event.data
        ws = data["ws"]
        msg_type = data["msg_type"]
        user_id = data["user_id"]
        group_id = data["group_id"]
        text = data["text"]

        # 会话 key：群聊用 group_id，私聊用 user_id
        session_key = f"qq_{msg_type}_{group_id or user_id}"

        # 维护对话历史
        if session_key not in self.sessions:
            self.sessions[session_key] = []
        history = self.sessions[session_key]
        history.append({"role": "user", "content": text})
        if len(history) > self.max_history:
            history.pop(0)

        # 获取系统提示和设置
        system_prompt = "你是一个智能AI助手，请友好地回答用户的问题。"
        settings = self._load_settings()
        if "systemPrompt" in settings:
            system_prompt = settings["systemPrompt"]

        # 准备 messages
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history)

        # 调用 LLM
        try:
            reply = await self._call_llm(messages, settings)
            history.append({"role": "assistant", "content": reply})

            # 回复 QQ
            if msg_type == "group":
                await send_group_msg(ws, group_id, reply)
                logger.info(f"[OneBotChat] ↪️ 群 {group_id}: {reply[:60]}")
            else:
                await send_private_msg(ws, user_id, reply)
                logger.info(f"[OneBotChat] ↪️ 私聊 {user_id}: {reply[:60]}")
        except Exception as e:
            error_msg = f"😅 AI 思考时出了点小差，等会儿再问我吧~"
            logger.error(f"[OneBotChat] ❌ AI 调用失败: {e}")
            if msg_type == "group":
                await send_group_msg(ws, group_id, error_msg)
            else:
                await send_private_msg(ws, user_id, error_msg)

    async def _call_llm(self, messages: list[dict], settings: dict) -> str:
        """调用 LLM API"""
        import httpx

        base_url = settings.get("baseUrl", "").rstrip("/")
        api_key = settings.get("apiKey", "")
        model = settings.get("model", "gpt-3.5-turbo")
        temperature = settings.get("temperature", 0.7)
        max_tokens = settings.get("maxTokens", 2048)

        if not base_url:
            # 尝试从 settings.json 读取
            settings_full = self._load_full_settings()
            provider = settings_full.get("provider", {})
            base_url = provider.get("baseUrl", "http://localhost:11434/v1")
            api_key = provider.get("apiKey", "")
            model = provider.get("model", "gpt-3.5-turbo")

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}" if api_key else "",
        }

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{base_url}/chat/completions",
                headers=headers,
                json=payload,
            )
            resp.raise_for_status()
            result = resp.json()
            return result["choices"][0]["message"]["content"]

    def _load_settings(self) -> dict:
        """加载轻量设置"""
        return self._load_full_settings()

    def _load_full_settings(self) -> dict:
        """从 settings.json 加载完整配置"""
        try:
            from pathlib import Path
            import json
            path = Path("storage/settings.json")
            if path.exists():
                return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
        return {}

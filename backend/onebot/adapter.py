"""
OneBot 11 协议适配器核心
- 反向 WebSocket 服务端（NapCat 主动连接 hhs）
- 接收 QQ 消息 → 转为 EventBus 事件
- 监听 EventBus 回复 → 发送 QQ 消息
"""
import asyncio
import base64
import json
import mimetypes
import os
import re
import secrets
import time
import uuid
from pathlib import Path
from typing import Any, Optional
from urllib.parse import unquote

from fastapi import APIRouter, Header, HTTPException, WebSocket, WebSocketDisconnect
from loguru import logger
from pydantic import BaseModel

from backend.event import EventBus

# ─── 路由器 ─────────────────────────────────────────────
router = APIRouter()

# ─── 全局状态 ───────────────────────────────────────────
_event_bus: Optional[EventBus] = None
_active_connections: dict[int, WebSocket] = {}
_active_groups: dict[int, WebSocket] = {}
_napcat_ws: Optional[WebSocket] = None
_chat_worker: Optional["OneBotChatWorker"] = None


# ═══════════════════════════════════════════════════════════
# OneBot 工具函数
# ═══════════════════════════════════════════════════════════

def _build_send_msg(action: str, params: dict) -> str:
    return json.dumps({
        "action": action,
        "params": params,
        "echo": str(uuid.uuid4()),
    })


async def send_private_msg(ws: WebSocket, user_id: int, message: str | list, reply_to: str = ""):
    msg = message
    if reply_to:
        msg = [{"type": "reply", "data": {"id": reply_to}}]
        if isinstance(message, str):
            msg.append({"type": "text", "data": {"text": message}})
        elif isinstance(message, list):
            msg.extend(message)
    await ws.send_text(_build_send_msg("send_private_msg", {
        "user_id": user_id,
        "message": msg,
    }))


async def send_group_msg(ws: WebSocket, group_id: int, message: str | list, reply_to: str = ""):
    msg = message
    if reply_to:
        msg = [{"type": "reply", "data": {"id": reply_to}}]
        if isinstance(message, str):
            msg.append({"type": "text", "data": {"text": message}})
        elif isinstance(message, list):
            msg.extend(message)
    await ws.send_text(_build_send_msg("send_group_msg", {
        "group_id": group_id,
        "message": msg,
    }))


def _is_at_bot(event: dict, self_id: int) -> bool:
    """检查群消息中是否 @ 了机器人"""
    message = event.get("message", [])
    if not isinstance(message, list):
        return False
    for seg in message:
        if not isinstance(seg, dict):
            continue
        if seg.get("type") == "at":
            qq = seg.get("data", {}).get("qq", "")
            if str(qq) == str(self_id) or qq == "all":
                return True
    return False


def _parse_onebot_event(raw: str) -> Optional[dict]:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.warning(f"[OneBot] 收到非法 JSON: {raw[:200]}")
        return None


def _extract_message_text(event: dict) -> str:
    msg = event.get("message", "")
    if isinstance(msg, list):
        parts = []
        for seg in msg:
            if not isinstance(seg, dict):
                continue
            seg_type = seg.get("type", "")
            data = seg.get("data", {}) or {}
            if seg_type == "text":
                parts.append(data.get("text", ""))
            elif seg_type == "face":
                from tools.qq_face_map import get_face_name
                face_name = get_face_name(int(data.get("id", 0)))
                parts.append(f"[QQ表情:{face_name}]")
                parts.append(f"[QQ表情:{data.get('id', '')}]")
            elif seg_type in ("mface", "image"):
                summary = data.get("summary") or data.get("name") or data.get("emoji_id") or data.get("file_id") or ""
                parts.append(f"[表情包:{summary}]")
            elif seg_type == "reply":
                continue
            elif seg_type == "at":
                continue
            else:
                parts.append(f"[{seg_type}消息]")
        return " ".join(p.strip() for p in parts if p and p.strip()).strip()
    if isinstance(msg, str):
        raw = event.get("raw_message") or msg
        return str(raw).strip()
    return str(msg).strip()


def _windows_file_to_data_url(value: str) -> str | None:
    """把 QQ 提供的 Windows 本地图片路径转换成模型可读的 data URL。"""
    raw = unquote(value or "").replace("file://", "", 1)
    match = re.match(r"^/?([A-Za-z]):[\\/](.*)$", raw)
    if not match:
        return None
    drive, rest = match.groups()
    path = Path(f"/mnt/{drive.lower()}") / Path(rest.replace("\\", "/"))
    try:
        if not path.is_file() or path.stat().st_size > 10 * 1024 * 1024:
            return None
        mime = mimetypes.guess_type(path.name)[0] or "image/jpeg"
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        return f"data:{mime};base64,{encoded}"
    except OSError:
        return None


def _extract_image_urls(event: dict) -> list[str]:
    """提取普通图片、截图和表情图片；优先公网 URL，兼容 QQ 的 file:// 路径。"""
    message = event.get("message", [])
    if not isinstance(message, list):
        return []
    images: list[str] = []
    for segment in message:
        if not isinstance(segment, dict) or segment.get("type") not in ("image", "mface"):
            continue
        data = segment.get("data", {}) or {}
        candidates = [data.get("url"), data.get("file"), data.get("path")]
        selected = None
        for candidate in candidates:
            if isinstance(candidate, str) and candidate.startswith(("https://", "http://")):
                selected = candidate
                break
        if not selected:
            for candidate in candidates:
                if not isinstance(candidate, str):
                    continue
                selected = _windows_file_to_data_url(candidate)
                if selected:
                    break
        if selected and selected not in images:
            images.append(selected)
    return images[:4]



# ═══════════════════════════════════════════════════════════
# WebSocket 端点 — NapCat 反向连接入口
# ═══════════════════════════════════════════════════════════

@router.websocket("/ws/onebot")
async def onebot_ws(websocket: WebSocket):
    await websocket.accept()
    global _napcat_ws
    _napcat_ws = websocket
    logger.info("[OneBot] 🟢 NapCat 反向 WS 已连接")

    bot_qq: Optional[int] = None

    try:
        while True:
            raw = await websocket.receive_text()
            event = _parse_onebot_event(raw)
            if not event:
                continue

            post_type = event.get("post_type", "")

            # 心跳
            if post_type == "meta_event" and event.get("meta_event_type") == "heartbeat":
                continue

            # 生命周期
            if post_type == "meta_event" and event.get("meta_event_type") == "lifecycle":
                logger.info(f"[OneBot] 🔄 NapCat 生命周期事件: {event.get('sub_type', 'connect')}")
                continue

            # 获取机器人 QQ
            if "self_id" in event:
                bot_qq = event["self_id"]
                logger.info(f"[OneBot] 🤖 机器人 QQ: {bot_qq}")

            # 处理消息
            if post_type == "message":
                await _handle_message(websocket, event)

            # 处理撤回通知
            if post_type == "notice":
                notice_type = event.get("notice_type", "")
                if notice_type in ("friend_recall", "group_recall"):
                    mid = event.get("message_id", "")
                    uid = event.get("user_id", 0)
                    gid = event.get("group_id", 0)
                    logger.info(f"[OneBot] ↩️ 撤回: msg={mid}")
                    if _chat_worker:
                        asyncio.create_task(_chat_worker.remove_from_context(mid, uid, gid))
    except WebSocketDisconnect:
        logger.warning("[OneBot] 🔴 NapCat 反向 WS 已断开")
    except Exception as e:
        logger.error(f"[OneBot] ⚠️ WS 异常: {e}")
    finally:
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


class HotkeyScreenshotRequest(BaseModel):
    image_base64: str


@router.post("/api/v1/onebot/hotkey-screenshot")
async def send_hotkey_screenshot(
    payload: HotkeyScreenshotRequest,
    x_hotkey_token: str = Header(default=""),
):
    """Send a locally captured screenshot through the active NapCat connection."""
    expected_token = os.getenv("HHS_SCREENSHOT_HOTKEY_TOKEN", "")
    recipient = os.getenv("HHS_SCREENSHOT_RECIPIENT", "")
    if not expected_token or not secrets.compare_digest(x_hotkey_token, expected_token):
        raise HTTPException(status_code=401, detail="invalid hotkey token")
    if not recipient.isdigit():
        raise HTTPException(status_code=503, detail="screenshot recipient is not configured")
    if _napcat_ws is None:
        raise HTTPException(status_code=503, detail="NapCat is not connected")
    if len(payload.image_base64) > 12 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="screenshot is too large")
    try:
        base64.b64decode(payload.image_base64, validate=True)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid screenshot encoding") from exc

    await send_private_msg(_napcat_ws, int(recipient), [
        {"type": "text", "data": {"text": "快捷键屏幕截图"}},
        {"type": "image", "data": {"file": f"base64://{payload.image_base64}"}},
    ])
    logger.info("[OneBot] 已发送快捷键屏幕截图")
    return {"ok": True}


# ═══════════════════════════════════════════════════════════
# 消息处理
# ═══════════════════════════════════════════════════════════

async def _handle_message(ws: WebSocket, event: dict):
    msg_type = event.get("message_type", "")
    user_id = event.get("user_id", 0)
    group_id = event.get("group_id", 0)
    raw_message = event.get("raw_message", "")
    message_id = event.get("message_id", "")
    text = _extract_message_text(event)
    image_urls = _extract_image_urls(event)
    self_id = event.get("self_id", 0)

    if not text:
        return

    if user_id:
        _active_connections[user_id] = ws
    if group_id:
        _active_groups[group_id] = ws

    logger.info(f"[OneBot] 💬 {'群' if msg_type == 'group' else '私'}聊 "
                f"<{user_id}>: {text[:60]}")

    if _event_bus:
        asyncio.create_task(_event_bus.emit("onebot.message", {
            "ws": ws,
            "msg_type": msg_type,
            "user_id": user_id,
            "group_id": group_id,
            "self_id": self_id,
            "raw": raw_message,
            "message_id": message_id,
            "text": text,
            "image_urls": image_urls,
            "event": event,
        }))
    else:
        logger.warning("[OneBot] EventBus 未就绪，消息无法处理")


# ═══════════════════════════════════════════════════════════
# 事件总线订阅 — 将 AI 回复发回 QQ
# ═══════════════════════════════════════════════════════════

def register_event_handlers(event_bus: EventBus):
    global _event_bus
    _event_bus = event_bus

    @event_bus.on("onebot.send.private")
    async def _send_private(event):
        data = event.data
        ws = data.get("ws")
        user_id = data.get("user_id")
        message = data.get("message", "")
        if ws and user_id and message:
            await send_private_msg(ws, user_id, message)

    @event_bus.on("onebot.send.group")
    async def _send_group(event):
        data = event.data
        ws = data.get("ws")
        group_id = data.get("group_id")
        message = data.get("message", "")
        if ws and group_id and message:
            await send_group_msg(ws, group_id, message)

    @event_bus.on("onebot.message")
    async def _on_qq_message(event):
        data = event.data
        ws = data["ws"]
        msg_type = data["msg_type"]
        user_id = data["user_id"]
        group_id = data["group_id"]
        message_id = data.get("message_id", "")
        text = data["text"]
        self_id = data.get("self_id", 0)
        raw_event = data.get("event", {})
        image_urls = data.get("image_urls") or _extract_image_urls(raw_event)

        await event_bus.emit("onebot.ai_request", {
            "ws": ws,
            "msg_type": msg_type,
            "user_id": user_id,
            "message_id": message_id,
            "group_id": group_id,
            "text": text,
            "image_urls": data.get("image_urls", []),
            "self_id": self_id,
            "event": raw_event,
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
    支持 / 命令和流式思考推送
    """

    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self._accounts: dict[str, dict] = {}
        self._accounts_path = Path("storage/onebot_accounts.json")
        self._groups: dict[str, dict] = {}
        self._groups_path = Path("storage/onebot_group_history.json")
        self._current_context: tuple[str, str, str] | None = None
        # 代理对并发长流式请求不稳定；统一串行，避免同一条 QQ 会话堆积卡死。
        self._llm_lock = asyncio.Lock()

    async def start(self):
        global _chat_worker
        _chat_worker = self
        self._load_accounts()
        self._load_groups()
        self.event_bus.subscribe("onebot.ai_request", self._handle_ai_request)
        logger.info("[OneBotChat] 🤖 AI 对话工作器已启动")

    # ─── AI 请求处理 ─────────────────────────────────

    async def _handle_ai_request(self, event):
        data = event.data
        ws = data["ws"]
        msg_type = data["msg_type"]
        user_id = data["user_id"]
        group_id = data["group_id"]
        message_id = data.get("message_id", "")
        text = data.get("text", "").strip()
        self_id = data.get("self_id", 0)
        raw_event = data.get("event", {})
        # 普通文本为空列表；图片消息携带可供多模态模型读取的 URL/data URL。
        image_urls = data.get("image_urls") or _extract_image_urls(raw_event)

        logger.info(
            f"[OneBotChat] 🔄 收到 AI 请求: {msg_type} "
            f"<{group_id or user_id}> text={text[:60]}"
        )

        if not text:
            logger.warning("[OneBotChat] ⚠️ 消息文本为空，已忽略")
            return

        # 群上下文采集不以 @ 为前提；保留该群最近 50 条真实聊天。
        if msg_type == "group":
            self._record_group_message(str(group_id), str(user_id), text, raw_event, message_id)

        # 群聊消息必须有 @ 才回复（私聊不受限）
        if msg_type == "group" and not _is_at_bot(raw_event, self_id):
            logger.info(f"[OneBotChat] ⏭️ 群 {group_id} 未 @ 机器人，已忽略")
            return

        # NTQQ/NapCat 会在“@机器人 /命令”场景把文本段开头的斜杠吞掉：
        # 实际日志收到的是 text=help，而不是 text=/help。
        # 群聊已通过 @ 校验，因此将命令名白名单中的首词恢复为标准 /命令。
        if msg_type == "group" and not text.startswith("/"):
            first_word = text.split(maxsplit=1)[0].lower() if text else ""
            known_commands = {
                "help", "h", "history", "his", "clear", "c",
                "model", "models", "m", "ms", "system", "s",
            }
            if first_word in known_commands:
                text = f"/{text}"
                logger.info(f"[OneBotChat] 🔧 已恢复 NTQQ 群命令斜杠: {text}")

        # 同一账号的私聊、以及在每个群里的会话均完全独立。
        account_id = str(user_id)
        scope = "群聊" if msg_type == "group" else "私聊"
        scope_id = str(group_id) if msg_type == "group" else ""
        self._current_context = (account_id, scope, scope_id)
        session = self._get_session(account_id, scope, scope_id, raw_event)
        logger.info(f"[OneBotChat] 🧩 会话已加载: {scope}/{scope_id or account_id}")

        # / 命令处理
        if text.startswith("/"):
            reply = await self._handle_command(text)
            if reply:
                if msg_type == "group":
                    await send_group_msg(ws, group_id, reply)
                else:
                    await send_private_msg(ws, user_id, reply)
                logger.info(f"[OneBotChat] ✅ 命令回复已发送: {text.split()[0]}")
            return

        # 私聊达到 30 条时压缩最早 10 条，始终留下最近 20 条原文。
        # 群内每位用户保留最近 6 轮直接对话（约 12 条消息）。
        history = session["上下文"]
        history.append({"role": "user", "content": text, "message_id": message_id})
        if msg_type == "group":
            history[:] = history[-12:]
            await self._update_group_summary(str(group_id), self._load_settings())
        elif len(history) >= 30:
            await self._compact_private_history(session, self._load_settings())
        self._save_accounts()
        logger.info(f"[OneBotChat] 🧩 会话消息已保存: history={len(history)}")
        settings = self._load_settings()
        system_prompt = session.get("系统提示词") or "你是一个智能AI助手，请友好地回答用户的问题。"
        if msg_type == "group":
            group_summary = self._groups.get(str(group_id), {}).get("群摘要", "")
            if group_summary:
                system_prompt += (
                    "\n\n【群共享背景摘要】\n"
                    "以下是群内共同背景，不代表当前用户本人的观点：\n"
                    f"{group_summary}"
                )
        else:
            private_summary = session.get("历史摘要", "")
            if private_summary:
                system_prompt += f"\n\n【当前用户更早的私聊记忆】\n{private_summary}"

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history)
        if image_urls:
            # 历史只保存文字占位；当前请求把真实图片作为多模态内容发送。
            vision_parts: list[dict] = [{
                "type": "text",
                "text": text or "请识别并说明这些图片的内容。",
            }]
            vision_parts.extend({
                "type": "image_url", "image_url": {"url": image_url, "detail": "auto"}
            } for image_url in image_urls)
            messages[-1] = {"role": "user", "content": vision_parts}
            logger.info(f"[OneBotChat] 🖼️ 已向模型附加 {len(image_urls)} 张图片")

        # 流式调用 LLM
        logger.info("[OneBotChat] 🧩 即将进入模型调用")
        try:
            async with self._llm_lock:
                async for ev in self._stream_call_llm(messages, settings, ws,
                                                       user_id, group_id, msg_type, message_id):
                    if ev["type"] == "reply":
                        history.append({"role": "assistant", "content": ev["content"]})
                        if msg_type == "group":
                            history[:] = history[-12:]
                        elif len(history) >= 30:
                            await self._compact_private_history(session, settings)
                        self._save_accounts()
                    elif ev["type"] == "error":
                        raise Exception(ev.get("content", "未知错误"))
        except Exception as e:
            if "websocket.send" in str(e) or "websocket.close" in str(e):
                logger.warning(f"[OneBotChat] WS 已断开，忽略残留发送: {e}")
                return
            logger.error(f"[OneBotChat] ❌ AI 调用失败: {e}")
            # 失败请求不应残留在记忆中，否则下一个无关问题会继续追旧任务。
            history[:] = [m for m in history if m.get("message_id") != message_id]
            self._save_accounts()
            err = "😅 AI 思考时出了点小差，等会儿再问我吧~"
            if msg_type == "group":
                await send_group_msg(ws, group_id, err)
            else:
                await send_private_msg(ws, user_id, err)

    # ─── 命令系统 ────────────────────────────────────

    async def _handle_command(self, text: str) -> str | None:
        parts = text[1:].strip().split()
        if not parts:
            return None
        cmd = parts[0].lower()
        if cmd in ("help", "h"):
            return (
                "📋 可用命令：\n"
                "/history    - 查看当前会话的记忆策略\n"
                "/clear      - 清除对话历史\n"
                "/model      - 查看当前模型\n"
                "/model xxx  - 全局匹配并切换模型\n"
                "/models     - 查看所有已配置模型\n"
                "/system     - 查看系统提示词\n"
                "/system xxx - 设置系统提示词\n"
                "/system -c  - 清空系统提示词（恢复默认）\n"
                "/help       - 显示此帮助"
            )

        if cmd in ("history", "his"):
            if self._current_context and self._current_context[1] == "群聊":
                return "当前群聊记忆：群共享增量摘要 + 当前群友最近 6 轮直接对话"
            return "当前私聊记忆：最近 20 条原文；累计到 30 条时压缩最早 10 条"

        if cmd in ("clear", "c"):
            session = self._current_session()
            if session is not None:
                session["上下文"] = []
                self._save_accounts()
            return "✅ 对话历史已清除"

        # ─── /system 命令 ─────────────────────────────
        if cmd in ("system", "s"):
            session = self._current_session()
            if session is None:
                return "❌ 当前会话不可用"
            current = session.get("系统提示词", "")
            # 清空
            if len(parts) >= 2 and parts[1] in ("-c", "clear"):
                session["系统提示词"] = ""
                self._save_accounts()
                return "✅ 此会话的系统提示词已清空（恢复默认）"
            # 查看
            if len(parts) == 1:
                if current:
                    return f"📝 当前会话系统提示词：\n{current}"
                return "📝 此会话无自定义提示词（使用默认）\n\n💡 发送 /system <内容> 设置，/system -c 清空"
            # 设置
            new_prompt = text[8:].strip() if cmd == "system" else text[3:].strip()
            if not new_prompt:
                return "❌ 内容不能为空"
            session["系统提示词"] = new_prompt
            self._save_accounts()
            return f"✅ 此会话系统提示词已设置！\n📝 {new_prompt[:100]}{'…' if len(new_prompt) > 100 else ''}"
        # ─── /model 和 /models ──────────────────────────
        if cmd not in ("model", "models", "m", "ms"):
            return f"❌ 未知命令: /{cmd}\n输入 /help 查看可用命令"

        settings = self._load_full_settings()
        current_provider = settings.get("provider", {})
        current_model = current_provider.get("model", "未知")
        providers = settings.get("providers", [])

        if cmd in ("models", "ms"):
            if len(parts) != 1:
                return "❌ /models 不接受参数；发送 /models 查看全部模型"
            lines = [f"🤖 当前模型: {current_model}"]
            for provider in providers:
                name = provider.get("name", "?")
                models = provider.get("models", [])
                if models:
                    models_text = "\n".join(f"  {model}," for model in models)
                else:
                    models_text = "  （未配置）"
                lines.append(f"\n{name}\n{models_text}")
            lines.append("\n发送 /model <模型名> 可直接切换")
            return "\n".join(lines)

        if len(parts) == 1:
            return (
                f"🤖 当前模型: {current_model}\n"
                f"🔗 provider: {current_provider.get('baseUrl', '?')}\n"
                "用法: /model <模型名>"
            )

        requested_model = parts[1]
        matched_providers = [
            provider
            for provider in providers
            if requested_model in provider.get("models", [])
        ]
        if not matched_providers:
            return f"❌ 未找到已配置模型: {requested_model}\n发送 /models 查看全部模型"

        matched_provider = next(
            (
                provider
                for provider in matched_providers
                if provider.get("baseUrl") == current_provider.get("baseUrl")
            ),
            matched_providers[0],
        )
        settings["provider"] = {
            "baseUrl": matched_provider.get("baseUrl", ""),
            "apiKey": matched_provider.get("key", ""),
            "model": requested_model,
        }
        try:
            from pathlib import Path
            Path("storage/settings.json").write_text(
                json.dumps(settings, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as exc:
            return f"❌ 保存失败: {exc}"

        return (
            f"✅ 已切换模型: {requested_model}\n"
            f"🔗 provider: {matched_provider.get('name', '?')}"
        )

    async def remove_from_context(self, message_id: str, user_id: int, group_id: int):
        """撤回消息时从上下文移除对应消息"""
        account = self._accounts.get(str(user_id), {})
        if group_id:
            session = account.get("群聊", {}).get(str(group_id), {})
        else:
            session = account.get("私聊", {})
        history = session.get("上下文", [])
        before = len(history)
        session["上下文"] = [m for m in history if m.get("message_id") != message_id]
        removed = before - len(session["上下文"])
        if removed:
            self._save_accounts()
            logger.info(f"[OneBotChat] ↩️ 已从上下文移除 {removed} 条消息 (msg_id={message_id})")

    # ─── 流式调用 LLM（含工具集成）────────────────────

    async def _stream_call_llm(self, messages: list[dict], settings: dict,
                                ws, user_id: int, group_id: int, msg_type: str,
                                message_id: str = ""):
        """流式调用 LLM，支持工具调用。自适应推送思考/工具/正文流"""
        logger.info(f"[OneBotChat] 🧩 开始模型请求: messages={len(messages)}")
        import httpx
        from tools import ToolRegistry
        import tools.filesystem  # noqa: F401
        import tools.search      # noqa: F401
        import tools.shell       # noqa: F401
        import tools.browser     # noqa: F401
        import tools.python      # noqa: F401
        import tools.media       # noqa: F401
        from tools.media import is_media_descriptor
        logger.info("[OneBotChat] 🧩 工具加载完成")

        base_url = settings.get("baseUrl", "").rstrip("/")
        api_key = settings.get("apiKey", "")
        model = settings.get("model", "gpt-3.5-turbo")
        temperature = settings.get("temperature", 0.7)
        max_tokens = settings.get("maxTokens", 8960)

        if not base_url:
            s = self._load_full_settings()
            p = s.get("provider", {})
            base_url = p.get("baseUrl", "http://localhost:11434/v1")
            api_key = p.get("apiKey", "")
            model = p.get("model", "gpt-3.5-turbo")

        if not api_key:
            yield {"type": "error", "content": "API Key 未配置"}
            return

        # 构建工具定义（OpenAI function calling 格式）
        last_content = next((m.get("content", "") for m in reversed(messages)
                             if m.get("role") == "user"), "")
        if isinstance(last_content, list):
            last_content = " ".join(
                part.get("text", "") for part in last_content if isinstance(part, dict)
            )
        tool_keywords = ("搜索", "查一下", "查询", "网页", "浏览", "文件", "目录", "终端", "命令", "端口", "运行", "截图", "图片", "画图", "配图", "照片")
        use_tools = any(keyword in str(last_content) for keyword in tool_keywords)
        tools_def = []
        for t in ToolRegistry.list() if use_tools else []:
            props = {}
            required = []
            p = t.parameters.get("properties", {})
            for pname, pinfo in p.items():
                raw_type = str(pinfo.get("type", "string"))
                ptype = {"str": "string", "int": "integer", "float": "number",
                         "bool": "boolean", "list": "array", "dict": "object",
                         "<class 'str'>": "string", "<class 'int'>": "integer",
                         "<class 'float'>": "number", "<class 'bool'>": "boolean"}.get(raw_type, "string")
                props[pname] = {"type": ptype, "description": pname}
                required.append(pname)
            tools_def.append({
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": {
                        "type": "object",
                        "properties": props,
                        "required": required,
                    },
                },
            })
        async def _delay(prev: str):
            await asyncio.sleep(2.0 + min(1.0, len(prev) / 200))

        async def _stream_one_round(current_messages: list, allow_tools: bool = True) -> dict:
            payload = {"model": model, "messages": current_messages,
                       "temperature": temperature, "max_tokens": max_tokens,
                       "stream": True}
            if allow_tools:
                payload["tools"] = tools_def
            headers = {"Content-Type": "application/json",
                       "Authorization": f"Bearer {api_key}" if api_key else ""}

            result = {"reasoning": "", "content": "", "tool_calls": []}
            # tool_calls 组装缓存：{index: {id, name, arguments}}
            tc_cache: dict[int, dict] = {}

            async with httpx.AsyncClient(timeout=45.0) as client:
                async with client.stream("POST", f"{base_url}/chat/completions",
                                         headers=headers, json=payload) as resp:
                    if resp.status_code != 200:
                        err = await resp.aread()
                        result["error"] = f"API {resp.status_code}: {err[:200]}"
                        return result

                    buf = b""
                    async for chunk in resp.aiter_bytes():
                        buf += chunk
                        while b"\n" in buf:
                            line, _, buf = buf.partition(b"\n")
                            line = line.decode("utf-8", errors="replace").strip()
                            if not line.startswith("data: "):
                                continue
                            data = line[6:].strip()
                            if data == "[DONE]":
                                break
                            try:
                                ev = json.loads(data)
                            except json.JSONDecodeError:
                                continue
                            choices = ev.get("choices") or [{}]
                            choice = choices[0] if choices else {}
                            delta = choice.get("delta", {}) or {}
                            finish = choice.get("finish_reason")

                            # 思考流
                            rc = delta.get("reasoning_content")
                            if rc:
                                result["reasoning"] += rc

                            # 正文流
                            dc = delta.get("content")
                            if dc:
                                result["content"] += dc

                            # 工具调用流
                            tcs = delta.get("tool_calls")
                            if tcs:
                                for tc in tcs:
                                    idx = tc.get("index", 0)
                                    if idx not in tc_cache:
                                        tc_cache[idx] = {"id": "", "name": "", "arguments": ""}
                                    if tc.get("id"):
                                        tc_cache[idx]["id"] = tc["id"]
                                    func = tc.get("function", {}) or {}
                                    if func.get("name"):
                                        tc_cache[idx]["name"] = func["name"]
                                    if func.get("arguments"):
                                        tc_cache[idx]["arguments"] += func["arguments"]

                            # 流结束且触发了工具调用
                            if finish == "tool_calls" and tc_cache:
                                result["tool_calls"] = list(tc_cache.values())

            return result

        # ─── 主循环 ────────────────────────────────────
        current_messages = [{
            "role": "system",
            "content": (
                "图片传输规则：需要把本地生成/已有图片发给用户时，必须调用 send_image(path, caption)，"
                "严禁读取、打印或在正文中输出 base64/data:image。图片由 OneBot 独立图片段一次性交付。"
            ),
        }, *messages]
        tool_call_count: dict[str, int] = {}
        total_tool_calls = 0
        max_total_tool_calls = 6
        max_same_tool_calls = 3
        force_final = False
        await self._send_qq(ws, user_id, group_id, msg_type, "🤔 思考中...")
        logger.info("[OneBotChat] 🧩 已发送思考状态，开始请求模型")

        for round_num in range(8):
            result = await _stream_one_round(current_messages, allow_tools=not force_final)

            if "error" in result:
                yield {"type": "error", "content": result["error"]}
                return

            reasoning = result.get("reasoning", "")
            content = result.get("content", "")
            tool_calls = result.get("tool_calls", [])

            # reasoning_content 是模型内部推理，只写日志，不发送给 QQ 用户。
            if reasoning:
                logger.debug(f"[OneBotChat] 模型内部推理长度: {len(reasoning)}")

            # 推工具流（合并调用+结果，多条工具合并一条消息）
            if tool_calls:
                tool_messages = []
                permitted = []
                for tc in tool_calls:
                    name = tc.get("name", "")
                    same_in_batch = sum(1 for item in permitted if item.get("name", "") == name)
                    if (total_tool_calls + len(permitted) < max_total_tool_calls
                            and tool_call_count.get(name, 0) + same_in_batch < max_same_tool_calls):
                        permitted.append(tc)
                tool_calls = permitted
                if not tool_calls:
                    logger.info("[OneBotChat] 工具预算已用完，切换为无工具最终答复")
                    current_messages.append({
                        "role": "system",
                        "content": (
                            "工具调用预算已用完。请立即基于已有工具结果和常识给出直接、"
                            "有帮助的最终答复；信息不足时明确说明不确定性和官方核实渠道，"
                            "不要再次请求工具，也不要只描述搜索过程。"
                        ),
                    })
                    force_final = True
                    continue
                tool_summary_lines = []

                for tc in tool_calls:
                    tcid = tc.get("id", "")
                    name = tc.get("name", "")
                    args_str = tc.get("arguments", "{}")
                    try:
                        args = json.loads(args_str) if args_str else {}
                    except json.JSONDecodeError:
                        args = {}

                    tool_call_count[name] = tool_call_count.get(name, 0) + 1
                    total_tool_calls += 1
                    # 执行工具
                    try:
                        loop = asyncio.get_event_loop()
                        result_val = await loop.run_in_executor(
                            None, lambda n=name, a=args: ToolRegistry.call(n, **a))
                        result_str = json.dumps(result_val, ensure_ascii=False) if isinstance(result_val, (dict, list)) else (str(result_val) if result_val is not None else "")
                        if is_media_descriptor(result_val):
                            await self._send_qq_media(ws, user_id, group_id, msg_type, result_val)
                            tool_summary_lines.append(f"🖼️ {name} 图片已发送")
                        else:
                            tool_summary_lines.append(f"✅ {name} 已完成")
                    except Exception as e:
                        result_str = f"错误: {e}"
                        tool_summary_lines.append(f"❌ {name} 失败: {e}")

                    # 构造工具调用消息（含 reasoning_content 回传）
                    assistant_msg = {"role": "assistant",
                                     "content": None,
                                     "reasoning_content": reasoning,
                                     "tool_calls": [{"id": tcid, "type": "function",
                                                      "function": {"name": name, "arguments": args_str}}]}
                    tool_messages.append(assistant_msg)
                    tool_messages.append({"role": "tool", "tool_call_id": tcid, "content": result_str})

                # 合并推一条消息
                push_text = "\n".join(tool_summary_lines)
                await self._send_qq(ws, user_id, group_id, msg_type, push_text)
                await _delay(push_text)

                yield {"type": "tool_round", "messages": tool_messages}
                # 把工具结果加入下一轮消息
                current_messages.extend(tool_messages)
                # 有工具调用，继续循环
                continue

            # 推正文流（最终回复）
            if content:
                final_text = f"💬 {content}"
                await self._send_qq(ws, user_id, group_id, msg_type, final_text)
                yield {"type": "reply", "content": content}
            elif reasoning:
                # 只有内部推理而没有正文时，再请求一次无工具最终答案。
                current_messages.append({
                    "role": "system",
                    "content": "请停止内部分析，直接向用户输出最终答复。",
                })
                force_final = True
                continue
            else:
                yield {"type": "error", "content": "AI 返回为空"}

            # 正文推完了，本轮结束
            return

        yield {"type": "error", "content": "未能生成最终答复"}

    async def _send_qq(self, ws, user_id: int, group_id: int,
                        msg_type: str, text: str, reply_to: str = ""):
        if msg_type == "group":
            await send_group_msg(ws, group_id, text, reply_to)
        else:
            await send_private_msg(ws, user_id, text, reply_to)

    async def _send_qq_media(self, ws, user_id: int, group_id: int,
                             msg_type: str, media: dict):
        """让 NapCat 通过 HTTP 一次拉取图片；图片字节绝不进入模型文本流。"""
        url = str(media.get("url", ""))
        if url.startswith("/"):
            public_base = os.getenv(
                "HHS_PUBLIC_BASE_URL", "http://127.0.0.1:8080"
            ).rstrip("/")
            url = f"{public_base}{url}"
        segments = []
        caption = str(media.get("caption", "")).strip()
        if caption:
            segments.append({"type": "text", "data": {"text": caption}})
        segments.append({
            "type": "image",
            "data": {"file": url, "url": url, "cache": "1"},
        })
        if msg_type == "group":
            await send_group_msg(ws, group_id, segments)
        else:
            await send_private_msg(ws, user_id, segments)
        logger.info(
            f"[OneBotChat] 🖼️ 图片已交给 NapCat 拉取: {media.get('media_id')}"
        )

    # ─── 账号 / 私聊 / 群成员会话持久化 ───────────────

    def _load_accounts(self):
        try:
            if self._accounts_path.exists():
                data = json.loads(self._accounts_path.read_text(encoding="utf-8"))
                self._accounts = data if isinstance(data, dict) else {}
        except Exception as exc:
            logger.error(f"[OneBotChat] 账号会话数据加载失败: {exc}")
            self._accounts = {}

    def _load_groups(self):
        try:
            if self._groups_path.exists():
                data = json.loads(self._groups_path.read_text(encoding="utf-8"))
                self._groups = data if isinstance(data, dict) else {}
        except Exception as exc:
            logger.error(f"[OneBotChat] 群聊历史加载失败: {exc}")
            self._groups = {}

    def _save_accounts(self):
        try:
            self._accounts_path.parent.mkdir(parents=True, exist_ok=True)
            temp_path = self._accounts_path.with_suffix(".json.tmp")
            temp_path.write_text(
                json.dumps(self._accounts, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            temp_path.replace(self._accounts_path)
        except Exception as exc:
            logger.error(f"[OneBotChat] 账号会话数据保存失败: {exc}")

    def _save_groups(self):
        try:
            self._groups_path.parent.mkdir(parents=True, exist_ok=True)
            temp_path = self._groups_path.with_suffix(".json.tmp")
            temp_path.write_text(
                json.dumps(self._groups, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            temp_path.replace(self._groups_path)
        except Exception as exc:
            logger.error(f"[OneBotChat] 群聊历史保存失败: {exc}")

    def _record_group_message(self, group_id: str, account_id: str,
                              text: str, raw_event: dict, message_id: str = ""):
        sender = raw_event.get("sender", {}) or {}
        nickname = sender.get("card") or sender.get("nickname") or account_id
        group = self._groups.setdefault(group_id, {
            "最近消息": [], "群摘要": "", "最后摘要序号": 0, "下一序号": 1,
        })
        sequence = int(group.get("下一序号", 1))
        messages = group.setdefault("最近消息", [])
        messages.append({
            "序号": sequence,
            "消息ID": str(message_id),
            "账号": account_id,
            "昵称": nickname,
            "内容": text,
            "时间": int(raw_event.get("time") or time.time()),
        })
        group["下一序号"] = sequence + 1
        group["最近消息"] = messages[-50:]
        self._save_groups()

    async def _summarize_text(self, source: str, previous: str, settings: dict,
                              instruction: str) -> str | None:
        """调用当前模型生成紧凑记忆；失败返回 None，调用方不得删除原文。"""
        import httpx

        base_url = settings.get("baseUrl", "").rstrip("/")
        api_key = settings.get("apiKey", "")
        model = settings.get("model", "gpt-3.5-turbo")
        if not base_url:
            provider = settings.get("provider", {})
            base_url = provider.get("baseUrl", "").rstrip("/")
            api_key = provider.get("apiKey", api_key)
            model = provider.get("model", model)
        if not base_url or not api_key or not source.strip():
            return None

        prompt = (
            f"{instruction}\n"
            "仅记录事实、人物观点、决定、待办和重要关系；忽略寒暄与重复内容。"
            "不要编造信息，不要输出标题，控制在 500 个中文字符以内。\n\n"
            f"已有摘要：\n{previous or '（无）'}\n\n待压缩内容：\n{source}"
        )
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": "你是对话记忆压缩器，只输出客观、紧凑的摘要。"},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.1,
            "max_tokens": 800,
            "stream": False,
        }
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json=payload,
                )
                response.raise_for_status()
                content = response.json()["choices"][0]["message"].get("content", "").strip()
                return content or previous
        except Exception as exc:
            logger.warning(f"[OneBotChat] 摘要生成失败，保留原文等待重试: {exc}")
            return None

    async def _update_group_summary(self, group_id: str, settings: dict) -> str:
        """只合并检查点之后的新消息；群内所有成员共享同一份摘要。"""
        group = self._groups.get(group_id, {})
        previous = group.get("群摘要", "")
        checkpoint = int(group.get("最后摘要序号", 0))
        pending = [
            message for message in group.get("最近消息", [])
            if int(message.get("序号", 0)) > checkpoint
        ]
        if not pending:
            return previous
        source = "\n".join(
            f"{m.get('昵称', m.get('账号'))}: {m.get('内容', '')}" for m in pending
        )
        updated = await self._summarize_text(
            source, previous, settings,
            "将尚未处理的新群消息增量合并进群共享摘要。区分不同发言人，"
            "不要把某个群友的观点描述成全群共识。",
        )
        # 只有生成了有效摘要才推进检查点；失败后下次仍可重试。
        if updated is not None:
            group["群摘要"] = updated
            group["最后摘要序号"] = max(int(m.get("序号", 0)) for m in pending)
            self._save_groups()
        return group.get("群摘要", previous)

    async def _compact_private_history(self, session: dict, settings: dict):
        history = session.setdefault("上下文", [])
        if len(history) < 30:
            return
        to_compress = history[:10]
        source = "\n".join(
            f"{'用户' if m.get('role') == 'user' else '助手'}: {m.get('content', '')}"
            for m in to_compress
        )
        updated = await self._summarize_text(
            source, session.get("历史摘要", ""), settings,
            "将较早的私聊记录与已有摘要合并为长期记忆。",
        )
        if updated is None:
            return
        session["历史摘要"] = updated
        history[:] = history[10:]

    def _account_info(self, account_id: str, raw_event: dict) -> dict:
        sender = raw_event.get("sender", {}) or {}
        info: dict[str, Any] = {"账号": account_id}
        nickname = sender.get("card") or sender.get("nickname")
        if nickname:
            info["昵称"] = nickname
        sex = sender.get("sex")
        if sex and sex != "unknown":
            info["性别"] = {"male": "男", "female": "女"}.get(sex, sex)
        age = sender.get("age")
        if isinstance(age, int) and age > 0:
            info["年龄"] = age
        area = sender.get("area") or sender.get("region")
        if area:
            info["地区"] = area
        signature = sender.get("sign") or sender.get("signature")
        if signature:
            info["个性签名"] = signature
        return info

    def _new_session(self) -> dict:
        # 兼容旧版全局提示词：只在会话首次建立时复制，之后彼此独立。
        legacy_prompt = self._load_settings().get("qq_systemPrompt", "")
        return {"系统提示词": legacy_prompt, "上下文": []}

    def _get_session(self, account_id: str, scope: str, scope_id: str,
                     raw_event: dict) -> dict:
        account = self._accounts.setdefault(account_id, {
            "账号基本信息": {"账号": account_id},
            "私聊": self._new_session(),
            "群聊": {},
        })
        # 用最新 OneBot 资料增量更新，缺失字段不会覆盖已有资料。
        account.setdefault("账号基本信息", {"账号": account_id}).update(
            self._account_info(account_id, raw_event)
        )
        account.setdefault("私聊", self._new_session())
        groups = account.setdefault("群聊", {})
        session = account["私聊"] if scope == "私聊" else groups.setdefault(scope_id, self._new_session())
        session.setdefault("系统提示词", "")
        session.setdefault("上下文", [])
        self._save_accounts()
        return session

    def _current_session(self) -> dict | None:
        if not self._current_context:
            return None
        account_id, scope, scope_id = self._current_context
        account = self._accounts.get(account_id, {})
        if scope == "私聊":
            return account.get("私聊")
        return account.get("群聊", {}).get(scope_id)

    # ─── 加载配置 ────────────────────────────────────

    def _load_settings(self) -> dict:
        return self._load_full_settings()

    def _load_full_settings(self) -> dict:
        try:
            from pathlib import Path
            path = Path("storage/settings.json")
            if path.exists():
                return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
        return {}

    def _save_settings(self, settings: dict):
        """保存完整配置到 settings.json"""
        try:
            from pathlib import Path
            Path("storage/settings.json").write_text(
                json.dumps(settings, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.error(f"[OneBotChat] ❌ 保存配置失败: {exc}")

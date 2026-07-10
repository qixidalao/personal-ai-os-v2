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
            else:
                parts.append(f"[{seg_type}消息]")
        return " ".join(p.strip() for p in parts if p and p.strip()).strip()
    if isinstance(msg, str):
        raw = event.get("raw_message") or msg
        return str(raw).strip()
    return str(msg).strip()



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

        await event_bus.emit("onebot.ai_request", {
            "ws": ws,
            "msg_type": msg_type,
            "user_id": user_id,
            "message_id": message_id,
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
    支持 / 命令和流式思考推送
    """

    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.sessions: dict[str, list[dict]] = {}
        self.max_history = 20

    async def start(self):
        global _chat_worker
        _chat_worker = self
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
        text = data["text"].strip()

        # / 命令处理
        if text.startswith("/"):
            reply = await self._handle_command(text)
            if reply:
                if msg_type == "group":
                    await send_group_msg(ws, group_id, reply)
                else:
                    await send_private_msg(ws, user_id, reply)
            return

        # 会话历史
        session_key = f"qq_{msg_type}_{group_id or user_id}"
        if session_key not in self.sessions:
            self.sessions[session_key] = []
        history = self.sessions[session_key]
        history.append({"role": "user", "content": text, "message_id": message_id})
        if len(history) > self.max_history:
            history.pop(0)
        settings = self._load_settings()
        # QQ 独立 system prompt（与前端 systemPrompt 隔离）
        system_prompt = settings.get("qq_systemPrompt") or "你是一个智能AI助手，请友好地回答用户的问题。"

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history)

        # 流式调用 LLM
        try:
            async for ev in self._stream_call_llm(messages, settings, ws,
                                                   user_id, group_id, msg_type, message_id):
                if ev["type"] == "reply":
                    history.append({"role": "assistant", "content": ev["content"]})
                elif ev["type"] == "tool_round":
                    history.extend(ev.get("messages", []))
                elif ev["type"] == "error":
                    raise Exception(ev.get("content", "未知错误"))
        except Exception as e:
            if "websocket.send" in str(e) or "websocket.close" in str(e):
                logger.warning(f"[OneBotChat] WS 已断开，忽略残留发送: {e}")
                return
            logger.error(f"[OneBotChat] ❌ AI 调用失败: {e}")
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
                f"/history N  - 设置上下文记忆条数（当前 {self.max_history}）\n"
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
            if len(parts) < 2:
                return f"当前上下文: {self.max_history} 条\n用法: /history N（1-100）"
            try:
                n = int(parts[1])
            except ValueError:
                return "❌ 请输入数字"
            if not 1 <= n <= 100:
                return "❌ N 必须在 1-100 之间"
            self.max_history = n
            return f"✅ 上下文记忆已设为 {n} 条"

        if cmd in ("clear", "c"):
            return "✅ 对话历史已清除"

        # ─── /system 命令 ─────────────────────────────
        if cmd in ("system", "s"):
            settings = self._load_full_settings()
            current = settings.get("qq_systemPrompt", "")
            # 清空
            if len(parts) >= 2 and parts[1] in ("-c", "clear"):
                settings.pop("qq_systemPrompt", None)
                self._save_settings(settings)
                return "✅ 系统提示词已清空（恢复默认）"
            # 查看
            if len(parts) == 1:
                if current:
                    return f"📝 当前系统提示词：\n{current}"
                return "📝 当前系统提示词：（默认）\n你是一个智能AI助手，请友好地回答用户的问题。\n\n💡 发送 /system <内容> 设置，/system -c 清空"
            # 设置
            new_prompt = text[8:].strip() if cmd == "system" else text[3:].strip()
            if not new_prompt:
                return "❌ 内容不能为空"
            settings["qq_systemPrompt"] = new_prompt
            self._save_settings(settings)
            return f"✅ 系统提示词已设置！\n📝 {new_prompt[:100]}{'…' if len(new_prompt) > 100 else ''}"

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
        session_key = f"qq_{'group' if group_id else 'private'}_{group_id or user_id}"
        history = self.sessions.get(session_key, [])
        before = len(history)
        self.sessions[session_key] = [m for m in history if m.get("message_id") != message_id]
        removed = before - len(self.sessions[session_key])
        if removed:
            logger.info(f"[OneBotChat] ↩️ 已从上下文移除 {removed} 条消息 (msg_id={message_id})")

    # ─── 流式调用 LLM（含工具集成）────────────────────

    async def _stream_call_llm(self, messages: list[dict], settings: dict,
                                ws, user_id: int, group_id: int, msg_type: str,
                                message_id: str = ""):
        """流式调用 LLM，支持工具调用。自适应推送思考/工具/正文流"""
        import httpx
        from tools import ToolRegistry
        import tools.filesystem  # noqa: F401
        import tools.search      # noqa: F401
        import tools.shell       # noqa: F401
        import tools.browser     # noqa: F401
        import tools.python      # noqa: F401

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
        tools_def = []
        for t in ToolRegistry.list():
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

        async def _stream_one_round(current_messages: list) -> dict:
            payload = {"model": model, "messages": current_messages,
                       "temperature": temperature, "max_tokens": max_tokens,
                       "stream": True, "tools": tools_def}
            headers = {"Content-Type": "application/json",
                       "Authorization": f"Bearer {api_key}" if api_key else ""}

            result = {"reasoning": "", "content": "", "tool_calls": []}
            # tool_calls 组装缓存：{index: {id, name, arguments}}
            tc_cache: dict[int, dict] = {}

            async with httpx.AsyncClient(timeout=180.0) as client:
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
        current_messages = list(messages)
        tool_call_count: dict[str, int] = {}  # 同类工具调用次数限制
        await self._send_qq(ws, user_id, group_id, msg_type, "🤔 思考中...")

        for round_num in range(10):  # 最多 10 轮工具调用
            result = await _stream_one_round(current_messages)

            if "error" in result:
                yield {"type": "error", "content": result["error"]}
                return

            reasoning = result.get("reasoning", "")
            content = result.get("content", "")
            tool_calls = result.get("tool_calls", [])

            # 推思考流
            if reasoning:
                await self._send_qq(ws, user_id, group_id, msg_type,
                                    f"💭 思考收纳盒\n{reasoning}")
                await _delay(reasoning)

            # 推工具流（合并调用+结果，多条工具合并一条消息）
            if tool_calls:
                tool_messages = []
                # 检查工具调用次数，超过 2 次则拦截
                banned_tools = {n for n, c in tool_call_count.items() if c >= 2}
                tool_calls = [tc for tc in tool_calls if tc.get("name", "") not in banned_tools]
                if not tool_calls:
                    logger.warning(f"[OneBotChat] ⚠️ 移除重复工具后无可用调用，终止工具轮")
                    break
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
                    # 执行工具
                    try:
                        loop = asyncio.get_event_loop()
                        result_val = await loop.run_in_executor(
                            None, lambda n=name, a=args: ToolRegistry.call(n, **a))
                        result_str = str(result_val) if result_val is not None else ""
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
                # 没正文但有思考，把思考当正文
                final_text = f"💬 {reasoning}"
                await self._send_qq(ws, user_id, group_id, msg_type, final_text)
                yield {"type": "reply", "content": reasoning}
            else:
                yield {"type": "error", "content": "AI 返回为空"}

            # 正文推完了，本轮结束
            return

        # 超过 10 轮工具调用
        yield {"type": "error", "content": "工具调用次数过多，已终止"}

    async def _send_qq(self, ws, user_id: int, group_id: int,
                        msg_type: str, text: str, reply_to: str = ""):
        if msg_type == "group":
            await send_group_msg(ws, group_id, text, reply_to)
        else:
            await send_private_msg(ws, user_id, text, reply_to)

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

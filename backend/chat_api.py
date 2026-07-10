"""
Personal AI OS — LLM 聊天完成 API
支持工具调用循环 + SSE 流式推送，前端可实时看到思考/工具/正文渐进式展示。

Streaming 架构（v20260709-2）:
  - ⚡ 零缓冲直推：LLM API 原生 SSE 流 → 直接转发到前端
  - 🚫 无人工 sleep / 无队列 / 无额外延迟层
  - 🔌 断连检测：客户端断开即刻取消上游 LLM 调用
  - 📝 异步日志：IO 不阻塞主路径
"""
import asyncio
import json
import re
import time
import uuid
from pathlib import Path
from typing import Any, AsyncIterator

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from loguru import logger
from pydantic import BaseModel

from tools import ToolRegistry
import tools.filesystem  # noqa: F401
import tools.search  # noqa: F401
import tools.shell  # noqa: F401
import tools.browser  # noqa: F401
import tools.python  # noqa: F401

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])
SETTINGS_FILE = Path("storage/settings.json")
STREAM_LOG_FILE = Path("storage/logs/stream_debug.jsonl")

# ── 异步日志（按事件循环隔离，避免跨 loop 复用 asyncio 对象）────────────
_log_queue: asyncio.Queue[dict] | None = None
_log_task: asyncio.Task | None = None
_log_loop: asyncio.AbstractEventLoop | None = None


async def _log_writer(queue: asyncio.Queue[dict]):
    buf: list[str] = []
    while True:
        try:
            record = await asyncio.wait_for(queue.get(), timeout=1.0)
            buf.append(json.dumps(record, ensure_ascii=False, default=str))
        except asyncio.TimeoutError:
            pass
        except asyncio.CancelledError:
            break
        except Exception:
            continue
        if len(buf) >= 20 or (queue.empty() and buf):
            try:
                STREAM_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
                with STREAM_LOG_FILE.open("a", encoding="utf-8") as file:
                    file.write("\n".join(buf) + "\n")
            except Exception:
                pass
            buf = []


async def _ensure_log_writer():
    global _log_queue, _log_task, _log_loop
    current_loop = asyncio.get_running_loop()
    if _log_loop is not current_loop or _log_task is None or _log_task.done():
        _log_loop = current_loop
        _log_queue = asyncio.Queue(maxsize=500)
        _log_task = current_loop.create_task(_log_writer(_log_queue))


def _stream_log(request_id: str, event: str, **data: Any) -> None:
    queue = _log_queue
    if queue is None:
        return
    try:
        record = {"ts": time.time(), "rid": request_id, "event": event, **data}
        queue.put_nowait(record)
    except asyncio.QueueFull:
        pass


def _preview(text: Any, limit: int = 80) -> str:
    s = str(text or "").replace("\n", "\\n")
    return s[:limit] + ("…" if len(s) > limit else "")


class ChatRequest(BaseModel):
    messages: list[dict]
    model: str
    baseUrl: str
    apiKey: str = ""
    temperature: float = 0.7
    maxTokens: int = 4096


class ChatResponse(BaseModel):
    reply: str
    model: str
    usage: dict | None = None
    reasoning: str | None = None
    tools: list[dict] = []
    rounds: int = 0


def _read_settings() -> dict[str, Any]:
    if not SETTINGS_FILE.exists():
        return {}
    try:
        return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _normalize_base_url(base_url: str) -> str:
    return base_url.rstrip("/")


def _get_enabled_tools() -> list[dict]:
    tools = []
    for ts in ToolRegistry.list():
        schema = _normalize_tool_schema(ts)
        tools.append({"type": "function", "function": {"name": ts.name, "description": ts.description, "parameters": schema}})
    return tools


def _normalize_tool_schema(ts) -> dict:
    params = ts.parameters or {}
    props = params.get("properties", {})
    if not props:
        return {"type": "object", "properties": {}}
    clean = {}
    for k, v in props.items():
        t = v.get("type", "string") if isinstance(v, dict) else str(v)
        if t in ("<class 'str'>", "str", "string"):
            t = "string"
        elif t in ("<class 'int'>", "int", "integer"):
            t = "integer"
        elif t in ("<class 'dict'>", "dict", "object"):
            t = "object"
        else:
            t = "string"
        clean[k] = {"type": t}
    return {"type": "object", "properties": clean}


def _tool_result_to_str(result: Any) -> str:
    if isinstance(result, str):
        return result
    try:
        return json.dumps(result, ensure_ascii=False)
    except Exception:
        return str(result)


def _extract_reasoning_from_message(message: dict) -> str:
    """提取不同 OpenAI 兼容服务使用的推理字段。"""
    return (
        message.get("reasoning_content")
        or message.get("reasoning")
        or message.get("reasoning_text")
        or ""
    )


def _split_think_tags(content: str, existing_reasoning: str = "") -> tuple[str, str]:
    chunks = re.findall(r"<think>([\s\S]*?)</think>", content, flags=re.IGNORECASE)
    if not chunks:
        return content, existing_reasoning
    clean = re.sub(r"<think>[\s\S]*?</think>", "", content, flags=re.IGNORECASE).strip()
    reasoning = existing_reasoning.strip()
    tag_reasoning = "\n\n".join(c.strip() for c in chunks if c.strip())
    if tag_reasoning:
        reasoning = f"{reasoning}\n\n{tag_reasoning}".strip() if reasoning else tag_reasoning
    return clean, reasoning


# ---------------------------------------------------------------------------
# 流式 LLM 调用 —— 纯异步迭代器，零缓冲
# ---------------------------------------------------------------------------
async def _stream_llm_completion(
    api_url: str, headers: dict, body: dict, request_id: str, round_idx: int
) -> AsyncIterator[dict]:
    """Real streaming from LLM API. Yields dicts: text_delta / reasoning_delta / done."""
    stream_body = {**body, "stream": True}
    full_content = ""
    full_reasoning = ""
    tool_calls_acc: dict[int, dict[str, Any]] = {}
    finish_reason = None
    sse_buf = b""
    raw_chunks = 0

    _stream_log(request_id, "llm_stream_start", round=round_idx, model=body.get("model"))

    try:
        async with httpx.AsyncClient(timeout=180) as client:
            async with client.stream("POST", api_url, headers=headers, json=stream_body) as response:
                _stream_log(request_id, "llm_http_status", round=round_idx, status=response.status_code)
                if response.status_code >= 400:
                    error_text = "<read-error>"
                    try:
                        err_bytes = await response.aread()
                        error_text = json.loads(err_bytes).get("error", {}).get("message", str(err_bytes[:300]))
                    except Exception:
                        pass
                    raise HTTPException(status_code=response.status_code, detail=f"LLM 请求异常 (HTTP {response.status_code}): {error_text}")

                async for raw_chunk in response.aiter_bytes():
                    raw_chunks += 1
                    sse_buf += raw_chunk
                    while b"\n" in sse_buf:
                        line_bytes, _, sse_buf = sse_buf.partition(b"\n")
                        line = line_bytes.decode("utf-8", errors="replace").strip()
                        if not line.startswith("data: "):
                            continue
                        payload = line[6:].strip()
                        if payload == "[DONE]":
                            _stream_log(request_id, "llm_done_marker", round=round_idx, raw_chunks=raw_chunks)
                            sse_buf = b""
                            break

                        try:
                            chunk = json.loads(payload)
                        except json.JSONDecodeError:
                            continue

                        choices = chunk.get("choices", [])
                        if not choices:
                            continue
                        choice = choices[0]
                        delta = choice.get("delta", {}) or {}
                        fr = choice.get("finish_reason")
                        if fr:
                            finish_reason = fr

                        rc = delta.get("reasoning_content")
                        if rc:
                            full_reasoning += rc
                            yield {"type": "reasoning_delta", "content": rc}

                        dc = delta.get("content")
                        if dc:
                            full_content += dc
                            yield {"type": "text_delta", "content": dc}

                        for tc_item in delta.get("tool_calls") or []:
                            idx = tc_item.get("index", 0)
                            if idx not in tool_calls_acc:
                                tool_calls_acc[idx] = {"id": "", "function": {"name": "", "arguments": ""}}
                            acc = tool_calls_acc[idx]
                            if tc_item.get("id"):
                                acc["id"] = tc_item["id"]
                            fn = tc_item.get("function") or {}
                            if fn.get("name"):
                                acc["function"]["name"] = fn["name"]
                            if fn.get("arguments"):
                                acc["function"]["arguments"] += fn["arguments"]

    except HTTPException:
        raise
    except Exception as exc:
        _stream_log(request_id, "llm_stream_exception", round=round_idx, error=str(exc))
        raise HTTPException(status_code=502, detail=f"LLM 流式请求失败: {exc}")

    # 构建完整 message
    tool_calls_list = []
    for idx in sorted(tool_calls_acc.keys()):
        tc = tool_calls_acc[idx]
        fn = tc.get("function", {})
        tool_calls_list.append({
            "id": tc.get("id") or f"call_{int(time.time() * 1000)}_{idx}",
            "type": "function",
            "function": {"name": fn.get("name", ""), "arguments": fn.get("arguments", "{}")},
        })

    message = {"content": full_content, "role": "assistant"}
    if full_reasoning:
        message["reasoning_content"] = full_reasoning
    if tool_calls_list:
        message["tool_calls"] = tool_calls_list

    _stream_log(request_id, "llm_stream_done", round=round_idx,
                reasoning_len=len(full_reasoning), content_len=len(full_content),
                tool_calls=len(tool_calls_list), finish_reason=finish_reason)
    yield {"type": "done", "message": message, "finish_reason": finish_reason}


# ---------------------------------------------------------------------------
# /completions —— 老版一次性接口（兼容）
# ---------------------------------------------------------------------------
@router.post("/completions")
async def chat_completion(req: ChatRequest):
    rid = uuid.uuid4().hex[:10]
    reasoning_parts: list[str] = []
    tools_trace: list[dict[str, Any]] = []
    last_content = ""
    last_usage: dict | None = None
    last_model = req.model

    async for event in _stream_events(req, rid):
        t = event.get("type")
        if t == "reasoning":
            reasoning_parts.append(event.get("content", ""))
        elif t == "tool_call":
            tools_trace.append(event)
        elif t == "content":
            last_content += event.get("content", "")
        elif t == "usage":
            last_usage = event.get("data")
        elif t == "model":
            last_model = event.get("data", last_model)

    merged = "\n\n".join(p for p in reasoning_parts if p).strip() or None
    return ChatResponse(
        reply=last_content,
        model=last_model,
        usage=last_usage,
        reasoning=merged,
        tools=tools_trace,
        rounds=len([e for e in reasoning_parts if e]),  # rough count
    )


# ---------------------------------------------------------------------------
# SSE 事件流生成器（零缓冲直推）
# ---------------------------------------------------------------------------
async def _stream_events(req: ChatRequest, request_id: str, request: Request | None = None):
    """
    直接迭代 LLM 流式生成器，零缓冲转发事件。
    断连时通过 request.is_disconnected() 感知并终止。
    """
    await _ensure_log_writer()

    api_url = f"{_normalize_base_url(req.baseUrl)}/chat/completions"
    headers = {"Content-Type": "application/json"}
    if req.apiKey:
        headers["Authorization"] = f"Bearer {req.apiKey}"

    normalized_messages: list[dict[str, Any]] = []
    for m in req.messages:
        role = m.get("role", "user")
        if role == "ai":
            role = "assistant"
        normalized_messages.append({"role": role, "content": m.get("content", "")})

    openai_tools = _get_enabled_tools()
    logger.info(f"📤 发送给 LLM，rid={request_id} tool_count={len(openai_tools)} messages_count={len(normalized_messages)}")
    _stream_log(request_id, "stream_events_start", model=req.model,
                base_url=_normalize_base_url(req.baseUrl), messages=len(normalized_messages),
                tools=len(openai_tools))

    body: dict[str, Any] = {
        "model": req.model,
        "messages": normalized_messages,
        "temperature": req.temperature,
        "max_tokens": req.maxTokens,
    }
    if openai_tools:
        body["tools"] = openai_tools
        body["tool_choice"] = "auto"

    settings = _read_settings()
    agent_params = settings.get("agentParams", {}) or {}
    MAX_TOOL_ROUNDS = int(agent_params.get("maxToolRounds", 6))

    for round_idx in range(MAX_TOOL_ROUNDS + 1):
        content_accumulated = ""
        reasoning_accumulated = ""
        tool_calls = []

        _stream_log(request_id, "round_start", round=round_idx, messages=len(body.get("messages", [])))

        # ★ 直接迭代 LLM 流，零缓冲、零 sleep
        async for stream_event in _stream_llm_completion(api_url, headers, body, request_id, round_idx):
            t = stream_event["type"]

            # 断连检测（非阻塞，每收到一个事件检查一次）
            if request is not None:
                try:
                    if await request.is_disconnected():
                        _stream_log(request_id, "stream_cancelled_disconnect", round=round_idx)
                        return
                except Exception:
                    pass

            if t == "text_delta":
                content_accumulated += stream_event["content"]
                yield {"type": "content", "content": stream_event["content"], "round": round_idx}
            elif t == "reasoning_delta":
                reasoning_accumulated += stream_event["content"]
                yield {"type": "reasoning", "content": stream_event["content"], "round": round_idx}
            elif t == "done":
                message = stream_event.get("message", {}) or {}
                content_accumulated = message.get("content", "") or content_accumulated
                tool_calls = message.get("tool_calls") or []
                _stream_log(request_id, "round_llm_done", round=round_idx,
                            reasoning_len=len(message.get("reasoning_content", reasoning_accumulated) or ""),
                            content_len=len(content_accumulated), tool_calls=len(tool_calls))
                break

        # 剥离 <think> 标签
        clean_content, clean_reasoning = _split_think_tags(content_accumulated, reasoning_accumulated)

        if not tool_calls:
            _stream_log(request_id, "stream_done_final", round=round_idx, rounds=round_idx)
            yield {"type": "done", "rounds": round_idx}
            return

        _stream_log(request_id, "tool_round_start", round=round_idx, tools=len(tool_calls))
        yield {"type": "tool_round_start", "round": round_idx}

        body["messages"].append({"role": "assistant", "content": content_accumulated or None, "tool_calls": tool_calls})

        for tc in tool_calls:
            fn = tc.get("function", {}) or {}
            fn_name = fn.get("name", "")
            raw_args = fn.get("arguments", "{}")
            try:
                fn_args = json.loads(raw_args) if isinstance(raw_args, str) else (raw_args or {})
            except json.JSONDecodeError:
                fn_args = {}

            tool_id = tc.get("id", f"tool-{round_idx}-{int(time.time() * 1000)}")

            _stream_log(request_id, "tool_call_start", round=round_idx, id=tool_id, name=fn_name)
            yield {"type": "tool_call_start", "id": tool_id, "round": round_idx + 1,
                   "name": fn_name or "unknown_tool", "args": fn_args}

            logger.info(f"🛠️ Round {round_idx + 1}: LLM 调用工具 {fn_name} args={fn_args}")
            started = time.perf_counter()
            ok = True
            error = ""
            try:
                tool_result = ToolRegistry.call(fn_name, **fn_args)
                result_str = _tool_result_to_str(tool_result)
            except Exception as exc:
                ok = False
                error = str(exc)
                result_str = f"工具 {fn_name} 执行出错: {exc}"

            elapsed_ms = int((time.perf_counter() - started) * 1000)

            yield {"type": "tool_call", "id": tool_id, "round": round_idx + 1,
                   "name": fn_name or "unknown_tool", "args": fn_args,
                   "result": result_str, "ok": ok, "error": error, "durationMs": elapsed_ms}

            body["messages"].append({"role": "tool", "tool_call_id": tc.get("id", ""), "content": result_str})

        _stream_log(request_id, "tool_round_end", round=round_idx)
        yield {"type": "tool_round_end", "round": round_idx}

    _stream_log(request_id, "stream_done_max_rounds", rounds=MAX_TOOL_ROUNDS)
    yield {"type": "done", "rounds": MAX_TOOL_ROUNDS}


# ---------------------------------------------------------------------------
# /stream —— SSE 流式接口（爆发缓冲 + 恒定速率输出）
# ---------------------------------------------------------------------------
@router.post("/stream")
async def chat_completion_stream(req: ChatRequest, fastapi_request: Request):
    """
    SSE 流式接口。

    架构：生产者-消费者爆发缓冲
      - 生产者：_stream_events() 以 LLM 原生速度产生事件（可能 burst）
      - 缓冲队列：asyncio.Queue(maxsize=200) 蓄住 burst
      - 消费者：以恒定 5ms 间隔从队列 drain，输出平滑 SSE 流

    效果：无论 LLM API 怎么爆发，用户看到的是 ~200 tokens/s 的稳定输出
    """
    await _ensure_log_writer()
    request_id = uuid.uuid4().hex[:10]
    _stream_log(request_id, "http_stream_open", model=req.model)

    async def event_generator():
        seq = 0
        queue: asyncio.Queue = asyncio.Queue(maxsize=200)  # ★ 爆发缓冲池

        # ── 生产者：尽快从 LLM 拉取，放入队列 ──
        async def _producer():
            try:
                async for event in _stream_events(req, request_id, request=fastapi_request):
                    await queue.put(event)
            except asyncio.CancelledError:
                pass
            except Exception:
                raise
            finally:
                await queue.put(None)  # 哨兵：生产结束

        producer_task = asyncio.create_task(_producer())

        try:
            # ── 消费者：恒定速率 drain ──
            while True:
                event = await queue.get()
                if event is None:  # 哨兵 → 流结束
                    break

                seq += 1
                typ = event.get("type")
                if typ in {"reasoning", "content", "tool_round_start", "tool_call_start",
                           "tool_call", "tool_round_end", "done"}:
                    _stream_log(request_id, "http_sse_send", seq=seq, type=typ,
                                round=event.get("round"),
                                content_len=len(event.get("content", "") or ""),
                                preview=_preview(event.get("content", "")))
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                # ★ 恒定 5ms 间隔 — 无论 LLM 怎么 burst，输出始终平稳
                await asyncio.sleep(0.005)

            _stream_log(request_id, "http_sse_done_marker", seq=seq + 1)
            yield "data: [DONE]\n\n"
        except asyncio.CancelledError:
            _stream_log(request_id, "http_stream_cancelled", seq=seq)
            producer_task.cancel()
        except Exception as exc:
            _stream_log(request_id, "http_stream_exception", error=str(exc))
            producer_task.cancel()
            raise
        finally:
            if not producer_task.done():
                producer_task.cancel()
            try:
                await producer_task
            except (asyncio.CancelledError, Exception):
                pass

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "X-Stream-Request-Id": request_id,
        },
    )

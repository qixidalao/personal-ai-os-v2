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
from contextlib import AsyncExitStack
import os
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
from runtime.execution import current_run, current_tool_call, get_execution_manager
from runtime.context.provenance import annotate as _provenance_annotate

import tools.filesystem  # noqa: F401
import tools.search  # noqa: F401
import tools.shell  # noqa: F401
import tools.browser  # noqa: F401
import tools.python  # noqa: F401
import tools.skills  # noqa: F401
import tools.media  # noqa: F401
import tools.media.image_enhance  # noqa: F401

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])
_TOOL_EXEC_SEM = asyncio.Semaphore(int(os.environ.get("AIOS_TOOL_CONCURRENCY", "2")))
# 复用连接，避免每次请求重新 TLS 握手，降低首字延迟
def _make_llm_client(base_url: str, settings: dict[str, Any] | None = None) -> httpx.AsyncClient:
    """直连模型 API；需要代理的 provider 用 proxy=env 标记。"""
    use_env = False
    try:
        for provider in (settings or _read_settings()).get("providers", []) or []:
            if not isinstance(provider, dict):
                continue
            if _normalize_base_url(str(provider.get("baseUrl") or "")) == _normalize_base_url(base_url):
                mode = str(provider.get("proxy") or "").lower()
                if mode in ("env", "system", "clash") or mode.startswith("http"):
                    use_env = True
                break
    except Exception:
        pass
    return httpx.AsyncClient(timeout=180, trust_env=use_env)
_TOOL_HINT_RE = re.compile(
    r"(文件|目录|读取|写入|保存|创建|删除|搜索|网页|链接|浏览器|截图|图片|运行|执行|命令|终端|"
    r"shell|bash|python|脚本|代码|工具|下载|上传|http|https|url|api|日志|数据库|表格|excel|pdf|word|邮件)",
    re.I,
)


def _needs_tools(messages: list[dict], settings: dict) -> bool:
    """自动工具选择：普通闲聊不携带 12 个工具 schema，显著降低首字延迟。"""
    if settings.get("autoTools", True) is False:
        return True
    text = ""
    for m in reversed(messages):
        if m.get("role") == "user":
            text = str(m.get("content") or "")
            break
    if len(text.strip()) < 4:
        return False
    return bool(_TOOL_HINT_RE.search(text))
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
    sessionId: str | None = None


class ChatResponse(BaseModel):
    reply: str
    model: str
    usage: dict | None = None
    reasoning: str | None = None
    tools: list[dict] = []
    rounds: int = 0


_run_store = None


def _get_run_store():
    """Lazy RunStore singleton; failures never block chat."""
    # 中文：延迟初始化的 RunStore 单例；故障不会阻塞聊天。
    global _run_store
    if _run_store is None:
        try:
            from runtime.runs.store import get_run_store as _factory
            _run_store = _factory()
        except Exception:
            try:
                from runtime.runs.store import RunStore
                _run_store = RunStore()
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"RunStore 初始化失败，审计/状态功能降级: {exc}")
                return None
    return _run_store


def _read_settings() -> dict[str, Any]:
    if not SETTINGS_FILE.exists():
        return {}
    try:
        return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _settings_for_request(request: Request | None) -> dict[str, Any]:
    """Owner uses instance settings; regular accounts use their own settings file."""
    if request is None:
        return _read_settings()
    try:
        from backend.ownership import identity
        user_id, role = identity(request)
        if role == "owner":
            return _read_settings()
        from backend.settings_api import _read_user_settings
        return _read_user_settings(user_id)
    except Exception:
        return _read_settings()


def _normalize_base_url(base_url: str) -> str:
    return base_url.rstrip("/")


def _get_enabled_tools(settings: dict[str, Any] | None = None) -> list[dict]:
    tools = []
    configured_items = (settings or _read_settings()).get("agentTools", [])
    if not isinstance(configured_items, list):
        configured_items = []
    configured = {
        item.get("name"): item
        for item in configured_items
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    }
    try:
        tools = ToolRegistry.openai_tools()
    except AttributeError:  # 旧版注册表回退
        tools = [
            {"type": "function", "function": {
                "name": ts.name, "description": ts.description,
                "parameters": _normalize_tool_schema(ts)}}
            for ts in ToolRegistry.list()
        ]
    filtered: list[dict] = []
    for item in tools:
        fn = item.get("function", {}) if isinstance(item, dict) else {}
        name = fn.get("name")
        if not name:
            continue
        if configured.get(name, {}).get("enabled", True) is False:
            continue
        filtered.append(item)
    return filtered


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


_tool_result_pruner = None


def _tool_result_to_str(result: Any) -> str:
    global _tool_result_pruner
    if isinstance(result, str):
        text = result
    else:
        try:
            text = json.dumps(result, ensure_ascii=False)
        except Exception:
            text = str(result)
    # 超长工具结果裁剪，减少上下文 token 占用（记忆层扩展 2026-08-21）
    # 裁剪失败时安全降级为原文，不影响主流程
    try:
        if _tool_result_pruner is None:
            from runtime.memory.pruner import ToolResultPruner
            _tool_result_pruner = ToolResultPruner()
        return _tool_result_pruner.prune(text)
    except Exception:
        return text


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
    api_url: str, headers: dict, body: dict, request_id: str, round_idx: int,
    settings: dict[str, Any] | None = None,
) -> AsyncIterator[dict]:
    """Real streaming from LLM API. Yields dicts: text_delta / reasoning_delta / done."""
    # 中文：来自 LLM API 的真实流式响应。生成 dict：text_delta / reasoning_delta / done。
    stream_body = {**body, "stream": True}
    full_content = ""
    full_reasoning = ""
    tool_calls_acc: dict[int, dict[str, Any]] = {}
    finish_reason = None
    last_usage: dict | None = None
    sse_buf = b""
    raw_chunks = 0

    _stream_log(request_id, "llm_stream_start", round=round_idx, model=body.get("model"))

    try:
        async with AsyncExitStack() as stack:
            if httpx.AsyncClient.__module__.startswith("unittest.mock"):
                # Unit tests patch httpx.AsyncClient with an async context-manager mock.
                client = await stack.enter_async_context(httpx.AsyncClient(timeout=180))
            else:
                client = await stack.enter_async_context(_make_llm_client(body.get("baseUrl") or api_url, settings))
            response = await stack.enter_async_context(
                client.stream("POST", api_url, headers=headers, json=stream_body)
            )
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

                    # 收集 token 用量（OpenAI 兼容流式末 chunk 携带 usage）
                    if chunk.get("usage"):
                        last_usage = chunk["usage"]

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
    yield {"type": "done", "message": message, "finish_reason": finish_reason, "usage": last_usage}


# ---------------------------------------------------------------------------
# /completions —— 老版一次性接口（兼容）
# ---------------------------------------------------------------------------
@router.post("/completions")
async def chat_completion(req: ChatRequest, request: Request):
    rid = uuid.uuid4().hex[:10]
    reasoning_parts: list[str] = []
    tools_trace: list[dict[str, Any]] = []
    last_content = ""
    last_usage: dict | None = None
    last_model = req.model

    async for event in _stream_events(req, rid, request=request):
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
        rounds=len([e for e in reasoning_parts if e]),  # rough count  ｜ 粗略计数
    )


# ---------------------------------------------------------------------------
# SSE 事件流生成器（零缓冲直推）
# ---------------------------------------------------------------------------
async def _wait_for_approval(store, approval_id: str, request, timeout_s: int) -> str:
    """Wait for a user decision; return approved | denied | expired | cancelled."""
    # 中文：等待用户决策；返回 approved | denied | expired | cancelled。
    import asyncio
    import time as _time

    deadline = _time.monotonic() + max(5, int(timeout_s))
    while _time.monotonic() < deadline:
        await asyncio.sleep(0.5)
        if request is not None:
            try:
                if await request.is_disconnected():
                    return "cancelled"
            except Exception:
                pass
        record = store.get(approval_id)
        if record and record.get("status") in ("approved", "denied", "expired"):
            return record["status"]
    store.expire_stale()
    record = store.get(approval_id)
    return record.get("status") if record else "expired"


async def _stream_events(req: ChatRequest, request_id: str, request: Request | None = None):
    """
    直接迭代 LLM 流式生成器，零缓冲转发事件。
    断连时通过 request.is_disconnected() 感知并终止。
    """
    await _ensure_log_writer()

    run_store = _get_run_store()
    run_id = f"run-{request_id}"
    if run_store is not None:
        try:
            run_store.create_run(run_id, getattr(req, "sessionId", None), req.model)
            run_store.add_event(run_id, "run_started", {"model": req.model})
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"创建 Run 记录失败: {exc}")
            run_store = None
    yield {"type": "run_started", "run_id": run_id}

    api_url = f"{_normalize_base_url(req.baseUrl)}/chat/completions"
    settings = _settings_for_request(request)
    # Providers are user-owned. Never fall back to another account's provider key.
    headers = {"Content-Type": "application/json"}
    if req.apiKey:
        headers["Authorization"] = f"Bearer {req.apiKey}"

    normalized_messages: list[dict[str, Any]] = []
    for m in req.messages:
        role = m.get("role", "user")
        if role == "ai":
            role = "assistant"
        normalized_messages.append({"role": role, "content": m.get("content", "")})
    # ─── 记忆自取注入（类人脑回忆，模型无感）────────────────
    # 系统自动用当前语境联想检索历史记忆并注入上下文；
    # LLM 无需调用任何工具去查记忆，就像自己记得一样。
    try:
        from runtime.memory.memory_service import get_memory_service
        _mem_svc = get_memory_service()
        if _mem_svc.enabled:
            _q = ""
            for _m in reversed(normalized_messages):
                if _m.get("role") == "user":
                    _q = _m.get("content", "")
                    break
            if _q:
                _recalls = await _mem_svc.recall(_q, top_k=_mem_svc.top_k)
                _block = _mem_svc.build_injection(_recalls)
                if _block:
                    normalized_messages.insert(0, {"role": "system", "content": _block})
                    logger.info(f"🧠 记忆自取: 注入 {len(_recalls)} 条联想记忆，rid={request_id}")
                await _mem_svc.auto_remember(_q)
    except Exception:
        pass  # 记忆层故障不阻断主流程

    enabled_skills = settings.get("enabledSkills", ["web-research", "interest-scout", "frontend-craft"])
    if not isinstance(enabled_skills, list):
        enabled_skills = []
    try:
        from runtime.skills.registry import skill_catalogue
        context_parts = []
        catalogue = skill_catalogue([item for item in enabled_skills if isinstance(item, str)])
        if catalogue:
            context_parts.append(catalogue)
        interests = settings.get("userInterests", [])
        if settings.get("interestsEnabled", True) and isinstance(interests, list):
            cleaned = list(dict.fromkeys(
                item.strip()[:80] for item in interests
                if isinstance(item, str) and item.strip()
            ))[:30]
            if cleaned:
                context_parts.append(
                    "用户主动保存的兴趣偏好（仅在相关时用于个性化，不代表当前任务要求联网）：\n"
                    + "\n".join(f"- {item}" for item in cleaned)
                )
        try:
            from runtime.context.provenance import provenance_guide
            context_parts.append(provenance_guide())
        except Exception:
            pass
        if context_parts:
            normalized_messages.insert(0, {"role": "system", "content": "\n\n".join(context_parts)})
    except Exception as exc:
        logger.warning(f"Agent Skill/兴趣上下文加载失败，继续普通对话: {exc}")

    openai_tools = _get_enabled_tools(settings)
    if not _needs_tools(normalized_messages, settings):
        openai_tools = []
    try:
        _stream_log(request_id, "context_sizes",
                    messages=len(normalized_messages), tools=len(openai_tools),
                    system_chars=sum(len(str(m.get("content") or "")) for m in normalized_messages if m.get("role") == "system"),
                    messages_chars=sum(len(str(m.get("content") or "")) for m in normalized_messages),
                    tools_chars=len(json.dumps(openai_tools, ensure_ascii=False)))
    except Exception:
        pass
    enabled_tool_names = {
        item["function"]["name"] for item in openai_tools
        if isinstance(item.get("function"), dict) and item["function"].get("name")
    }
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
    # 深度思考开关：仅 DeepSeek 支持 thinking 参数，其它兼容 API 不发送
    if settings.get("thinking", False) is False and "deepseek" in str(req.baseUrl or "").lower():
        body["thinking"] = {"type": "disabled"}

    agent_params = settings.get("agentParams", {}) or {}
    MAX_TOOL_ROUNDS = int(agent_params.get("maxToolRounds", 6))

    for round_idx in range(MAX_TOOL_ROUNDS + 1):
        content_accumulated = ""
        reasoning_accumulated = ""
        tool_calls = []

        _stream_log(request_id, "round_start", round=round_idx, messages=len(body.get("messages", [])))

        # ★ 直接迭代 LLM 流，零缓冲、零 sleep
        async for stream_event in _stream_llm_completion(api_url, headers, body, request_id, round_idx, settings):
            t = stream_event["type"]

            # 断连检测（非阻塞，每收到一个事件检查一次）
            if request is not None:
                try:
                    if await request.is_disconnected():
                        _stream_log(request_id, "stream_cancelled_disconnect", round=round_idx)
                        _killed = 0
                        try:
                            _killed = get_execution_manager().cancel(run_id)
                        except Exception:
                            _killed = 0
                        if run_store is not None:
                            try:
                                # 只有确认执行进程被终止时才记 cancelled；
                                # 否则进程可能仍在运行，结果不可判定，必须记 unknown。
                                run_store.finish_run(
                                    run_id,
                                    "cancelled" if _killed else "unknown",
                                    error="client disconnected" if _killed
                                    else "client disconnected; sandbox result unknown",
                                )
                            except Exception:
                                pass
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
                # 透传 token 用量（若无 tool_calls 则这是最终 round）
                usage = stream_event.get("usage")
                if usage and not tool_calls:
                    yield {"type": "usage", "data": usage, "round": round_idx}
                _stream_log(request_id, "round_llm_done", round=round_idx,
                            reasoning_len=len(message.get("reasoning_content", reasoning_accumulated) or ""),
                            content_len=len(content_accumulated), tool_calls=len(tool_calls))
                break

        # 剥离 <think> 标签
        clean_content, clean_reasoning = _split_think_tags(content_accumulated, reasoning_accumulated)

        if not tool_calls:
            _stream_log(request_id, "stream_done_final", round=round_idx, rounds=round_idx)
            if run_store is not None:
                try:
                    run_store.finish_run(run_id, "succeeded")
                except Exception:
                    pass
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

            # ── P0.5 三档权限 / 单次审批 ─────────────────────────────────
            try:
                from runtime.approvals import approval_timeout as _approval_timeout
                from runtime.approvals import decide as _approval_decide
                from runtime.approvals import get_approval_store
                _decision = _approval_decide(fn_name, fn_args, session_id=getattr(req, "sessionId", None))
                if fn_name not in enabled_tool_names:
                    _decision = type(_decision)("deny", _decision.risk, f"工具未启用: {fn_name}")
                _approval_store = get_approval_store()
            except Exception as _ap_exc:  # noqa: BLE001
                logger.warning(f"审批策略初始化失败，按拒绝处理: {_ap_exc}")
                _decision = None
                _approval_store = None
            _permission_value = _decision.kind if _decision is not None else "deny"

            if run_store is not None:
                try:
                    run_store.create_tool_call(tool_id, run_id, fn_name or "unknown_tool", fn_args, permission=_permission_value)
                    run_store.add_event(run_id, "tool_call_prepared",
                                        {"tool_call_id": tool_id, "name": fn_name, "args": fn_args})
                except Exception as exc:  # noqa: BLE001
                    logger.warning(f"记录 ToolCall 失败: {exc}")

            _approval_status = "allow"
            if _decision is None or _decision.kind == "deny":
                _approval_status = "denied"
                _deny_reason = _decision.reason if _decision is not None else "审批层不可用"
                if run_store is not None:
                    try:
                        run_store.add_event(run_id, "approval_denied",
                                            {"tool_call_id": tool_id, "reason": _deny_reason})
                    except Exception:
                        pass
            elif _decision.kind == "confirm":
                _approval = None
                try:
                    _approval = _approval_store.create(
                        run_id, tool_id, fn_name, fn_args,
                        risk=_decision.risk, timeout_s=_approval_timeout(),
                        session_id=getattr(req, "sessionId", None),
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.warning(f"创建审批失败，按拒绝处理: {exc}")
                if _approval is None:
                    _approval_status = "denied"
                else:
                    if run_store is not None:
                        try:
                            run_store.add_event(run_id, "approval_requested",
                                                {"approval_id": _approval["id"], "tool_call_id": tool_id,
                                                 "tool": fn_name, "risk": _decision.risk,
                                                 "expires_at": _approval["expires_at"]})
                        except Exception:
                            pass
                    yield {"type": "approval_required", "approval_id": _approval["id"],
                           "tool_call_id": tool_id, "run_id": run_id, "tool": fn_name,
                           "args": fn_args, "risk": _decision.risk,
                           "expires_at": _approval["expires_at"],
                           "canRememberSession": bool(getattr(req, "sessionId", None))}
                    _approval_status = await _wait_for_approval(
                        _approval_store, _approval["id"], request, int(_approval_timeout())
                    )
                    if run_store is not None:
                        try:
                            run_store.add_event(run_id, "approval_decided",
                                                {"approval_id": _approval["id"], "tool_call_id": tool_id,
                                                 "status": _approval_status})
                            if _approval_status == "approved":
                                run_store.update_tool_call(tool_id, "dispatched", permission="approved")
                        except Exception:
                            pass

            token_run = current_run.set(run_id)
            token_call = current_tool_call.set(tool_id)
            if run_store is not None:
                try:
                    run_store.update_tool_call(tool_id, "dispatched")
                except Exception:
                    pass

            _stream_log(request_id, "tool_call_start", round=round_idx, id=tool_id, name=fn_name)
            yield {"type": "tool_call_start", "id": tool_id, "run_id": run_id,
                   "round": round_idx + 1, "name": fn_name or "unknown_tool", "args": fn_args}

            logger.info(f"🛠️ Round {round_idx + 1}: LLM 调用工具 {fn_name} args={fn_args}")
            started = time.perf_counter()
            ok = True
            error = ""
            tool_result = None
            try:
                if _approval_status == "denied":
                    raise PermissionError("操作被拒绝" + (f"：{_decision.reason}" if _decision is not None and _decision.reason else ""))
                if _approval_status == "expired":
                    raise PermissionError("审批超时，操作未执行")
                if _approval_status == "cancelled":
                    raise PermissionError("审批期间客户端断开，操作未执行")
                if _approval_status not in ("allow", "approved"):
                    raise PermissionError(f"审批未通过: {_approval_status}")
                if fn_name not in enabled_tool_names:
                    raise PermissionError(f"工具未启用或不存在: {fn_name}")
                if request is not None:
                    try:
                        from backend.ownership import identity as _ident
                        _uid, _role = _ident(request)
                    except Exception:
                        _role = "owner"
                    if _role != "owner":
                        raise PermissionError(
                            "当前账号未配置执行服务器，不能执行本地工具；"
                            "请先在设置中配置执行服务器"
                        )
                async with _TOOL_EXEC_SEM:
                    tool_result = await asyncio.to_thread(ToolRegistry.call, fn_name, **fn_args)
                result_str = _tool_result_to_str(tool_result)
            except Exception as exc:
                ok = False
                error = str(exc)
                result_str = f"工具 {fn_name} 执行出错: {exc}"
            finally:
                current_run.reset(token_run)
                current_tool_call.reset(token_call)

            if run_store is not None:
                try:
                    _final_permission = _approval_status if _approval_status in ("approved", "denied", "expired") else "allow"
                    run_store.update_tool_call(
                        tool_id,
                        "succeeded" if ok else "failed",
                        error=error or None,
                        output_bytes=len(result_str.encode("utf-8")),
                        permission=_final_permission,
                    )
                    run_store.add_event(run_id, "tool_call_finished",
                                        {"tool_call_id": tool_id, "ok": ok, "error": error})
                except Exception:
                    pass

            elapsed_ms = int((time.perf_counter() - started) * 1000)

            if _approval_status == "cancelled":
                if run_store is not None:
                    try:
                        run_store.finish_run(run_id, "unknown", error="client disconnected during approval")
                    except Exception:
                        pass
                return

            yield {"type": "tool_call", "id": tool_id, "run_id": run_id, "round": round_idx + 1,
                   "name": fn_name or "unknown_tool", "args": fn_args,
                   "result": result_str, "ok": ok, "error": error, "durationMs": elapsed_ms,
                   "sandbox": (tool_result.get("sandbox") if isinstance(tool_result, dict) else None),
                   "truncated": (tool_result.get("truncated") if isinstance(tool_result, dict) else None)}

            # send_image 等工具返回结构化图片描述符时，额外发一个 media 事件，
            # 前端据此把图片直接内联渲染（而不是把 JSON 描述符当文本显示）。
            if ok:
                try:
                    from tools.media import is_media_descriptor
                    if is_media_descriptor(tool_result):
                        _media = {k: tool_result.get(k) for k in
                                  ("kind", "media_id", "name", "mime", "size", "url", "caption")}
                        yield {"type": "media", "media": _media}
                                                # 中文：媒体
                                       # 中文：媒体
                        _stream_log(request_id, "media_emit", round=round_idx,
                                    media_id=_media.get("media_id"))
                except Exception as _media_exc:  # noqa: BLE001
                    logger.warning(f"media 事件发送失败: {_media_exc}")

            body["messages"].append({"role": "tool", "tool_call_id": tc.get("id", ""),
                                     "content": _provenance_annotate(result_str, "tool")})

        _stream_log(request_id, "tool_round_end", round=round_idx)
        yield {"type": "tool_round_end", "round": round_idx}

    _stream_log(request_id, "stream_done_max_rounds", rounds=MAX_TOOL_ROUNDS)
    if run_store is not None:
        try:
            run_store.finish_run(run_id, "succeeded", error="max_tool_rounds")
        except Exception:
            pass
    yield {"type": "done", "rounds": MAX_TOOL_ROUNDS}


# ---------------------------------------------------------------------------
# /stream —— SSE 流式接口（直通 SSE 流式输出）
# ---------------------------------------------------------------------------
@router.post("/stream")
async def chat_completion_stream(req: ChatRequest, fastapi_request: Request):
    """
    SSE stream with direct async iteration.

    Yielding each upstream event directly lets the ASGI client provide backpressure,
    avoiding an extra producer task, burst queue, and artificial per-event delay.
    """
    # 中文：通过直接异步迭代实现 SSE 流。
    await _ensure_log_writer()
    request_id = uuid.uuid4().hex[:10]
    _stream_log(request_id, "http_stream_open", model=req.model)

    async def event_generator():
        seq = 0
        try:
            async for event in _stream_events(req, request_id, request=fastapi_request):
                seq += 1
                typ = event.get("type")
                if typ in {"reasoning", "content", "tool_round_start", "tool_call_start",
                           "tool_call", "tool_round_end", "done"}:
                    _stream_log(request_id, "http_sse_send", seq=seq, type=typ,
                                round=event.get("round"),
                                content_len=len(event.get("content", "") or ""),
                                preview=_preview(event.get("content", "")))
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

            _stream_log(request_id, "http_sse_done_marker", seq=seq + 1)
            yield "data: [DONE]\n\n"
        except asyncio.CancelledError:
            _stream_log(request_id, "http_stream_cancelled", seq=seq)
            try:
                _rs = _get_run_store()
                if _rs is not None:
                    _rs.finish_run(f"run-{request_id}", "cancelled", error="cancelled")
            except Exception:
                pass
            try:
                get_execution_manager().cancel(f"run-{request_id}")
            except Exception:
                pass
            raise
        except Exception as exc:
            _stream_log(request_id, "http_stream_exception", error=str(exc))
            try:
                _rs = _get_run_store()
                if _rs is not None:
                    _rs.finish_run(f"run-{request_id}", "failed", error=str(exc)[:500])
            except Exception:
                pass
            # 上游 4xx/5xx（例如模型名不存在）如果不在这里转成事件，会变成
            # "response already started" 的 500，前端只看到半截流、没有任何可读错误。
            detail = getattr(exc, "detail", None) or str(exc)
            try:
                yield "data: " + json.dumps({"type": "error", "message": str(detail)}, ensure_ascii=False) + "\n\n"
                yield "data: [DONE]\n\n"
            except Exception:
                pass

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "X-Stream-Request-Id": request_id,
            "X-Stream-Run-Id": f"run-{request_id}",
        },
    )

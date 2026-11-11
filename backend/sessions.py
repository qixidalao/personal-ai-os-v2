"""
Personal AI OS — 会话管理 API（多用户 Phase 1：归属隔离）
每个会话一个独立 JSON 文件；meta.owner_user_id 标记归属。
owner 可看全部；member 只能看/改/删自己的，越权一律 404。
"""
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from pathlib import Path
import json
import uuid
from datetime import datetime

from backend.ownership import can_access_session, identity, owner_user_id, read_session_meta

router = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])

STORAGE_DIR = Path("storage/sessions")
STORAGE_DIR.mkdir(parents=True, exist_ok=True)


class Message(BaseModel):
    id: str
    role: str
    content: str
    streaming: bool = False
    toolCall: dict | None = None
    toolExpanded: bool = False
    branches: list | None = None
    branchIdx: int = 0
    reasoning: str | None = None
    tools: list[dict] | None = None
    segments: list[dict] | None = None
    traceExpanded: bool = False
    reasoningExpanded: bool = False
    toolsExpanded: bool = False
    usage: dict | None = None
    images: list[str] | None = None
    createdAt: int | None = None
    finishedAt: int | None = None
    tokPerSec: int | None = None
    cachedTokens: int | None = None
    cumTokens: int | None = None
    source: str | None = None
    trust: str | None = None


class SessionMeta(BaseModel):
    id: str
    icon: str = "💬"
    title: str = "新对话"
    preview: str = ""
    time: str = ""
    tag: str = ""
    created_at: str = ""
    updated_at: str = ""
    owner_user_id: str = ""


class SessionMetaPatch(BaseModel):
    icon: str | None = None
    title: str | None = None
    preview: str | None = None
    tag: str | None = None


class SessionData(BaseModel):
    meta: SessionMeta
    messages: list[Message] = []


def _session_path(session_id: str) -> Path:
    return STORAGE_DIR / f"{session_id}.json"


def _read_session(session_id: str) -> SessionData:
    path = _session_path(session_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Session not found")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return SessionData(**data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read session: {e}")


def _write_session(session_id: str, data: SessionData):
    path = _session_path(session_id)
    path.write_text(
        json.dumps(data.model_dump(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _checked_session(request: Request, session_id: str) -> SessionData:
    data = _read_session(session_id)
    user_id, role = identity(request)
    if not can_access_session(data.meta.model_dump(), user_id, role):
        raise HTTPException(status_code=404, detail="Session not found")
    return data


@router.get("")
async def list_sessions(request: Request):
    user_id, role = identity(request)
    sessions = []
    for f in sorted(STORAGE_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        if f.stat().st_size == 0:
            f.unlink(missing_ok=True)
            continue
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            meta = data.get("meta", {}) or {}
        except Exception:
            f.unlink(missing_ok=True)
            continue
        # 旧数据（无 owner_user_id）归 owner；member 不可见
        if not can_access_session(meta, user_id, role):
            continue
        sessions.append(meta)
    return {"sessions": sessions}


@router.post("")
async def create_session(request: Request, meta: SessionMeta | None = None):
    user_id, role = identity(request)
    now = datetime.now().isoformat()
    session_id = meta.id if meta and meta.id else f"s{uuid.uuid4().hex[:8]}"
    if meta is None:
        meta = SessionMeta(id=session_id, title="新对话", time=now, created_at=now, updated_at=now)
    else:
        meta.id = session_id
        meta.created_at = meta.created_at or now
        meta.updated_at = now
    # 归属由服务端决定，忽略客户端伪造
    meta.owner_user_id = user_id or (owner_user_id() if role == "owner" else "")
    data = SessionData(meta=meta, messages=[])
    _write_session(session_id, data)
    return {"session": data.model_dump()}


@router.get("/{session_id}")
async def get_session(request: Request, session_id: str):
    data = _checked_session(request, session_id)
    return {"session": data.model_dump()}


@router.put("/{session_id}")
async def update_session(request: Request, session_id: str, data: SessionData):
    existing = _checked_session(request, session_id)
    user_id, role = identity(request)
    now = datetime.now().isoformat()
    data.meta.id = session_id
    data.meta.updated_at = now
    if not data.meta.created_at:
        data.meta.created_at = now
    # 归属不可通过接口改写
    data.meta.owner_user_id = existing.meta.owner_user_id or (user_id if role == "owner" else "")
    _write_session(session_id, data)
    return {"status": "ok"}


@router.delete("/{session_id}")
async def delete_session(request: Request, session_id: str):
    _checked_session(request, session_id)
    path = _session_path(session_id)
    if path.exists():
        path.unlink()
    return {"status": "ok"}


@router.put("/{session_id}/messages")
async def update_messages(request: Request, session_id: str, messages: list[Message]):
    data = _checked_session(request, session_id)
    data.messages = messages
    data.meta.updated_at = datetime.now().isoformat()
    if messages:
        last = messages[-1]
        data.meta.preview = last.content[:50] if last.content else ""
    _write_session(session_id, data)
    return {"status": "ok"}


@router.patch("/{session_id}/meta")
async def patch_session_meta(request: Request, session_id: str, meta: SessionMetaPatch):
    data = _checked_session(request, session_id)
    if meta.title is not None:
        data.meta.title = meta.title
    if meta.icon is not None:
        data.meta.icon = meta.icon
    if meta.tag is not None:
        data.meta.tag = meta.tag
    if meta.preview is not None:
        data.meta.preview = meta.preview
    data.meta.updated_at = datetime.now().isoformat()
    _write_session(session_id, data)
    return {"status": "ok", "meta": data.meta.model_dump()}

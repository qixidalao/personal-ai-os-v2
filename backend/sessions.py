"""
Personal AI OS — 会话管理 API
每个会话一个独立 JSON 文件，落盘存储
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from pathlib import Path
import json
import uuid
from datetime import datetime

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


class SessionMeta(BaseModel):
    id: str
    icon: str = "💬"
    title: str = "新对话"
    preview: str = ""
    time: str = ""
    tag: str = ""
    created_at: str = ""
    updated_at: str = ""


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


@router.get("")
async def list_sessions():
    sessions = []
    for f in sorted(STORAGE_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        if f.stat().st_size == 0:
            f.unlink(missing_ok=True)
            continue
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            sessions.append(data.get("meta", {}))
        except:
            f.unlink(missing_ok=True)
            continue
    return {"sessions": sessions}


@router.post("")
async def create_session(meta: SessionMeta | None = None):
    now = datetime.now().isoformat()
    session_id = meta.id if meta and meta.id else f"s{uuid.uuid4().hex[:8]}"
    if meta is None:
        meta = SessionMeta(id=session_id, title="新对话", time=now, created_at=now, updated_at=now)
    else:
        meta.id = session_id
        meta.created_at = meta.created_at or now
        meta.updated_at = now
    data = SessionData(meta=meta, messages=[])
    _write_session(session_id, data)
    return {"session": data.model_dump()}


@router.get("/{session_id}")
async def get_session(session_id: str):
    data = _read_session(session_id)
    return {"session": data.model_dump()}


@router.put("/{session_id}")
async def update_session(session_id: str, data: SessionData):
    now = datetime.now().isoformat()
    data.meta.id = session_id
    data.meta.updated_at = now
    if not data.meta.created_at:
        data.meta.created_at = now
    _write_session(session_id, data)
    return {"status": "ok"}


@router.delete("/{session_id}")
async def delete_session(session_id: str):
    path = _session_path(session_id)
    if path.exists():
        path.unlink()
    return {"status": "ok"}


@router.put("/{session_id}/messages")
async def update_messages(session_id: str, messages: list[Message]):
    try:
        data = _read_session(session_id)
        data.messages = messages
        data.meta.updated_at = datetime.now().isoformat()
        if messages:
            last = messages[-1]
            data.meta.preview = last.content[:50] if last.content else ""
        _write_session(session_id, data)
        return {"status": "ok"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{session_id}/meta")
async def patch_session_meta(session_id: str, meta: SessionMetaPatch):
    """部分更新会话元信息（如标题）"""
    try:
        data = _read_session(session_id)
        now = datetime.now().isoformat()
        if meta.title is not None:
            data.meta.title = meta.title
        if meta.icon is not None:
            data.meta.icon = meta.icon
        if meta.tag is not None:
            data.meta.tag = meta.tag
        if meta.preview is not None:
            data.meta.preview = meta.preview
        data.meta.updated_at = now
        _write_session(session_id, data)
        return {"status": "ok", "meta": data.meta.model_dump()}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

"""Ownership helpers for multi-user isolation (AIOS scope only)."""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import Request

SESSIONS_DIR = Path("storage/sessions")


def owner_user_id() -> str:
    """第一个 owner 账号的 user_id（旧数据默认归属）。"""
    try:
        from backend.auth import _db_conn, _db_lock

        with _db_lock:
            row = _db_conn().execute(
                "SELECT id FROM users WHERE role='owner' AND status='active' ORDER BY created_at LIMIT 1"
            ).fetchone()
        return str(row["id"]) if row else ""
    except Exception:
        return ""


def identity(request: Request) -> tuple[str, str]:
    """返回 (user_id, role)；本机/Bearer/鉴权关闭时视为 owner。"""
    try:
        from backend.auth import DISABLE_AUTH, _bearer_ok, is_local_access, session_from_scope

        session = session_from_scope(request.scope)
        if session:
            return str(session.get("user_id") or ""), str(session.get("role") or "member")
        if is_local_access(request.scope) or _bearer_ok(request.scope) or DISABLE_AUTH:
            return owner_user_id(), "owner"
    except Exception:
        pass
    return "", ""


def read_session_meta(session_id: str) -> dict | None:
    path = SESSIONS_DIR / f"{session_id}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("meta") or {}
    except (OSError, json.JSONDecodeError):
        return None


def can_access_session(meta: dict | None, user_id: str, role: str) -> bool:
    if role == "owner":
        return True
    if not meta or not user_id:
        return False
    return str(meta.get("owner_user_id") or "") == user_id


def owned_session_ids(user_id: str) -> set[str]:
    ids: set[str] = set()
    if not user_id:
        return ids
    for f in SESSIONS_DIR.glob("*.json"):
        try:
            meta = json.loads(f.read_text(encoding="utf-8")).get("meta") or {}
        except (OSError, json.JSONDecodeError):
            continue
        if str(meta.get("owner_user_id") or "") == user_id:
            ids.add(str(meta.get("id") or f.stem))
    return ids

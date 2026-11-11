"""Approval API with session-scope grants (P2)."""
# 中文：带会话范围授权的审批 API（P2）。
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from runtime.approvals import get_approval_store
from backend.ownership import identity, owned_session_ids

router = APIRouter(prefix="/api/v1/approvals", tags=["approvals"])


def _role(request: Request) -> tuple[str, str]:
    return identity(request)


def _can_access_record(request: Request, record: dict | None) -> bool:
    if not record:
        return False
    user_id, role = _role(request)
    if role == "owner":
        return True
    if role != "member" or not user_id:
        return False
    try:
        from backend.ownership import can_access_session, read_session_meta
        session_id = str(record.get("session_id") or "")
        return bool(session_id and can_access_session(read_session_meta(session_id), user_id, role))
    except Exception:
        return False


class ApprovalDecisionRequest(BaseModel):
    decision: str = Field(..., description="approve 或 deny")
    remember: str | None = Field(None, description="once（默认）或 session：本会话授权该工具")
    reason: str | None = None


@router.get("")
async def list_approvals(request: Request, status: str = "pending", limit: int = 50):
    store = get_approval_store()
    user_id, role = _role(request)
    if role == "owner":
        rows = store.list_pending(limit=limit) if status == "pending" else []
    elif role == "member":
        own = owned_session_ids(user_id)
        rows = [r for sid in own for r in store.list_by_session(sid) if r.get("status") == status][:max(1, min(limit, 100))]
    else:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return {"approvals": rows}


@router.get("/grants")
async def list_all_grants(request: Request):
    store = get_approval_store()
    user_id, role = _role(request)
    if role == "owner":
        return {"grants": store.list_all_grants()}
    if role != "member":
        raise HTTPException(status_code=401, detail="Unauthorized")
    own = owned_session_ids(user_id)
    return {"grants": [g for sid in own for g in store.list_grants(sid)]}


@router.get("/{approval_id}")
async def get_approval(approval_id: str, request: Request):
    record = get_approval_store().get(approval_id)
    if not _can_access_record(request, record):
        raise HTTPException(status_code=404, detail="Approval not found")
    return {"approval": record}


@router.post("/{approval_id}")
async def decide_approval(approval_id: str, payload: ApprovalDecisionRequest, request: Request):
    decision = payload.decision.strip().lower()
    if decision not in ("approve", "deny", "approved", "denied"):
        raise HTTPException(status_code=422, detail="decision 必须是 approve 或 deny")
    store = get_approval_store()
    before = store.get(approval_id)
    if not _can_access_record(request, before):
        raise HTTPException(status_code=404, detail="Approval not found")
    user_id, role = _role(request)
    record = store.decide(approval_id, decision, decided_by="admin" if role == "owner" else user_id, reason=payload.reason)
    if record is None:
        raise HTTPException(status_code=404, detail="Approval not found")

    granted = False
    if (
        record.get("status") == "approved"
        and (payload.remember or "").lower() == "session"
        and record.get("session_id")
    ):
        store.add_grant(record["session_id"], record["tool"], record.get("run_id"))
        granted = True
    return {"approval": record, "session_grant": granted}


@router.delete("/grants/{session_id}/{tool}")
async def revoke_grant(session_id: str, tool: str, request: Request):
    user_id, role = _role(request)
    if role != "owner" and session_id not in owned_session_ids(user_id):
        raise HTTPException(status_code=404, detail="Grant not found")
    store = get_approval_store()
    removed = store.revoke_grant(session_id, tool)
    return {"revoked": removed, "session_id": session_id, "tool": tool}


@router.get("/grants/{session_id}")
async def list_grants(session_id: str, request: Request):
    user_id, role = _role(request)
    if role != "owner" and session_id not in owned_session_ids(user_id):
        raise HTTPException(status_code=404, detail="Grant not found")
    return {"grants": get_approval_store().list_grants(session_id)}

"""Personal AI OS — Run / ToolCall 审计查询 API（P2：分页 + 导出）."""
from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response

from runtime.runs.store import DEFAULT_RUN_LIMIT, MAX_RUN_LIMIT, RunStore
from backend.ownership import can_access_session, identity, owned_session_ids, read_session_meta

router = APIRouter(prefix="/api/v1/runs", tags=["runs"])

_STORE_STATE_ATTR = "run_store"


def _can_access_run(request: Request, run: dict | None) -> bool:
    """owner 全部可见；member 仅自己会话下的 run。"""
    if not run:
        return False
    user_id, role = identity(request)
    if role == "owner":
        return True
    session_id = run.get("session_id")
    if not session_id:
        return False
    return can_access_session(read_session_meta(str(session_id)), user_id, role)


def get_run_store(request: Request) -> RunStore:
    store = getattr(request.app.state, _STORE_STATE_ATTR, None)
    if not isinstance(store, RunStore):
        store = RunStore()
        setattr(request.app.state, _STORE_STATE_ATTR, store)
    return store


def _run_markdown(run: dict, tool_calls: list[dict], events: list[dict]) -> str:
    lines = [f"# Run `{run.get('id')}`", ""]
    lines.append(f"- 状态: **{run.get('status')}**")
    lines.append(f"- 模型: `{run.get('model')}`")
    lines.append(f"- 会话: `{run.get('session_id') or '-'}`")
    lines.append(f"- 开始: {run.get('started_at')}")
    lines.append(f"- 结束: {run.get('finished_at') or '-'}")
    if run.get("error"):
        lines.append(f"- 错误: {run.get('error')}")
    lines += ["", "## 工具调用", ""]
    if tool_calls:
        lines.append("| # | 工具 | 状态 | 权限 | 耗时 | 产物 bytes | 错误 |")
        lines.append("|---|---|---|---|---|---:|---|")
        for i, tc in enumerate(tool_calls, 1):
            lines.append(
                f"| {i} | `{tc.get('name')}` | {tc.get('status')} | {tc.get('permission_decision') or '-'} "
                f"| {tc.get('duration_ms') if tc.get('duration_ms') is not None else '-'} "
                f"| {tc.get('output_bytes') if tc.get('output_bytes') is not None else '-'} "
                f"| {tc.get('error') or ''} |"
            )
    else:
        lines.append("（本次运行没有工具调用）")
    lines += ["", "## 事件时间线", ""]
    for ev in events:
        lines.append(f"- `#{ev.get('seq')}` **{ev.get('type')}** @ {ev.get('ts')}")
        if ev.get("data"):
            try:
                lines.append("  ```json")
                lines.append("  " + json.dumps(ev["data"], ensure_ascii=False))
                lines.append("  ```")
            except Exception:
                pass
    lines += ["", "## 参数明细（脱敏前仅本机查看）", ""]
    for i, tc in enumerate(tool_calls, 1):
        lines.append(f"### {i}. {tc.get('name')}")
        lines.append("```json")
        try:
            parsed = json.loads(tc.get("args_json") or "{}")
            lines.append(json.dumps(parsed, ensure_ascii=False, indent=2))
        except Exception:
            lines.append(str(tc.get("args_json")))
        lines.append("```")
    return "\n".join(lines) + "\n"


@router.get("", summary="Run 列表（分页）")
def list_runs(
    request: Request,
    session_id: str | None = Query(None, description="按会话过滤；缺省返回全部"),
    limit: int = Query(20, ge=1, le=MAX_RUN_LIMIT, description="返回条数上限"),
    offset: int = Query(0, ge=0, description="跳过条数（分页）"),
    store: RunStore = Depends(get_run_store),
) -> dict[str, Any]:
    user_id, role = identity(request)
    if role != "owner":
        if session_id:
            if not can_access_session(read_session_meta(session_id), user_id, role):
                raise HTTPException(status_code=404, detail="Session not found")
            runs = store.list_runs(session_id=session_id, limit=limit, offset=offset)
            total = store.count_runs(session_id=session_id)
        else:
            owned = owned_session_ids(user_id)
            all_runs = store.list_runs(limit=MAX_RUN_LIMIT, offset=0)
            filtered = [r for r in all_runs if str(r.get("session_id") or "") in owned]
            total = len(filtered)
            runs = filtered[offset: offset + limit]
        return {
            "runs": runs,
            "count": len(runs),
            "total": total,
            "session_id": session_id,
            "limit": limit,
            "offset": offset,
        }
    runs = store.list_runs(session_id=session_id, limit=limit, offset=offset)
    total = store.count_runs(session_id=session_id)
    return {
        "runs": runs,
        "count": len(runs),
        "total": total,
        "session_id": session_id,
        "limit": limit,
        "offset": offset,
    }


@router.get("/export", summary="导出 Run 汇总 JSON")
def export_runs(
    request: Request,
    session_id: str | None = Query(None),
    limit: int = Query(100, ge=1, le=MAX_RUN_LIMIT),
    store: RunStore = Depends(get_run_store),
) -> Response:
    user_id, role = identity(request)
    if role != "owner":
        if session_id and not can_access_session(read_session_meta(session_id), user_id, role):
            raise HTTPException(status_code=404, detail="Session not found")
        if not session_id:
            raise HTTPException(status_code=400, detail="member 导出需指定 session_id")
    runs = store.list_runs(session_id=session_id, limit=limit)
    payload = []
    for run in runs:
        data = store.get_run(run["id"])
        if data:
            payload.append(data)
    body = json.dumps({"runs": payload, "count": len(payload)}, ensure_ascii=False, indent=2)
    return Response(
        content=body,
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="runs-export.json"'},
    )


@router.get("/{run_id}/events", summary="Run 的审计事件（可增量）")
def list_run_events(
    run_id: str,
    request: Request,
    after_seq: int = Query(0, ge=0, description="只返回 seq 大于该值的事件"),
    store: RunStore = Depends(get_run_store),
) -> dict[str, Any]:
    data = store.get_run(run_id)
    if data is None or not _can_access_run(request, data.get("run") or data):
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")
    events = store.list_events(run_id, after_seq=after_seq)
    return {"run_id": run_id, "after_seq": after_seq, "events": events, "count": len(events)}


@router.get("/{run_id}/export", summary="导出单个 Run（markdown / json）")
def export_run(
    run_id: str,
    request: Request,
    format: str = Query("markdown", pattern="^(markdown|md|json)$"),
    store: RunStore = Depends(get_run_store),
) -> Response:
    data = store.get_run(run_id)
    if data is None or not _can_access_run(request, data.get("run") or data):
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")
    tool_calls = data.get("tool_calls") or []
    events = data.get("events") or []
    if format in ("json", "JSON"):
        body = json.dumps(data, ensure_ascii=False, indent=2)
        media, filename = "application/json", f"{run_id}.json"
    else:
        body = _run_markdown(data.get("run") or {}, tool_calls, events)
        media, filename = "text/markdown; charset=utf-8", f"{run_id}.md"
    return Response(
        content=body,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{run_id}", summary="单个 Run 的完整状态")
def get_run(run_id: str, request: Request, store: RunStore = Depends(get_run_store)) -> dict[str, Any]:
    data = store.get_run(run_id)
    if data is None or not _can_access_run(request, data.get("run") or data):
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")
    return data

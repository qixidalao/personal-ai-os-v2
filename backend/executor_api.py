"""Executor API: per-user SSH runner config / test / run (BYO compute)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from backend.executor import (
    MAX_TIMEOUT,
    ensure_keypair,
    load_config,
    run_remote,
    save_config,
    test_connection,
    validate_target,
)
from backend.ownership import identity, owner_user_id

router = APIRouter(prefix="/api/v1/executor", tags=["executor"])
DOC_PATH = Path(__file__).resolve().parents[1] / "docs" / "AIOS-执行器接入指南.md"


def _me(request: Request) -> tuple[str, str]:
    user_id, role = identity(request)
    if not user_id:
        user_id = owner_user_id()
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return user_id, role


def _sanitize(cfg: dict[str, Any]) -> dict[str, Any]:
    return {
        "mode": cfg.get("mode") or "disabled",
        "ssh": {
            "host": (cfg.get("ssh") or {}).get("host", ""),
            "port": (cfg.get("ssh") or {}).get("port", 22),
            "user": (cfg.get("ssh") or {}).get("user", "aios"),
            "image": (cfg.get("ssh") or {}).get("image", "aios-runner:latest"),
            "host_key_set": bool((cfg.get("ssh") or {}).get("host_key")),
        },
        "limits": cfg.get("limits") or {},
    }


@router.get("/docs")
async def executor_docs(request: Request):
    """用户版执行器接入指南（Markdown），供前端「部署文档」弹层展示。"""
    _me(request)
    if not DOC_PATH.exists():
        raise HTTPException(status_code=404, detail="文档不存在")
    return {"markdown": DOC_PATH.read_text(encoding="utf-8")}


@router.get("/config")
async def get_config(request: Request):
    user_id, role = _me(request)
    cfg = load_config(user_id, role)
    return {"config": _sanitize(cfg), "role": role}


@router.put("/config")
async def put_config(request: Request):
    user_id, role = _me(request)
    try:
        data = await request.json()
    except Exception:
        data = {}
    if not isinstance(data, dict):
        raise HTTPException(status_code=422, detail="配置格式不正确")
    cfg = load_config(user_id, role)
    mode = str(data.get("mode") or cfg.get("mode") or "disabled")
    if mode not in ("local", "ssh", "disabled"):
        raise HTTPException(status_code=422, detail="mode 只能是 local/ssh/disabled")
    if role != "owner" and mode == "local":
        raise HTTPException(status_code=403, detail="普通账号不允许本机执行")
    ssh_in = data.get("ssh") or {}
    if not isinstance(ssh_in, dict):
        raise HTTPException(status_code=422, detail="ssh 配置格式不正确")
    if mode == "ssh":
        host = str(ssh_in.get("host") or (cfg.get("ssh") or {}).get("host") or "").strip()
        port = int(ssh_in.get("port") or (cfg.get("ssh") or {}).get("port") or 22)
        if not (1 <= port <= 65535):
            raise HTTPException(status_code=422, detail="SSH 端口不正确")
        try:
            host = validate_target(host, role, port)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        ssh = {
            "host": host,
            "port": port,
            "user": str(ssh_in.get("user") or (cfg.get("ssh") or {}).get("user") or "aios").strip(),
            "image": str(ssh_in.get("image") or (cfg.get("ssh") or {}).get("image") or "aios-runner:latest").strip(),
            "host_key": str(ssh_in.get("host_key", (cfg.get("ssh") or {}).get("host_key", "")) or "").strip(),
        }
        if not ssh["user"]:
            raise HTTPException(status_code=422, detail="SSH 用户名不能为空")
        cfg["ssh"] = ssh
    cfg["mode"] = mode
    if isinstance(data.get("limits"), dict):
        cfg["limits"] = {
            "timeout": min(max(int(data["limits"].get("timeout") or 60), 1), MAX_TIMEOUT),
            "memory": str(data["limits"].get("memory") or "512m"),
            "cpus": str(data["limits"].get("cpus") or "1"),
        }
    save_config(user_id, cfg)
    if mode == "ssh":
        ensure_keypair(user_id)
    return {"config": _sanitize(cfg), "role": role}


@router.get("/ssh-key")
async def get_ssh_key(request: Request):
    user_id, _role = _me(request)
    ensure_keypair(user_id)
    path = _key_path_for(user_id)
    pub = path.with_suffix(".pub")
    return {"public_key": pub.read_text(encoding="utf-8").strip()}


def _key_path_for(user_id: str):
    from backend.executor import _key_path

    return _key_path(user_id)


@router.post("/test")
async def test(request: Request):
    user_id, role = _me(request)
    cfg = load_config(user_id, role)
    try:
        return await test_connection(user_id, role, cfg)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"连接失败: {exc}"}


@router.post("/run")
async def run(request: Request):
    user_id, role = _me(request)
    try:
        data = await request.json()
    except Exception:
        data = {}
    command = str(data.get("command") or "").strip()
    if not command:
        raise HTTPException(status_code=422, detail="command 不能为空")
    if len(command) > 20_000:
        raise HTTPException(status_code=422, detail="command 过长")
    try:
        timeout = int(data.get("timeout") or 60)
    except (TypeError, ValueError):
        timeout = 60
    try:
        return await run_remote(user_id, role, command, timeout=timeout)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"远程执行失败: {exc}", "mode": "ssh"}


@router.get("/status")
async def status(request: Request):
    user_id, role = _me(request)
    cfg = load_config(user_id, role)
    mode = cfg.get("mode") or "disabled"
    return {
        "role": role,
        "mode": mode,
        "configured": mode == "ssh",
        "local_allowed": role == "owner",
    }

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
        "device_id": cfg.get("device_id", ""),
        "ssh": {
            "host": (cfg.get("ssh") or {}).get("host", ""),
            "port": (cfg.get("ssh") or {}).get("port", 22),
            "user": (cfg.get("ssh") or {}).get("user", "aios"),
            "image": (cfg.get("ssh") or {}).get("image", "aios-runner:latest"),
            "host_key_set": bool((cfg.get("ssh") or {}).get("host_key")),
        },
        "limits": cfg.get("limits") or {},
        "storage": {"mode": (cfg.get("storage") or {}).get("mode", "local"), "path": (cfg.get("storage") or {}).get("path", "~/aios-data")},
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
    if mode not in ("local", "ssh", "device", "disabled"):
        raise HTTPException(status_code=422, detail="mode 只能是 local/ssh/device/disabled")
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
    if mode == "device":
        device_id = str(data.get("device_id") or cfg.get("device_id") or "").strip()
        if not device_id:
            raise HTTPException(status_code=422, detail="请先选择已配对的本机设备")
        from backend.device_api import _connect as _device_connect
        device_conn = _device_connect()
        try:
            device = device_conn.execute(
                "SELECT device_id FROM devices WHERE device_id=? AND user_id=? AND revoked=0",
                (device_id, user_id),
            ).fetchone()
        finally:
            device_conn.close()
        if not device:
            raise HTTPException(status_code=422, detail="本机设备不存在、已撤销或不属于当前账号")
        cfg["device_id"] = device_id
    cfg["mode"] = mode
    if isinstance(data.get("storage"), dict):
        storage_mode = str(data["storage"].get("mode") or "local")
        if storage_mode not in ("local", "remote"):
            raise HTTPException(status_code=422, detail="存储模式只能是 local 或 remote")
        if role != "owner" and storage_mode == "remote" and mode != "ssh":
            raise HTTPException(status_code=422, detail="远程存储需要先配置 SSH 执行服务器")
        cfg["storage"] = {"mode": storage_mode, "path": str(data["storage"].get("path") or "~/aios-data").strip()}
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


@router.get("/storage/status")
async def storage_status(request: Request):
    user_id, role = _me(request)
    cfg = load_config(user_id, role)
    storage = cfg.get("storage") or {}
    return {"mode": storage.get("mode", "local"), "path": storage.get("path", "~/aios-data"), "migration": storage.get("migration", "none")}


@router.post("/storage/migrate")
async def storage_migrate(request: Request):
    user_id, role = _me(request)
    if role == "owner":
        raise HTTPException(status_code=400, detail="管理员默认使用本机存储")
    cfg = load_config(user_id, role)
    if (cfg.get("mode") or "disabled") != "ssh":
        raise HTTPException(status_code=422, detail="请先配置并测试远程执行服务器")
    try:
        data = await request.json()
    except Exception:
        data = {}
    action = str(data.get("action") or "keep_local")
    if action not in ("keep_local", "migrate"):
        raise HTTPException(status_code=422, detail="action 只能是 keep_local 或 migrate")
    if action == "keep_local":
        cfg.setdefault("storage", {})["mode"] = "local"
        cfg["storage"]["migration"] = "keep_local"
        save_config(user_id, cfg)
        return {"ok": True, "mode": "local", "migration": "keep_local", "source_kept": True}

    # Copy, verify, then switch. Leave every local source file in place on success/failure.
    from backend.executor import remote_write_bytes
    from backend.ownership import owned_session_ids
    import json
    import mimetypes
    import hashlib
    from pathlib import Path

    files: list[tuple[str, bytes]] = []
    sessions_root = Path("storage/sessions")
    for sid in sorted(owned_session_ids(user_id)):
        sp = sessions_root / f"{sid}.json"
        if sp.is_file():
            raw = json.loads(sp.read_text(encoding="utf-8"))
            # Strip inline data URLs; media has its own migration path.
            for message in raw.get("messages", []):
                if isinstance(message, dict):
                    imgs = message.get("images")
                    if isinstance(imgs, list):
                        message["images"] = [x for x in imgs if not (isinstance(x, str) and x.startswith("data:"))]
            files.append((f"conversations/{sid}.json", json.dumps(raw, ensure_ascii=False, indent=2).encode()))

    media_root = Path("storage/users") / user_id / "media"
    index_path = media_root / "index.json"
    media_index = {}
    if index_path.exists():
        try: media_index = json.loads(index_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError): media_index = {}
    for media_id, record in media_index.items():
        if not isinstance(record, dict): continue
        local_path = Path(str(record.get("path") or ""))
        if not local_path.is_file(): continue
        suffix = local_path.suffix or mimetypes.guess_extension(record.get("mime") or "") or ".bin"
        files.append((f"media/{media_id}{suffix}", local_path.read_bytes()))
    files.append(("media/index.json", json.dumps(media_index, ensure_ascii=False, indent=2).encode()))

    copied = []
    try:
        for rel, content in files:
            result = await remote_write_bytes(user_id, role, rel, content, timeout=120)
            if not result.get("ok"):
                raise RuntimeError(result.get("stderr") or f"复制失败：{rel}")
            # Read back and compare exact bytes before declaring migration complete.
            from backend.executor import remote_read_bytes
            back = await remote_read_bytes(user_id, role, rel, timeout=120)
            if hashlib.sha256(back).digest() != hashlib.sha256(content).digest():
                raise RuntimeError(f"远程校验失败：{rel}")
            copied.append(rel)
    except Exception as exc:
        return JSONResponse({"detail": f"迁移中断；本地原数据保留，已复制 {len(copied)}/{len(files)} 项：{exc}",
                             "mode": "local", "source_kept": True}, status_code=502)

    cfg.setdefault("storage", {})["mode"] = "remote"
    cfg["storage"]["migration"] = "complete"
    cfg["storage"]["migrated_files"] = len(copied)
    save_config(user_id, cfg)
    return {"ok": True, "mode": "remote", "migration": "complete", "migrated_files": len(copied), "source_kept": True}


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

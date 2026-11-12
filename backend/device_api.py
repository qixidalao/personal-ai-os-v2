"""Outbound local-device executor API for AIOS.

Pairing is initiated from an authenticated user session. The paired agent then makes
outbound HTTPS long-poll requests; the AIOS server never connects to localhost on the
user's device. Device credentials are stored hashed and scoped to a single account.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import secrets
import sqlite3
import time
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from backend.ownership import identity

router = APIRouter(prefix="/api/v1/devices", tags=["devices"])
DB_PATH = Path("storage/devices.db")
PAIR_FAILURE_WINDOW = 300
PAIR_FAILURE_LIMIT = 10
_pair_failures: dict[str, deque[float]] = defaultdict(deque)
_pair_lock = asyncio.Lock()


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB_PATH, timeout=20)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.executescript("""
      CREATE TABLE IF NOT EXISTS pair_codes (
        code_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL, expires_at REAL NOT NULL, created_at REAL NOT NULL
      );
      CREATE TABLE IF NOT EXISTS devices (
        device_id TEXT PRIMARY KEY, user_id TEXT NOT NULL, name TEXT NOT NULL,
        token_hash TEXT NOT NULL, created_at REAL NOT NULL, last_seen REAL NOT NULL,
        revoked INTEGER NOT NULL DEFAULT 0, platform TEXT NOT NULL DEFAULT ''
      );
      CREATE INDEX IF NOT EXISTS idx_devices_user ON devices(user_id, revoked, last_seen DESC);
      CREATE TABLE IF NOT EXISTS device_jobs (
        job_id TEXT PRIMARY KEY, device_id TEXT NOT NULL, user_id TEXT NOT NULL,
        command TEXT NOT NULL, kind TEXT NOT NULL, timeout INTEGER NOT NULL,
        status TEXT NOT NULL, created_at REAL NOT NULL, claimed_at REAL,
        finished_at REAL, stdout TEXT NOT NULL DEFAULT '', stderr TEXT NOT NULL DEFAULT '',
        exit_code INTEGER, error TEXT
      );
      CREATE INDEX IF NOT EXISTS idx_device_jobs_queue ON device_jobs(device_id,status,created_at);
    """)
    return c


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _user(request: Request) -> tuple[str, str]:
    user_id, role = identity(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")
    return user_id, role


def _agent(request: Request) -> dict[str, Any]:
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="设备令牌缺失")
    token_hash = _hash(auth[7:].strip())
    c = _connect()
    try:
        row = c.execute("SELECT * FROM devices WHERE token_hash=? AND revoked=0", (token_hash,)).fetchone()
        if not row:
            raise HTTPException(status_code=401, detail="设备令牌无效或已撤销")
        c.execute("UPDATE devices SET last_seen=? WHERE device_id=?", (time.time(), row["device_id"]))
        c.commit()
        return dict(row)
    finally:
        c.close()


@router.post("/pairing-code")
async def create_pairing_code(request: Request):
    user_id, _ = _user(request)
    # 80-bit one-time secret; copied from the authenticated UI to the local agent.
    code = secrets.token_urlsafe(10)
    now = time.time()
    c = _connect()
    try:
        c.execute("DELETE FROM pair_codes WHERE expires_at<?", (now,))
        c.execute("INSERT INTO pair_codes(code_hash,user_id,expires_at,created_at) VALUES(?,?,?,?)",
                  (_hash(code), user_id, now + 300, now))
        c.commit()
    finally:
        c.close()
    return {"pairing_code": code, "expires_in": 300, "instructions": "在本机运行 AIOS Agent 并输入此码；此码仅可使用一次。"}


@router.post("/pair")
async def pair_device(request: Request):
    try:
        data = await request.json()
    except Exception:
        data = {}
    code = str(data.get("pairing_code") or "").strip()
    name = str(data.get("name") or "我的设备").strip()[:100]
    platform = str(data.get("platform") or "unknown").strip()[:100]
    if len(code) > 64 or not code:
        raise HTTPException(status_code=422, detail="配对码格式不正确")
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    async with _pair_lock:
        failures = _pair_failures[client_ip]
        while failures and now - failures[0] > PAIR_FAILURE_WINDOW:
            failures.popleft()
        if len(failures) >= PAIR_FAILURE_LIMIT:
            raise HTTPException(status_code=429, detail="配对尝试过多，请稍后再试")
    c = _connect()
    try:
        c.execute("BEGIN IMMEDIATE")
        row = c.execute("SELECT * FROM pair_codes WHERE code_hash=? AND expires_at>=?", (_hash(code), now)).fetchone()
        if not row:
            c.rollback()
            async with _pair_lock:
                failures = _pair_failures[client_ip]
                while failures and now - failures[0] > PAIR_FAILURE_WINDOW:
                    failures.popleft()
                failures.append(now)
            raise HTTPException(status_code=401, detail="配对码错误、过期或已使用")
        async with _pair_lock:
            _pair_failures[client_ip].clear()
        user_id = row["user_id"]
        c.execute("DELETE FROM pair_codes WHERE code_hash=?", (_hash(code),))
        device_id = f"dev_{secrets.token_hex(12)}"
        token = secrets.token_urlsafe(32)
        c.execute("INSERT INTO devices(device_id,user_id,name,token_hash,created_at,last_seen,platform) VALUES(?,?,?,?,?,?,?)",
                  (device_id,user_id,name,_hash(token),now,now,platform))
        c.commit()
        return {"device_id": device_id, "device_token": token, "name": name,
                "server": "Paired. Store this token securely; it is shown only once."}
    finally:
        c.close()


@router.get("")
async def list_devices(request: Request):
    user_id, _ = _user(request)
    c = _connect()
    try:
        rows = c.execute("SELECT device_id,name,platform,created_at,last_seen,revoked FROM devices WHERE user_id=? ORDER BY created_at DESC", (user_id,)).fetchall()
        now = time.time()
        return {"devices": [{**dict(r), "online": not r["revoked"] and now-r["last_seen"] < 45} for r in rows]}
    finally:
        c.close()


@router.delete("/{device_id}")
async def revoke_device(device_id: str, request: Request):
    user_id, _ = _user(request)
    c = _connect()
    try:
        cur = c.execute("UPDATE devices SET revoked=1 WHERE device_id=? AND user_id=?", (device_id,user_id))
        c.execute("UPDATE device_jobs SET status='cancelled',finished_at=?,error='device revoked' WHERE device_id=? AND user_id=? AND status IN ('queued','running')", (time.time(),device_id,user_id))
        c.commit()
        if not cur.rowcount:
            raise HTTPException(status_code=404, detail="设备不存在")
        return {"revoked": True, "device_id": device_id}
    finally:
        c.close()


@router.get("/agent/jobs/next")
async def agent_next_job(request: Request, wait: int = 20):
    device = _agent(request)
    deadline = time.monotonic() + min(max(int(wait),0),25)
    while True:
        c = _connect()
        try:
            c.execute("BEGIN IMMEDIATE")
            row = c.execute("SELECT * FROM device_jobs WHERE device_id=? AND user_id=? AND status='queued' ORDER BY created_at LIMIT 1",
                            (device["device_id"],device["user_id"])).fetchone()
            if row:
                c.execute("UPDATE device_jobs SET status='running',claimed_at=? WHERE job_id=? AND status='queued'",
                          (time.time(),row["job_id"]))
                c.commit()
                return {"job":{"job_id":row["job_id"],"kind":row["kind"],"command":row["command"],"timeout":row["timeout"],"expires_at":row["created_at"] + row["timeout"] + 5}}
            c.commit()
        finally:
            c.close()
        if time.monotonic() >= deadline:
            return {"job": None, "heartbeat": True}
        await asyncio.sleep(0.5)


@router.post("/agent/jobs/{job_id}/result")
async def agent_job_result(job_id: str, request: Request):
    device = _agent(request)
    try:
        length = int(request.headers.get("content-length") or "0")
    except ValueError:
        length = 0
    if length > 450_000:
        raise HTTPException(status_code=413, detail="设备任务结果超出大小上限")
    raw = await request.body()
    if len(raw) > 450_000:
        raise HTTPException(status_code=413, detail="设备任务结果超出大小上限")
    try:
        data = json.loads(raw or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(status_code=400, detail="设备任务结果不是有效 JSON")
    stdout = str(data.get("stdout") or "")[:200_000]
    stderr = str(data.get("stderr") or "")[:200_000]
    try:
        exit_code = int(data.get("exit_code", 1))
    except (TypeError,ValueError):
        exit_code = 1
    c = _connect()
    try:
        cur = c.execute("UPDATE device_jobs SET status=?,finished_at=?,stdout=?,stderr=?,exit_code=?,error=? WHERE job_id=? AND device_id=? AND user_id=? AND status='running'",
                        ("succeeded" if exit_code==0 else "failed",time.time(),stdout,stderr,exit_code,str(data.get("error") or "")[:2000],job_id,device["device_id"],device["user_id"]))
        c.commit()
        if not cur.rowcount:
            raise HTTPException(status_code=404, detail="任务不存在或已结束")
        return {"accepted": True}
    finally:
        c.close()


async def run_on_user_device(user_id: str, device_id: str, command: str, kind: str="shell", timeout: int=60) -> dict[str, Any]:
    if kind not in ("shell","python"):
        raise ValueError("unsupported device task kind")
    if not command or len(command)>20_000:
        raise ValueError("command empty or too long")
    now=time.time(); job_id=f"job_{secrets.token_hex(12)}"
    c=_connect()
    try:
        device=c.execute("SELECT * FROM devices WHERE device_id=? AND user_id=? AND revoked=0",(device_id,user_id)).fetchone()
        if not device: raise PermissionError("当前账号没有已配对的本机设备")
        if now-device["last_seen"]>45: raise ConnectionError("本机设备离线，请启动 AIOS Agent")
        c.execute("INSERT INTO device_jobs(job_id,device_id,user_id,command,kind,timeout,status,created_at) VALUES(?,?,?,?,?,?,?,?)",
                  (job_id,device_id,user_id,command,kind,min(max(int(timeout),1),300),"queued",now))
        c.commit()
    finally: c.close()
    deadline=time.monotonic()+min(max(int(timeout),1),300)+12
    while time.monotonic()<deadline:
        await asyncio.sleep(0.25)
        c=_connect()
        try:
            row=c.execute("SELECT * FROM device_jobs WHERE job_id=? AND user_id=? AND device_id=?",(job_id,user_id,device_id)).fetchone()
            if not row: raise RuntimeError("device job disappeared")
            if row["status"] in ("succeeded","failed","cancelled","expired"):
                return {"ok":row["status"]=="succeeded","exit_code":row["exit_code"],"stdout":row["stdout"],"stderr":row["stderr"],"mode":"device","device_id":device_id}
            if time.time()-row["created_at"]>min(max(int(timeout),1),300)+5:
                c.execute("UPDATE device_jobs SET status='expired',finished_at=?,error='job lease expired' WHERE job_id=? AND status IN ('queued','running')",(time.time(),job_id));c.commit()
                raise TimeoutError("本机执行超时或设备中断")
        finally: c.close()
    c=_connect()
    try:
        c.execute("UPDATE device_jobs SET status='expired',finished_at=?,error='job wait timeout' WHERE job_id=? AND status IN ('queued','running')",(time.time(),job_id));c.commit()
    finally: c.close()
    raise TimeoutError("等待本机设备执行超时")

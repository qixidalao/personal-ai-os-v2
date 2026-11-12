"""AIOS account auth: email registration/login + sliding sessions.

Design (single-owner now, multi-user later):
- First account must be created on the local machine (loopback bypass).
- Email + password, password hashed with scrypt; email verification code required
  for registration/password reset when SMTP is configured.
- Sessions: random token in HttpOnly cookie, SHA256 stored server-side,
  30-day sliding expiry, revocable; no IP binding (IP only audited).
- Local access (loopback without proxy headers) needs no login.
- Machine/API access: Authorization: Bearer <api_token>.
- SMTP config: storage/mail.json or AIOS_SMTP_* env; without SMTP, local
  registration uses a dev code shown on the local page and remote mail is disabled.
"""
from __future__ import annotations

import hashlib
import hmac
import html
import json
import os
import re
import secrets
import sqlite3
import threading
import time
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from pathlib import Path
from typing import Any

import httpx
try:
    from dotenv import load_dotenv
    load_dotenv(override=False)
except ImportError:
    pass
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

COOKIE_NAME = "aios_session"
SESSION_DAYS = 30
API_TOKEN_FILE = Path("storage/auth.json")
DB_FILE = Path("storage/auth.db")
MAIL_FILE = Path("storage/mail.json")
DEV_CODE_LOG = Path("storage/dev_codes.log")
CODE_TTL = 600
MAX_CODE_ATTEMPTS = 5
MAX_LOGIN_FAILS = 5
LOCK_SECONDS = 900
DISABLE_AUTH = os.environ.get("AIOS_DISABLE_AUTH") == "1"
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")


# ------------------------------------------------------------------ helpers
def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime | None = None) -> str:
    return (dt or _now()).isoformat(timespec="seconds").replace("+00:00", "Z")


# ------------------------------------------------------------------ credentials / api token
def _load_api_token() -> str:
    API_TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    data: dict[str, Any] = {}
    if API_TOKEN_FILE.exists():
        try:
            data = json.loads(API_TOKEN_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
    if not data.get("api_token"):
        data["api_token"] = secrets.token_urlsafe(32)
        data.pop("password", None)
        data.pop("admin_qq", None)
        API_TOKEN_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        try:
            os.chmod(API_TOKEN_FILE, 0o600)
        except OSError:
            pass
    return str(os.environ.get("AIOS_API_TOKEN") or data["api_token"])


API_TOKEN = _load_api_token()


def _token_ok(value: str) -> bool:
    return hmac.compare_digest(value.encode(), API_TOKEN.encode())


# ------------------------------------------------------------------ password hashing (scrypt)
def hash_password(password: str) -> str:
    salt = os.urandom(16)
    n, r, p = 2 ** 14, 8, 1
    digest = hashlib.scrypt(password.encode(), salt=salt, n=n, r=r, p=p, dklen=32)
    return f"scrypt${n}${r}${p}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, n, r, p, salt_hex, digest_hex = stored.split("$")
        if algo != "scrypt":
            return False
        digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt_hex),
                                n=int(n), r=int(r), p=int(p), dklen=32)
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


def valid_password(password: str) -> bool:
    if not isinstance(password, str) or not (8 <= len(password) <= 128):
        return False
    return bool(re.search(r"[A-Za-z]", password)) and bool(re.search(r"\d", password))


# ------------------------------------------------------------------ db
_db_lock = threading.RLock()
_db: sqlite3.Connection | None = None


def _db_conn() -> sqlite3.Connection:
    global _db
    if _db is None:
        DB_FILE.parent.mkdir(parents=True, exist_ok=True)
        _db = sqlite3.connect(str(DB_FILE), check_same_thread=False, timeout=30)
        _db.row_factory = sqlite3.Row
        with _db_lock:
            _db.execute("PRAGMA journal_mode=WAL")
            _db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id           TEXT PRIMARY KEY,
                    email        TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    role         TEXT NOT NULL DEFAULT 'owner',
                    status       TEXT NOT NULL DEFAULT 'active',
                    created_at   TEXT NOT NULL,
                    last_login_at TEXT,
                    failed_count INTEGER NOT NULL DEFAULT 0,
                    locked_until TEXT
                )
            """)
            _db.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id          TEXT PRIMARY KEY,
                    user_id     TEXT NOT NULL,
                    token_hash  TEXT NOT NULL,
                    created_at  TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    expires_at  TEXT NOT NULL,
                    user_agent  TEXT,
                    ip_created  TEXT,
                    revoked     INTEGER NOT NULL DEFAULT 0
                )
            """)
            _db.execute("CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(token_hash)")
            _db.execute("""
                CREATE TABLE IF NOT EXISTS email_codes (
                    id         TEXT PRIMARY KEY,
                    email      TEXT NOT NULL,
                    purpose    TEXT NOT NULL,
                    code_hash  TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    attempts   INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                )
            """)
            _db.execute("""
                CREATE TABLE IF NOT EXISTS auth_events (
                    id         TEXT PRIMARY KEY,
                    kind       TEXT NOT NULL,
                    email      TEXT,
                    ip         TEXT,
                    geo        TEXT,
                    status     TEXT,
                    detail     TEXT,
                    created_at TEXT NOT NULL
                )
            """)
            _db.commit()
    return _db


def _audit(kind: str, email: str = "", ip: str = "", geo: str = "", status: str = "", detail: str = "") -> None:
    try:
        with _db_lock:
            _db_conn().execute(
                "INSERT INTO auth_events (id, kind, email, ip, geo, status, detail, created_at) VALUES (?,?,?,?,?,?,?,?)",
                (f"ev_{secrets.token_hex(8)}", kind, email, ip, geo, status, detail, _iso()),
            )
            _db_conn().commit()
    except Exception:
        pass


# ------------------------------------------------------------------ mail
def mail_config() -> dict:
    cfg: dict[str, Any] = {}
    if MAIL_FILE.exists():
        try:
            cfg = json.loads(MAIL_FILE.read_text(encoding="utf-8")) or {}
        except (OSError, json.JSONDecodeError):
            cfg = {}
    host = os.environ.get("AIOS_SMTP_HOST") or cfg.get("host") or ""
    port = int(os.environ.get("AIOS_SMTP_PORT") or cfg.get("port") or 465)
    username = os.environ.get("AIOS_SMTP_USER") or cfg.get("username") or ""
    password = os.environ.get("AIOS_SMTP_PASSWORD") or cfg.get("password") or ""
    sender = os.environ.get("AIOS_SMTP_FROM") or cfg.get("from") or username
    ssl = cfg.get("ssl", port == 465)
    return {"host": host, "port": port, "username": username, "password": password,
            "from": sender, "ssl": bool(ssl)}


def mail_configured() -> bool:
    cfg = mail_config()
    return bool(cfg["host"] and cfg["username"] and cfg["password"] and cfg["from"])


SECURITY_FILE = Path("storage/security.json")


def security_config() -> dict:
    """临时安全开关（渗透测试用）：loginLockout / rateLimit，默认都开启。"""
    defaults = {"loginLockout": True, "rateLimit": True}
    if SECURITY_FILE.exists():
        try:
            data = json.loads(SECURITY_FILE.read_text(encoding="utf-8")) or {}
        except (OSError, json.JSONDecodeError):
            return defaults
        for key in defaults:
            if key in data:
                defaults[key] = bool(data[key])
    return defaults


def registration_config() -> dict:
    """注册策略：allow / 邀请邮箱白名单 / 调试验证码（仅本机请求返回）。"""
    raw: dict = {}
    if MAIL_FILE.exists():
        try:
            raw = json.loads(MAIL_FILE.read_text(encoding="utf-8")) or {}
        except (OSError, json.JSONDecodeError):
            raw = {}
    reg = raw.get("registration") if isinstance(raw.get("registration"), dict) else {}
    allowed = reg.get("allowedEmails")
    allowed_list = [str(x).strip().lower() for x in allowed if isinstance(x, str)] if isinstance(allowed, list) else []
    return {
        "allow": bool(reg.get("allow", False)),
        "allowedEmails": allowed_list,
        "debugCodes": bool(reg.get("debugCodes", False)),
    }


def _smtp_send(to: str, subject: str, body: str) -> None:
    cfg = mail_config()
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = cfg["from"]
    msg["To"] = to
    msg.set_content(body)
    if cfg["ssl"]:
        import smtplib
        with smtplib.SMTP_SSL(cfg["host"], cfg["port"], timeout=15) as smtp:
            smtp.login(cfg["username"], cfg["password"])
            smtp.send_message(msg)
    else:
        import smtplib
        with smtplib.SMTP(cfg["host"], cfg["port"], timeout=15) as smtp:
            smtp.starttls()
            smtp.login(cfg["username"], cfg["password"])
            smtp.send_message(msg)


async def send_mail(to: str, subject: str, body: str) -> tuple[bool, str]:
    if not mail_configured():
        return False, "SMTP 未配置"
    try:
        import asyncio
        await asyncio.to_thread(_smtp_send, to, subject, body)
        return True, ""
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)[:200]


def _new_code() -> str:
    return f"{secrets.randbelow(1000000):06d}"


def _store_code(email: str, purpose: str) -> str:
    code = _new_code()
    with _db_lock:
        _db_conn().execute(
            "INSERT INTO email_codes (id, email, purpose, code_hash, expires_at, attempts, created_at) VALUES (?,?,?,?,?,?,?)",
            (f"code_{secrets.token_hex(8)}", email.lower(), purpose,
             hashlib.sha256(code.encode()).hexdigest(), _iso(_now() + timedelta(seconds=CODE_TTL)), 0, _iso()),
        )
        _db_conn().commit()
    return code


def _check_code(email: str, purpose: str, code: str) -> bool:
    email = email.lower()
    with _db_lock:
        row = _db_conn().execute(
            "SELECT * FROM email_codes WHERE email=? AND purpose=? ORDER BY created_at DESC LIMIT 1",
            (email, purpose),
        ).fetchone()
        if not row:
            return False
        if row["attempts"] >= MAX_CODE_ATTEMPTS:
            return False
        try:
            expires = datetime.fromisoformat(row["expires_at"].replace("Z", "+00:00"))
        except ValueError:
            return False
        ok = _now() <= expires and hmac.compare_digest(
            hashlib.sha256(code.encode()).hexdigest(), row["code_hash"]
        )
        _db_conn().execute("UPDATE email_codes SET attempts=attempts+1 WHERE id=?", (row["id"],))
        if ok:
            _db_conn().execute("DELETE FROM email_codes WHERE email=? AND purpose=?", (email, purpose))
        _db_conn().commit()
    return ok


# ------------------------------------------------------------------ sessions
def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(user_id: str, user_agent: str, ip: str) -> str:
    token = secrets.token_urlsafe(32)
    now = _now()
    with _db_lock:
        _db_conn().execute(
            "INSERT INTO sessions (id, user_id, token_hash, created_at, last_seen_at, expires_at, user_agent, ip_created) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (f"sess_{secrets.token_hex(8)}", user_id, _token_hash(token), _iso(now), _iso(now),
             _iso(now + timedelta(days=SESSION_DAYS)), user_agent[:300], ip),
        )
        _db_conn().commit()
    return token


def find_session(token: str) -> dict | None:
    if not token:
        return None
    with _db_lock:
        row = _db_conn().execute(
            "SELECT s.*, u.email AS email, u.role AS role FROM sessions s JOIN users u ON u.id=s.user_id "
            "WHERE s.token_hash=? AND s.revoked=0 AND u.status='active'",
            (_token_hash(token),),
        ).fetchone()
        if not row:
            return None
        try:
            expires = datetime.fromisoformat(row["expires_at"].replace("Z", "+00:00"))
        except ValueError:
            return None
        if _now() > expires:
            return None
        # sliding renewal (at most once per hour)
        try:
            last = datetime.fromisoformat(row["last_seen_at"].replace("Z", "+00:00"))
        except ValueError:
            last = _now() - timedelta(hours=2)
        if _now() - last > timedelta(hours=1):
            new_exp = _iso(_now() + timedelta(days=SESSION_DAYS))
            _db_conn().execute(
                "UPDATE sessions SET last_seen_at=?, expires_at=? WHERE id=?",
                (_iso(), new_exp, row["id"]),
            )
            _db_conn().commit()
            refreshed = _db_conn().execute(
                "SELECT s.*, u.email AS email, u.role AS role FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.id=?",
                (row["id"],),
            ).fetchone()
            return dict(refreshed) if refreshed else None
    return dict(row)


def session_from_scope(scope) -> dict | None:
    headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers", [])}
    cookie_header = headers.get("cookie", "")
    for part in cookie_header.split(";"):
        name, _, value = part.strip().partition("=")
        if name == COOKIE_NAME and value:
            return find_session(value)
    return None


# ------------------------------------------------------------------ IP / geo
def _headers(scope) -> dict[str, str]:
    return {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers", [])}


def _forwarded_ip(headers: dict[str, str]) -> str:
    for key in ("cf-connecting-ip", "true-client-ip", "x-real-ip"):
        v = headers.get(key, "").strip()
        if v:
            return v
    xff = headers.get("x-forwarded-for", "")
    return xff.split(",")[0].strip() if xff else ""


def real_ip(scope) -> str:
    headers = _headers(scope)
    return _forwarded_ip(headers) or (scope.get("client") or ("", 0))[0]


def is_local_access(scope) -> bool:
    """True only for direct loopback access with a localhost Host header.

    经过隧道/代理（带 X-Forwarded-*/CF-Connecting-IP）或 Host 不是本机的一律不算本机，
    防止任何 forwarder 把外部流量转成 127.0.0.1 后绕过登录。
    """
    headers = _headers(scope)
    if _forwarded_ip(headers):
        return False
    host = headers.get("host", "").strip().lower()
    if host.startswith("["):
        hostname = host[1:host.find("]")] if "]" in host else host
    else:
        hostname = host.split(":")[0]
    if hostname not in ("localhost", "127.0.0.1", "::1"):
        return False
    return (scope.get("client") or ("", 0))[0] in ("127.0.0.1", "::1", "localhost")


def _is_private_ip(ip: str) -> bool:
    import ipaddress
    try:
        addr = ipaddress.ip_address(ip)
        return addr.is_private or addr.is_loopback or addr.is_link_local
    except ValueError:
        return True


async def geo_lookup(ip: str) -> str:
    if not ip:
        return "未知"
    if _is_private_ip(ip):
        return "本机 / 内网"
    try:
        async with httpx.AsyncClient(timeout=2.5, trust_env=True) as client:
            r = await client.get(f"http://ip-api.com/json/{ip}",
                                 params={"lang": "zh-CN", "fields": "status,country,regionName,city"})
            d = r.json()
        if d.get("status") == "success":
            return " · ".join(p for p in (d.get("country"), d.get("regionName"), d.get("city")) if p) or "未知"
    except Exception:
        pass
    return "未知"


# ------------------------------------------------------------------ rate limits
_rate: dict[str, list[float]] = {}
_register_passwords: dict[str, str] = {}
_rate_lock = threading.Lock()


def rate_ok(key: str, limit: int, window: int = 600) -> bool:
    now = time.time()
    with _rate_lock:
        items = [t for t in _rate.get(key, []) if now - t < window]
        if len(items) >= limit:
            _rate[key] = items
            return False
        items.append(now)
        _rate[key] = items
        return True


# ------------------------------------------------------------------ middleware
PUBLIC_PATHS = {"/login", "/api/v1/health", "/api/v1/auth/status"}
PUBLIC_PREFIXES = ("/assets/", "/api/v1/auth/")


class AuthMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if DISABLE_AUTH or scope["type"] not in ("http", "websocket"):
            return await self.app(scope, receive, send)

        path = scope.get("path", "/")
        if path in PUBLIC_PATHS or path.startswith(PUBLIC_PREFIXES):
            return await self.app(scope, receive, send)
        # The outbound local-device agent authenticates with its own device token.
        # The device route performs ownership/revocation validation.
        if path.startswith("/api/v1/devices/agent/"):
            return await self.app(scope, receive, send)
        if is_local_access(scope):
            return await self.app(scope, receive, send)

        session = session_from_scope(scope)
        token_ok = _bearer_ok(scope)
        if scope["type"] == "websocket":
            if not (session or token_ok):
                await send({"type": "websocket.close", "code": 4401})
                return
            return await self.app(scope, receive, send)

        # Instance administration API is unavailable to regular accounts.
        if path.startswith("/api/v1/admin") or path.startswith("/api/v1/auth/mail/") or path.startswith("/api/v1/auth/security"):
            if not (token_ok or (session and session.get("role") == "owner")):
                body = json.dumps({"detail": "Forbidden: 需要管理员权限"}, ensure_ascii=False).encode()
                await send({"type": "http.response.start", "status": 403,
                            "headers": [(b"content-type", b"application/json; charset=utf-8"),
                                        (b"content-length", str(len(body)).encode())]})
                await send({"type": "http.response.body", "body": body})
                return

        # 敏感操作：审批与手动工具执行仅 owner（或 Bearer）可操作；
        # settings PUT 由 handler 写入当前账号自己的隔离文件。
        method = (scope.get("method") or "GET").upper()
        # Tool execution stays admin-only; personal approval records are scoped in their API handlers.
        owner_only = path.startswith("/api/v1/tools/call")
        settings_instance_write = (
            path == "/api/v1/settings" and method not in ("GET", "HEAD")
            and session and session.get("role") == "owner"
        )
        if owner_only or settings_instance_write:
            if not (token_ok or (session and session.get("role") == "owner")):
                body = json.dumps({"detail": "Forbidden: 需要管理员权限"}, ensure_ascii=False).encode()
                await send({"type": "http.response.start", "status": 403,
                            "headers": [(b"content-type", b"application/json; charset=utf-8"),
                                        (b"content-length", str(len(body)).encode())]})
                await send({"type": "http.response.body", "body": body})
                return

        if session or token_ok:
            return await self.app(scope, receive, send)

        if path.startswith("/api/") or path.startswith("/ws/"):
            body = json.dumps({"detail": "Unauthorized: 请先登录"}, ensure_ascii=False).encode()
            await send({"type": "http.response.start", "status": 401,
                        "headers": [(b"content-type", b"application/json; charset=utf-8"),
                                    (b"content-length", str(len(body)).encode())]})
            await send({"type": "http.response.body", "body": body})
            return

        page = LOGIN_HTML.encode("utf-8")
        await send({"type": "http.response.start", "status": 200,
                    "headers": [(b"content-type", b"text/html; charset=utf-8"),
                                (b"content-length", str(len(page)).encode()),
                                (b"cache-control", b"no-store")]})
        await send({"type": "http.response.body", "body": page})


def _bearer_ok(scope) -> bool:
    headers = _headers(scope)
    auth = headers.get("authorization", "")
    return auth.lower().startswith("bearer ") and _token_ok(auth[7:].strip())


# ------------------------------------------------------------------ login page
LOGIN_HTML = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>AIOS · 登录</title>
<style>
:root{color-scheme:dark}
*{box-sizing:border-box}
body{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;
background:radial-gradient(1200px 600px at 50% -10%,#16213d 0%,#080b14 55%);color:#e8ebf4;
font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans SC",sans-serif}
.card{width:min(420px,92vw);padding:30px 28px;border:1px solid #232b3d;border-radius:20px;
background:linear-gradient(165deg,#121828,#0b0f1a);box-shadow:0 28px 90px rgba(0,0,0,.55)}
.brand{display:flex;align-items:center;gap:10px;margin-bottom:22px}
.mark{width:34px;height:34px;border-radius:11px;display:grid;place-items:center;
background:linear-gradient(135deg,#5b7cfa,#7c5bfa);color:#fff;font-size:11px;font-weight:800;letter-spacing:.04em;
box-shadow:0 6px 20px rgba(91,124,250,.4)}
.brand-name{font-size:14px;font-weight:700;letter-spacing:.01em}
.brand-sub{font-size:10px;color:#6b7488;letter-spacing:.18em;text-transform:uppercase;margin-top:2px}
h1{margin:0 0 6px;font-size:23px;letter-spacing:-.02em}
.sub{margin:0 0 20px;color:#8b93a7;font-size:13px;line-height:1.6}
.tabs{display:flex;gap:4px;padding:4px;border-radius:12px;background:#0b1020;border:1px solid #232b3d;margin-bottom:18px}
.tab{flex:1;height:34px;border-radius:9px;border:none;background:transparent;color:#8b93a7;font-size:12.5px;cursor:pointer;font-weight:600}
.tab.active{color:#fff;background:rgba(91,124,250,.22);box-shadow:inset 0 0 0 1px rgba(91,124,250,.4)}
.field{margin-bottom:14px}
label{display:block;font-size:12px;color:#9aa3b8;margin:0 0 7px}
.input-wrap{position:relative}
input{width:100%;height:44px;border-radius:11px;border:1px solid #2a3247;background:#0b1020 !important;color:#e8ebf4 !important;
padding:0 13px;font-size:14px;outline:none;transition:border-color .15s,box-shadow .15s;
color-scheme:dark;-webkit-appearance:none;appearance:none;-webkit-text-fill-color:#e8ebf4;caret-color:#e8ebf4}
input::placeholder{color:#5d667c !important;-webkit-text-fill-color:#5d667c !important;opacity:1}
input:focus{border-color:#5b7cfa;box-shadow:0 0 0 3px rgba(91,124,250,.16)}
/* 移动端浏览器自动填充会强制白底白字，覆盖掉 */
input:-webkit-autofill,input:-webkit-autofill:hover,input:-webkit-autofill:focus,input:-webkit-autofill:active{
  -webkit-box-shadow:0 0 0 1000px #0b1020 inset !important;
  box-shadow:0 0 0 1000px #0b1020 inset !important;
  -webkit-text-fill-color:#e8ebf4 !important;
  caret-color:#e8ebf4 !important;
  transition:background-color 99999s ease-in-out 0s;
}
.eye{position:absolute;right:10px;top:50%;transform:translateY(-50%);border:none;background:transparent;
color:#6b7488;font-size:12px;cursor:pointer;padding:4px}
.row{display:flex;gap:8px}
.row input{flex:1}
.code-btn{height:44px;padding:0 14px;border-radius:11px;border:1px solid #2a3247;background:#111a2c;color:#c7d2fe;
font-size:12px;white-space:nowrap;cursor:pointer;font-weight:600}
.code-btn:disabled{opacity:.5;cursor:default}
button.primary{margin-top:6px;width:100%;height:46px;border-radius:12px;border:none;cursor:pointer;
background:linear-gradient(135deg,#5b7cfa,#7c5bfa);color:#fff;font-size:14.5px;font-weight:700;letter-spacing:.01em;
box-shadow:0 8px 24px rgba(91,124,250,.28)}
button.primary:disabled{opacity:.6;cursor:default;box-shadow:none}
.err{min-height:18px;margin-top:10px;color:#f87171;font-size:12px;line-height:1.5}
.hint{margin-top:16px;font-size:11.5px;color:#6b7488;line-height:1.7}
.hint b{color:#9aa3b8;font-weight:600}
.link{color:#8ea2ff;cursor:pointer;text-decoration:none}
.link:hover{text-decoration:underline}
.providers{margin-top:10px;font-size:11px;color:#5d667c;line-height:1.7}
.providers span{display:inline-block;padding:1px 7px;margin-right:5px;border:1px solid #232b3d;border-radius:999px;color:#8b93a7}
.hidden{display:none}
</style></head>
<body>
<div class="card">
  <div class="brand">
    <div class="mark">AI</div>
    <div><div class="brand-name">Personal AI OS</div><div class="brand-sub">Console</div></div>
  </div>
  <h1 id="title">欢迎回来</h1>
  <p class="sub" id="sub">登录后继续使用你的 AI 工作台。</p>

  <div class="tabs">
    <button class="tab active" data-mode="login">登录</button>
    <button class="tab" data-mode="register">注册账号</button>
  </div>

  <form id="form">
    <div class="field">
      <label for="email">邮箱</label>
      <input id="email" type="email" autocomplete="username" placeholder="name@gmail.com" />
    </div>
    <div class="field">
      <label for="password">密码</label>
      <div class="input-wrap">
        <input id="password" type="password" autocomplete="current-password" placeholder="输入密码" />
        <button class="eye" type="button" id="eye">显示</button>
      </div>
    </div>
    <div class="field hidden" id="confirmRow">
      <label for="confirm">确认密码</label>
      <input id="confirm" type="password" autocomplete="new-password" placeholder="再次输入密码" />
    </div>
    <div class="field hidden" id="codeRow">
      <label for="code">邮箱验证码</label>
      <div class="row">
        <input id="code" inputmode="numeric" maxlength="6" placeholder="6 位验证码" />
        <button class="code-btn" type="button" id="sendCode">发送验证码</button>
      </div>
    </div>
    <div class="field hidden" id="forgotRow">
      <label for="newPassword">新密码</label>
      <input id="newPassword" type="password" autocomplete="new-password" placeholder="至少 8 位，含字母和数字" />
    </div>
    <button class="primary" id="submit" type="submit">登录</button>
  </form>
  <div class="err" id="err"></div>

  <div class="hint" id="hint">
    <span class="link" id="forgot">忘记密码？</span>
  </div>
  <div class="providers hidden" id="providers">
    支持 Gmail、Outlook、网易、QQ 等常见邮箱注册：<br/>
    <span>Gmail</span><span>Outlook</span><span>网易 163</span><span>126</span><span>QQ 邮箱</span><span>企业邮箱</span>
  </div>
</div>
<script>
const $=id=>document.getElementById(id);
let mode='login';
async function checkBootstrap(){
  try{
    const r=await fetch('/api/v1/auth/bootstrap/status');
    const d=await r.json();
    if(d.available && d.local){
      bootstrapMode=true;
      const tab=document.querySelector('[data-mode=\"register\"]');
      if(tab) tab.textContent='创建管理员';
      $('sub').textContent='首次使用：创建本机管理员账号。此入口仅在本机且尚无账号时开放。';
      setMode('bootstrap');
      $('password').autocomplete='new-password';
    }
  }catch(e){}
}

let bootstrapMode = false;
function setMode(next){
  if(next==='register' && bootstrapMode) next='bootstrap';
  mode=next; $('err').textContent='';
  const tabMode = next==='bootstrap' ? 'register' : next;
  document.querySelectorAll('.tab').forEach(t=>t.classList.toggle('active', t.dataset.mode===tabMode));
  $('confirmRow').classList.toggle('hidden', next!=='register' && next!=='bootstrap');
  $('codeRow').classList.toggle('hidden', next!=='register' && next!=='reset');
  $('forgotRow').classList.toggle('hidden', next!=='reset');
  $('providers').classList.toggle('hidden', next!=='register');
  $('password').parentElement.parentElement.classList.toggle('hidden', next==='reset');
  $('hint').classList.toggle('hidden', next==='reset' || next==='bootstrap');
  if(next==='login'){ $('title').textContent='欢迎回来'; $('sub').textContent='登录后继续使用你的 AI 工作台。'; $('submit').textContent='登录'; $('password').autocomplete='current-password'; }
  if(next==='register'){ $('title').textContent='创建账号'; $('sub').textContent='使用邮箱注册，收一封验证码即可开始。'; $('submit').textContent='注册'; $('password').autocomplete='new-password'; }
  if(next==='bootstrap'){ $('title').textContent='创建管理员账号'; $('sub').textContent='首次使用：在本机创建管理员账号。此入口只在尚无账号时开放。'; $('submit').textContent='创建管理员账号'; $('password').autocomplete='new-password'; }
  if(next==='reset'){ $('title').textContent='重置密码'; $('sub').textContent='验证邮箱后设置新密码。'; $('submit').textContent='重置密码'; }
}
document.querySelectorAll('.tab').forEach(t=>t.addEventListener('click',()=>setMode(t.dataset.mode)));
$('forgot').addEventListener('click',()=>setMode('reset'));
checkBootstrap();
$('eye').addEventListener('click',()=>{ const p=$('password'); p.type=p.type==='password'?'text':'password'; $('eye').textContent=p.type==='password'?'显示':'隐藏'; });

async function api(path, body){
  const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  const d=await r.json().catch(()=>({}));
  if(!r.ok) throw new Error(d.detail || ('请求失败 HTTP '+r.status));
  return d;
}
$('sendCode').addEventListener('click',async()=>{
  const email=$('email').value.trim();
  if(!email){ $('err').textContent='请先填写邮箱'; return; }
  $('sendCode').disabled=true; $('err').textContent='';
  try{
    const path = mode==='reset' ? '/api/v1/auth/reset/request' : '/api/v1/auth/register/request';
    await api(path,{email});
    $('err').textContent='验证码已发送，请检查收件箱（含垃圾邮件）';
    let left=60; const t=setInterval(()=>{ left--; $('sendCode').textContent=left>0?left+' 秒后重发':'发送验证码'; if(left<=0){ clearInterval(t); $('sendCode').disabled=false; } },1000);
  }catch(e){ $('err').textContent=e.message; $('sendCode').disabled=false; }
});
$('form').addEventListener('submit',async e=>{
  e.preventDefault();
  const email=$('email').value.trim().toLowerCase();
  const password=$('password').value, confirm=$('confirm').value, code=$('code').value.trim(), newPassword=$('newPassword').value;
  $('err').textContent=''; $('submit').disabled=true;
  try{
    if(mode==='login'){
      await api('/api/v1/auth/login',{email,password});
      location.replace('/');
    } else if(mode==='bootstrap'){
      if(!password || password!==confirm) throw new Error('两次输入的密码不一致');
      await api('/api/v1/auth/bootstrap',{email,password});
      location.replace('/');
    } else if(mode==='register'){
      if(!password || password!==confirm) throw new Error('两次输入的密码不一致');
      const d=await api('/api/v1/auth/register/verify',{email,code,password});
      location.replace('/');
    } else {
      await api('/api/v1/auth/reset/verify',{email,code,password:newPassword});
      $('err').textContent='密码已重置，请用新密码登录';
      setMode('login');
    }
  }catch(x){ $('err').textContent=x.message; }
  finally{ $('submit').disabled=false; }
});
</script>
</body></html>"""


# ------------------------------------------------------------------ routes
router = APIRouter(tags=["auth"])


@router.get("/login", response_class=HTMLResponse)
async def login_page():
    return HTMLResponse(LOGIN_HTML, headers={"Cache-Control": "no-store"})


@router.get("/api/v1/auth/bootstrap/status")
async def bootstrap_status(request: Request):
    local = is_local_access(request.scope)
    with _db_lock:
        count = _db_conn().execute("SELECT COUNT(*) FROM users").fetchone()[0]
    return {"available": bool(local and count == 0), "local": local}


@router.post("/api/v1/auth/bootstrap")
async def bootstrap_first_owner(request: Request):
    if not is_local_access(request.scope):
        return JSONResponse({"detail": "首次创建管理员账号只能在本机完成"}, status_code=403)
    try:
        data = await request.json()
    except Exception:
        data = {}
    email = str(data.get("email") or "").strip().lower()
    password = str(data.get("password") or "")
    if not EMAIL_RE.match(email):
        return JSONResponse({"detail": "邮箱格式不正确"}, status_code=422)
    if not valid_password(password):
        return JSONResponse({"detail": "密码至少 8 位，且需同时包含字母和数字"}, status_code=422)
    ip = real_ip(request.scope)
    with _db_lock:
        count = _db_conn().execute("SELECT COUNT(*) FROM users").fetchone()[0]
        if count != 0:
            return JSONResponse({"detail": "管理员账号已初始化"}, status_code=409)
        user_id = f"user_{secrets.token_hex(8)}"
        _db_conn().execute(
            "INSERT INTO users (id,email,password_hash,role,status,created_at,last_login_at) VALUES (?,?,?,?,?,?,?)",
            (user_id, email, hash_password(password), "owner", "active", _iso(), _iso()),
        )
        _db_conn().commit()
    _audit("bootstrap_owner", email, ip, "", "ok")
    token = create_session(user_id, request.headers.get("user-agent", ""), ip)
    response = JSONResponse({"ok": True, "role": "owner"})
    response.set_cookie(COOKIE_NAME, token, max_age=SESSION_DAYS * 86400,
                        httponly=True, samesite="lax", path="/")
    return response


@router.get("/api/v1/auth/status")
async def status(request: Request):
    local = is_local_access(request.scope)
    session = session_from_scope(request.scope)
    return {"authenticated": bool(local or session or _bearer_ok(request.scope)),
            "local": local, "email": (session or {}).get("email")}


@router.post("/api/v1/auth/register/request")
async def register_request(request: Request):
    try:
        data = await request.json()
    except Exception:
        data = {}
    email = str(data.get("email") or "").strip().lower()
    password = str(data.get("password") or "")
    ip = real_ip(request.scope)
    if not EMAIL_RE.match(email):
        return JSONResponse({"detail": "邮箱格式不正确"}, status_code=422)
    # 密码可以在注册请求或验证阶段提交；此处可选校验
    if password and not valid_password(password):
        return JSONResponse({"detail": "密码至少 8 位，且需同时包含字母和数字"}, status_code=422)
    with _db_lock:
        count = _db_conn().execute("SELECT COUNT(*) FROM users").fetchone()[0]
        exists = _db_conn().execute("SELECT 1 FROM users WHERE email=?", (email,)).fetchone()
    if exists:
        return JSONResponse({"detail": "该邮箱已注册"}, status_code=409)
    reg = registration_config()
    if reg["allowedEmails"] and email not in reg["allowedEmails"]:
        return JSONResponse({"detail": "该邮箱暂未获得注册邀请"}, status_code=403)
    if count == 0:
        if not is_local_access(request.scope):
            return JSONResponse({"detail": "注册暂未开放，请稍后再试"}, status_code=403)
    elif not reg["allow"]:
        return JSONResponse({"detail": "注册暂未开放，请稍后再试"}, status_code=403)
    if not rate_ok(f"reg:{ip}", 5):
        return JSONResponse({"detail": "请求过于频繁，请稍后再试"}, status_code=429)

    _register_passwords[email] = password
    code = _store_code(email, "register")
    _audit("register_request", email, ip, await geo_lookup(ip), "pending")
    if not mail_configured():
        return JSONResponse({"detail": "邮件服务暂不可用，请稍后再试"}, status_code=503)
    ok, err = await send_mail(email, "AIOS 注册验证码",
                              f"你的 AIOS 注册验证码是：{code}\n10 分钟内有效。若不是你操作请忽略。")
    if not ok:
        return JSONResponse({"detail": "验证码邮件发送失败，请稍后再试"}, status_code=503)
    result = {"ok": True, "message": "验证码已发送到邮箱"}
    if reg["debugCodes"] and is_local_access(request.scope):
        result["dev_code"] = code
    return result


@router.post("/api/v1/auth/register/verify")
async def register_verify(request: Request):
    try:
        data = await request.json()
    except Exception:
        data = {}
    email = str(data.get("email") or "").strip().lower()
    code = str(data.get("code") or "").strip()
    ip = real_ip(request.scope)
    password = str(data.get("password") or _register_passwords.pop(email, ""))
    if not valid_password(password):
        return JSONResponse({"detail": "密码至少 8 位，且需同时包含字母和数字"}, status_code=422)
    if not _check_code(email, "register", code):
        return JSONResponse({"detail": "验证码错误或已过期"}, status_code=401)
    with _db_lock:
        exists = _db_conn().execute("SELECT 1 FROM users WHERE email=?", (email,)).fetchone()
        if exists:
            return JSONResponse({"detail": "该邮箱已注册"}, status_code=409)
        reg = registration_config()
        if reg["allowedEmails"] and email not in reg["allowedEmails"]:
            return JSONResponse({"detail": "该邮箱暂未获得注册邀请"}, status_code=403)
        count = _db_conn().execute("SELECT COUNT(*) FROM users").fetchone()[0]
        if count > 0 and not reg["allow"]:
            return JSONResponse({"detail": "注册暂未开放，请稍后再试"}, status_code=403)
        role = "owner" if count == 0 else "member"
        user_id = f"user_{secrets.token_hex(8)}"
        _db_conn().execute(
            "INSERT INTO users (id, email, password_hash, role, status, created_at) VALUES (?,?,?,?,?,?)",
            (user_id, email, hash_password(password), role, "active", _iso()),
        )
        _db_conn().commit()
    _audit("register_success", email, ip, await geo_lookup(ip), "ok")
    token = create_session(user_id, request.headers.get("user-agent", ""), ip)
    response = JSONResponse({"ok": True})
    response.set_cookie(COOKIE_NAME, token, max_age=SESSION_DAYS * 86400,
                        httponly=True, samesite="lax", path="/")
    return response


@router.post("/api/v1/auth/login")
async def login(request: Request):
    try:
        data = await request.json()
    except Exception:
        data = {}
    email = str(data.get("email") or "").strip().lower()
    password = str(data.get("password") or "")
    ip = real_ip(request.scope)
    sec = security_config()
    if sec.get("rateLimit", True) and not rate_ok(f"login:{ip}", 10, 600):
        return JSONResponse({"detail": "尝试过于频繁，请 10 分钟后再试"}, status_code=429)
    with _db_lock:
        row = _db_conn().execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if row:
            if str(row["status"] or "") != "active":
                return JSONResponse({"detail": "账号已禁用"}, status_code=403)
            try:
                locked = row["locked_until"] and datetime.fromisoformat(row["locked_until"].replace("Z", "+00:00")) > _now()
            except (ValueError, TypeError):
                locked = False
            if locked and sec.get("loginLockout", True):
                return JSONResponse({"detail": "账号暂时锁定，请稍后再试"}, status_code=403)
            if verify_password(password, row["password_hash"]):
                _db_conn().execute(
                    "UPDATE users SET last_login_at=?, failed_count=0, locked_until=NULL WHERE id=?",
                    (_iso(), row["id"]),
                )
                _db_conn().commit()
            else:
                fails = int(row["failed_count"] or 0) + 1
                lock = _iso(_now() + timedelta(seconds=LOCK_SECONDS)) if (
                    sec.get("loginLockout", True) and fails >= MAX_LOGIN_FAILS
                ) else None
                _db_conn().execute(
                    "UPDATE users SET failed_count=?, locked_until=? WHERE id=?",
                    (fails, lock, row["id"]),
                )
                _db_conn().commit()
                _audit("login_failed", email, ip, await geo_lookup(ip), "bad_password")
                return JSONResponse({"detail": "邮箱或密码错误"}, status_code=401)
        else:
            _audit("login_failed", email, ip, await geo_lookup(ip), "unknown_user")
            return JSONResponse({"detail": "邮箱或密码错误"}, status_code=401)

    _audit("login_success", email, ip, await geo_lookup(ip), "ok")
    token = create_session(row["id"], request.headers.get("user-agent", ""), ip)
    response = JSONResponse({"ok": True})
    response.set_cookie(COOKIE_NAME, token, max_age=SESSION_DAYS * 86400,
                        httponly=True, samesite="lax", path="/")
    return response


@router.post("/api/v1/auth/logout")
async def logout(request: Request):
    session = session_from_scope(request.scope)
    if session:
        with _db_lock:
            _db_conn().execute("UPDATE sessions SET revoked=1 WHERE id=?", (session["id"],))
            _db_conn().commit()
    response = JSONResponse({"ok": True})
    response.delete_cookie(COOKIE_NAME, path="/")
    return response


@router.get("/api/v1/auth/me")
async def me(request: Request):
    session = session_from_scope(request.scope)
    if session:
        return {"authenticated": True, "email": session["email"], "role": session["role"],
                "session_id": session["id"], "expires_at": session["expires_at"]}
    if is_local_access(request.scope):
        return {"authenticated": True, "local": True}
    return JSONResponse({"detail": "Unauthorized"}, status_code=401)


@router.get("/api/v1/auth/sessions")
async def sessions(request: Request):
    session = session_from_scope(request.scope)
    if not session:
        return JSONResponse({"detail": "Unauthorized"}, status_code=401)
    with _db_lock:
        rows = _db_conn().execute(
            "SELECT id, created_at, last_seen_at, expires_at, user_agent, ip_created, revoked "
            "FROM sessions WHERE user_id=? ORDER BY created_at DESC LIMIT 50",
            (session["user_id"],),
        ).fetchall()
    return {"sessions": [dict(r) for r in rows], "current": session["id"]}


@router.post("/api/v1/auth/sessions/revoke")
async def revoke_session(request: Request):
    try:
        data = await request.json()
    except Exception:
        data = {}
    target = str(data.get("session_id") or "")
    session = session_from_scope(request.scope)
    if not session:
        return JSONResponse({"detail": "Unauthorized"}, status_code=401)
    with _db_lock:
        _db_conn().execute("UPDATE sessions SET revoked=1 WHERE id=? AND user_id=?", (target, session["user_id"]))
        _db_conn().commit()
    return {"ok": True}




@router.post("/api/v1/auth/reset/request")
async def reset_request(request: Request):
    try:
        data = await request.json()
    except Exception:
        data = {}
    email = str(data.get("email") or "").strip().lower()
    ip = real_ip(request.scope)
    if not EMAIL_RE.match(email):
        return JSONResponse({"detail": "邮箱格式不正确"}, status_code=422)
    if not rate_ok(f"reset:{ip}", 5):
        return JSONResponse({"detail": "请求过于频繁，请稍后再试"}, status_code=429)
    with _db_lock:
        exists = _db_conn().execute("SELECT 1 FROM users WHERE email=?", (email,)).fetchone()
    # 不泄露邮箱是否存在
    if exists and mail_configured():
        code = _store_code(email, "reset")
        ok, _err = await send_mail(email, "AIOS 重置密码验证码",
                                   f"你的 AIOS 重置密码验证码是：{code}\n10 分钟内有效。若不是你操作请忽略。")
        if ok:
            _audit("reset_request", email, ip, await geo_lookup(ip), "ok")
    return {"ok": True, "message": "如果该邮箱已注册，验证码已发送"}


@router.post("/api/v1/auth/reset/verify")
async def reset_verify(request: Request):
    try:
        data = await request.json()
    except Exception:
        data = {}
    email = str(data.get("email") or "").strip().lower()
    code = str(data.get("code") or "").strip()
    password = str(data.get("password") or "")
    ip = real_ip(request.scope)
    if not valid_password(password):
        return JSONResponse({"detail": "新密码至少 8 位，且需同时包含字母和数字"}, status_code=422)
    if not _check_code(email, "reset", code):
        return JSONResponse({"detail": "验证码错误或已过期"}, status_code=401)
    with _db_lock:
        row = _db_conn().execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
        if not row:
            return JSONResponse({"detail": "验证码错误或已过期"}, status_code=401)
        _db_conn().execute("UPDATE users SET password_hash=?, failed_count=0, locked_until=NULL WHERE id=?",
                           (hash_password(password), row["id"]))
        _db_conn().execute("UPDATE sessions SET revoked=1 WHERE user_id=?", (row["id"],))
        _db_conn().commit()
    _audit("reset_success", email, ip, await geo_lookup(ip), "ok")
    return {"ok": True}


@router.post("/api/v1/auth/change-password")
async def change_password(request: Request):
    try:
        data = await request.json()
    except Exception:
        data = {}
    old = str(data.get("old_password") or "")
    new = str(data.get("new_password") or "")
    session = session_from_scope(request.scope)
    local = is_local_access(request.scope)
    if not (session or local):
        return JSONResponse({"detail": "Unauthorized"}, status_code=401)
    if not valid_password(new):
        return JSONResponse({"detail": "新密码至少 8 位，且需同时包含字母和数字"}, status_code=422)
    if session:
        with _db_lock:
            row = _db_conn().execute("SELECT * FROM users WHERE id=?", (session["user_id"],)).fetchone()
    else:
        with _db_lock:
            row = _db_conn().execute("SELECT * FROM users ORDER BY created_at LIMIT 1").fetchone()
    if not row:
        return JSONResponse({"detail": "账号不存在"}, status_code=404)
    if not verify_password(old, row["password_hash"]):
        return JSONResponse({"detail": "原密码错误"}, status_code=401)
    with _db_lock:
        _db_conn().execute("UPDATE users SET password_hash=? WHERE id=?", (hash_password(new), row["id"]))
        _db_conn().commit()
    return {"ok": True}


@router.post("/api/v1/auth/change-email")
async def change_email(request: Request):
    try:
        data = await request.json()
    except Exception:
        data = {}
    password = str(data.get("password") or "")
    new_email = str(data.get("new_email") or "").strip().lower()
    session = session_from_scope(request.scope)
    local = is_local_access(request.scope)
    if not (session or local):
        return JSONResponse({"detail": "Unauthorized"}, status_code=401)
    if not EMAIL_RE.match(new_email):
        return JSONResponse({"detail": "邮箱格式不正确"}, status_code=422)
    if session:
        with _db_lock:
            row = _db_conn().execute("SELECT * FROM users WHERE id=?", (session["user_id"],)).fetchone()
    else:
        with _db_lock:
            row = _db_conn().execute("SELECT * FROM users ORDER BY created_at LIMIT 1").fetchone()
    if not row or not verify_password(password, row["password_hash"]):
        return JSONResponse({"detail": "密码错误"}, status_code=401)
    with _db_lock:
        dup = _db_conn().execute("SELECT 1 FROM users WHERE email=? AND id<>?", (new_email, row["id"])).fetchone()
        if dup:
            return JSONResponse({"detail": "该邮箱已被使用"}, status_code=409)
        _db_conn().execute("UPDATE users SET email=? WHERE id=?", (new_email, row["id"]))
        _db_conn().commit()
    return {"ok": True}


@router.get("/api/v1/auth/security")
async def get_security(request: Request):
    if not _owner_request(request):
        return JSONResponse({"detail": "Forbidden"}, status_code=403)
    return security_config()


@router.post("/api/v1/auth/security")
async def set_security(request: Request):
    if not _owner_request(request):
        return JSONResponse({"detail": "Forbidden"}, status_code=403)
    try:
        data = await request.json()
    except Exception:
        data = {}
    cfg = security_config()
    for key in ("loginLockout", "rateLimit"):
        if key in data:
            cfg[key] = bool(data[key])
    SECURITY_FILE.parent.mkdir(parents=True, exist_ok=True)
    SECURITY_FILE.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        os.chmod(SECURITY_FILE, 0o600)
    except OSError:
        pass
    return cfg


def _owner_request(request: Request) -> bool:
    try:
        if is_local_access(request.scope) or _bearer_ok(request.scope):
            return True
        session = session_from_scope(request.scope)
        return bool(session and session.get("role") == "owner")
    except Exception:
        return False


@router.get("/api/v1/auth/mail/config")
async def get_mail_config(request: Request):
    if not _owner_request(request):
        return JSONResponse({"detail": "Forbidden"}, status_code=403)
    cfg = mail_config()
    reg = registration_config()
    return {
        "configured": mail_configured(),
        "host": cfg["host"],
        "port": cfg["port"],
        "username": cfg["username"],
        "from": cfg["from"],
        "ssl": cfg["ssl"],
        "password_set": bool(cfg["password"]),
        "registration": reg,
    }


@router.put("/api/v1/auth/mail/config")
async def put_mail_config(request: Request):
    if not _owner_request(request):
        return JSONResponse({"detail": "Forbidden"}, status_code=403)
    try:
        data = await request.json()
    except Exception:
        data = {}
    if not isinstance(data, dict):
        return JSONResponse({"detail": "配置格式不正确"}, status_code=422)
    raw: dict = {}
    if MAIL_FILE.exists():
        try:
            raw = json.loads(MAIL_FILE.read_text(encoding="utf-8")) or {}
        except (OSError, json.JSONDecodeError):
            raw = {}
    for key in ("host", "username", "from", "password"):
        if key in data:
            raw[key] = str(data.get(key) or "").strip()
    if "port" in data:
        try:
            raw["port"] = max(1, min(int(data.get("port") or 465), 65535))
        except (TypeError, ValueError):
            return JSONResponse({"detail": "端口不正确"}, status_code=422)
    if "ssl" in data:
        raw["ssl"] = bool(data.get("ssl"))
    if isinstance(data.get("registration"), dict):
        reg = data["registration"]
        raw["registration"] = {
            "allow": bool(reg.get("allow", False)),
            "allowedEmails": [str(x).strip().lower() for x in (reg.get("allowedEmails") or []) if str(x).strip()],
            "debugCodes": bool(reg.get("debugCodes", False)),
        }
    MAIL_FILE.parent.mkdir(parents=True, exist_ok=True)
    MAIL_FILE.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        os.chmod(MAIL_FILE, 0o600)
    except OSError:
        pass
    cfg = mail_config()
    return {
        "configured": mail_configured(),
        "host": cfg["host"], "port": cfg["port"], "username": cfg["username"],
        "from": cfg["from"], "ssl": cfg["ssl"], "password_set": bool(cfg["password"]),
        "registration": registration_config(),
    }


@router.get("/api/v1/auth/stats")
async def stats(request: Request, limit: int = 20):
    session = session_from_scope(request.scope)
    if not (is_local_access(request.scope) or _bearer_ok(request.scope)
            or (session and session.get("role") == "owner")):
        return JSONResponse({"detail": "Forbidden: 需要管理员权限"}, status_code=403)
    with _db_lock:
        rows = _db_conn().execute("SELECT kind, status, COUNT(*) c FROM auth_events GROUP BY kind, status").fetchall()
        recent = _db_conn().execute(
            "SELECT kind, email, ip, geo, status, created_at FROM auth_events ORDER BY created_at DESC LIMIT ?",
            (max(1, min(int(limit), 100)),),
        ).fetchall()
    return {"counts": [dict(r) for r in rows], "recent": [dict(r) for r in recent]}


@router.get("/api/v1/auth/mail/status")
async def mail_status(request: Request):
    if not (is_local_access(request.scope) or _bearer_ok(request.scope)):
        return JSONResponse({"detail": "Unauthorized"}, status_code=401)
    cfg = mail_config()
    return {"configured": mail_configured(), "host": cfg["host"], "port": cfg["port"],
            "from": cfg["from"], "ssl": cfg["ssl"]}


@router.post("/api/v1/auth/mail/test")
async def mail_test(request: Request):
    if not (is_local_access(request.scope) or _bearer_ok(request.scope)):
        return JSONResponse({"detail": "Unauthorized"}, status_code=401)
    try:
        data = await request.json()
    except Exception:
        data = {}
    to = str(data.get("to") or "").strip()
    if not EMAIL_RE.match(to):
        return JSONResponse({"detail": "收件邮箱格式不正确"}, status_code=422)
    ok, err = await send_mail(to, "AIOS SMTP 测试", "这是一封测试邮件，收到即表示 SMTP 配置可用。")
    return {"ok": ok, "error": err}

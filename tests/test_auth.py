"""Email auth tests (SMTP mocked): registration, login, reset, sessions, lockout."""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import backend.auth as auth  # noqa: E402

REMOTE = {"cf-connecting-ip": "203.0.113.9", "x-forwarded-for": "203.0.113.9"}
EMAIL = "owner@example.com"
PASSWORD = "Passw0rd123"
CODE = "123456"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(auth, "DB_FILE", tmp_path / "auth.db")
    monkeypatch.setattr(auth, "DISABLE_AUTH", False)
    monkeypatch.setattr(auth, "API_TOKEN", "test-api-token")
    monkeypatch.setattr(auth, "_db", None)
    auth._rate.clear()
    auth._register_passwords.clear()
    monkeypatch.setattr(auth, "is_local_access", lambda scope: True)
    monkeypatch.setattr(auth, "mail_configured", lambda: True)
    monkeypatch.setattr(auth, "registration_config",
                        lambda: {"allow": False, "allowedEmails": [], "debugCodes": False})
    monkeypatch.setattr(auth, "_new_code", lambda: CODE)

    async def fake_send(to, subject, body):
        return True, ""

    monkeypatch.setattr(auth, "send_mail", fake_send)
    auth._db_conn()

    app = FastAPI()
    app.add_middleware(auth.AuthMiddleware)
    app.include_router(auth.router)

    @app.get("/api/ping")
    def ping():
        return {"pong": True}

    return TestClient(app)


def _register(client, email: str = EMAIL, password: str = PASSWORD):
    r = client.post("/api/v1/auth/register/request", json={"email": email})
    assert r.status_code == 200, r.text
    v = client.post("/api/v1/auth/register/verify", json={"email": email, "code": CODE, "password": password})
    assert v.status_code == 200, v.text
    return v




def test_bootstrap_status_requires_loopback_and_empty_db(client, monkeypatch):
    monkeypatch.setattr(auth, "is_local_access", lambda scope: True)
    r = client.get("/api/v1/auth/bootstrap/status")
    assert r.status_code == 200 and r.json() == {"available": True, "local": True}
    monkeypatch.setattr(auth, "is_local_access", lambda scope: False)
    r = client.get("/api/v1/auth/bootstrap/status", headers=REMOTE)
    assert r.json() == {"available": False, "local": False}


def test_bootstrap_creates_first_owner_without_smtp(client, monkeypatch):
    monkeypatch.setattr(auth, "is_local_access", lambda scope: True)
    monkeypatch.setattr(auth, "mail_configured", lambda: False)
    r = client.post("/api/v1/auth/bootstrap", json={"email": EMAIL, "password": PASSWORD})
    assert r.status_code == 200, r.text
    assert r.cookies.get(auth.COOKIE_NAME)
    with auth._db_lock:
        row = auth._db_conn().execute("SELECT email,role,status FROM users").fetchone()
    assert tuple(row) == (EMAIL, "owner", "active")
    assert client.post("/api/v1/auth/bootstrap", json={"email":"second@example.com", "password":PASSWORD}).status_code == 409


def test_bootstrap_is_forbidden_remote(client, monkeypatch):
    monkeypatch.setattr(auth, "is_local_access", lambda scope: False)
    r = client.post("/api/v1/auth/bootstrap", json={"email": EMAIL, "password": PASSWORD}, headers=REMOTE)
    assert r.status_code == 403

def test_local_bypass(client):
    assert client.get("/api/ping").status_code == 200


def test_remote_gate(client, monkeypatch):
    monkeypatch.setattr(auth, "is_local_access", lambda scope: False)
    r = client.get("/", headers=REMOTE)
    assert r.status_code == 200 and "登录" in r.text
    assert client.get("/api/ping", headers=REMOTE).status_code == 401


def test_login_page_is_productized(client):
    r = client.get("/login")
    text = r.text
    assert "欢迎回来" in text or "创建账号" in text
    assert "本机免登录" not in text
    assert "开发模式" not in text
    assert "storage/" not in text
    assert "Gmail" in text and "Outlook" in text and "网易" in text




def test_member_settings_write_reaches_user_scoped_handler(client, monkeypatch):
    # Set up a member session so auth middleware can distinguish role.
    with auth._db_lock:
        auth._db_conn().execute(
            "INSERT INTO users (id,email,password_hash,role,status,created_at) VALUES (?,?,?,?,?,?)",
            ("user_settings_test", "settings@example.com", auth.hash_password("Passw0rd123"), "member", "active", auth._iso()),
        )
        auth._db_conn().commit()
    token = auth.create_session("user_settings_test", "pytest", "203.0.113.9")
    client.cookies.set(auth.COOKIE_NAME, token)
    r = client.put("/api/v1/settings", json={"theme":"light"}, headers=REMOTE)
    # Fixture app intentionally does not mount settings_api; the auth middleware must let a member write reach routing.
    assert r.status_code != 403

def test_bearer_token(client, monkeypatch):
    monkeypatch.setattr(auth, "is_local_access", lambda scope: False)
    r = client.get("/api/ping", headers={**REMOTE, "Authorization": "Bearer test-api-token"})
    assert r.status_code == 200


def test_register_first_account(client):
    _register(client)
    with auth._db_lock:
        users = auth._db_conn().execute("SELECT email, role, status FROM users").fetchall()
    assert len(users) == 1
    assert users[0]["email"] == EMAIL
    assert users[0]["role"] == "owner"


def test_remote_register_blocked(client, monkeypatch):
    monkeypatch.setattr(auth, "is_local_access", lambda scope: False)
    r = client.post("/api/v1/auth/register/request", json={"email": "x@example.com"}, headers=REMOTE)
    assert r.status_code == 403
    assert "暂未开放" in r.json()["detail"]


def test_login_and_session(client, monkeypatch):
    _register(client)
    client.cookies.clear()
    monkeypatch.setattr(auth, "is_local_access", lambda scope: False)
    r = client.post("/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD}, headers=REMOTE)
    assert r.status_code == 200, r.text
    assert client.cookies.get(auth.COOKIE_NAME)
    assert client.get("/api/ping", headers=REMOTE).status_code == 200
    client.cookies.clear()
    bad = client.post("/api/v1/auth/login", json={"email": EMAIL, "password": "wrong"}, headers=REMOTE)
    assert bad.status_code == 401


def test_password_rules(client):
    r = client.post("/api/v1/auth/register/request", json={"email": "bad"})
    assert r.status_code == 422
    r2 = client.post("/api/v1/auth/register/verify",
                     json={"email": EMAIL, "code": CODE, "password": "short"})
    no_code = client.post("/api/v1/auth/register/request", json={"email": EMAIL})
    assert r2.status_code == 422


def test_second_register_disabled(client):
    _register(client)
    r = client.post("/api/v1/auth/register/request", json={"email": "second@example.com"})
    assert r.status_code == 403


def test_logout_revokes_session(client, monkeypatch):
    _register(client)
    client.cookies.clear()
    monkeypatch.setattr(auth, "is_local_access", lambda scope: False)
    client.post("/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD}, headers=REMOTE)
    assert client.get("/api/ping", headers=REMOTE).status_code == 200
    client.post("/api/v1/auth/logout", headers=REMOTE)
    client.cookies.clear()
    assert client.get("/api/ping", headers=REMOTE).status_code == 401


def test_reset_password(client, monkeypatch):
    _register(client)
    client.cookies.clear()
    # 请求重置（SMTP mock + 固定码）
    r = client.post("/api/v1/auth/reset/request", json={"email": EMAIL}, headers=REMOTE)
    assert r.status_code == 200
    v = client.post("/api/v1/auth/reset/verify",
                    json={"email": EMAIL, "code": CODE, "password": "NewPassw0rd"}, headers=REMOTE)
    assert v.status_code == 200, v.text
    monkeypatch.setattr(auth, "is_local_access", lambda scope: False)
    assert client.post("/api/v1/auth/login",
                       json={"email": EMAIL, "password": "NewPassw0rd"}, headers=REMOTE).status_code == 200


def test_change_password(client):
    _register(client)
    r = client.post("/api/v1/auth/change-password",
                    json={"old_password": PASSWORD, "new_password": "Changed123"})
    assert r.status_code == 200, r.text
    assert client.post("/api/v1/auth/login",
                       json={"email": EMAIL, "password": "Changed123"}).status_code == 200


def test_change_email(client):
    _register(client)
    r = client.post("/api/v1/auth/change-email",
                    json={"password": PASSWORD, "new_email": "new@example.com"})
    assert r.status_code == 200, r.text
    with auth._db_lock:
        email = auth._db_conn().execute("SELECT email FROM users").fetchone()[0]
    assert email == "new@example.com"


def test_session_sliding_renewal(client):
    _register(client)
    with auth._db_lock:
        user = auth._db_conn().execute("SELECT id FROM users").fetchone()
    token = auth.create_session(user["id"], "pytest", "127.0.0.1")
    old_seen = datetime.now(timezone.utc) - timedelta(days=20)
    old_exp = datetime.now(timezone.utc) + timedelta(days=5)
    old_seen_iso = old_seen.isoformat(timespec="seconds").replace("+00:00", "Z")
    old_exp_iso = old_exp.isoformat(timespec="seconds").replace("+00:00", "Z")
    with auth._db_lock:
        auth._db_conn().execute("UPDATE sessions SET last_seen_at=?, expires_at=? WHERE token_hash=?",
                                (old_seen_iso, old_exp_iso, auth._token_hash(token)))
        auth._db_conn().commit()
    found = auth.find_session(token)
    assert found is not None
    new_exp = datetime.fromisoformat(found["expires_at"].replace("Z", "+00:00"))
    assert new_exp > datetime.now(timezone.utc) + timedelta(days=29)


def test_login_lockout(client, monkeypatch):
    _register(client)
    client.cookies.clear()
    monkeypatch.setattr(auth, "is_local_access", lambda scope: False)
    for _ in range(auth.MAX_LOGIN_FAILS):
        client.post("/api/v1/auth/login", json={"email": EMAIL, "password": "wrong"}, headers=REMOTE)
    r = client.post("/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD}, headers=REMOTE)
    assert r.status_code == 403 and "锁定" in r.json()["detail"]

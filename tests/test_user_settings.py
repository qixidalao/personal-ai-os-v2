"""Per-user settings isolation tests."""
from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import backend.settings_api as settings_api
import backend.auth as auth


def _client(tmp_path, monkeypatch, user_id, role):
    monkeypatch.setattr(settings_api, "SETTINGS_FILE", tmp_path / "instance.json")
    monkeypatch.setattr(settings_api, "USER_SETTINGS_DIR", tmp_path / "users")
    monkeypatch.setattr(settings_api, "_is_owner_request", lambda req: role == "owner")
    monkeypatch.setattr(settings_api, "_settings_identity",
                        lambda req: (req.headers.get("x-test-user", ""), req.headers.get("x-test-role", "member")))
    app=FastAPI(); app.include_router(settings_api.router)
    return TestClient(app, headers={"X-Test-User": user_id, "X-Test-Role": role})


def test_member_provider_settings_are_per_user(tmp_path, monkeypatch):
    a=_client(tmp_path,monkeypatch,"user_a","member")
    b=_client(tmp_path,monkeypatch,"user_b","member")
    r=a.put("/api/v1/settings",json={"providers":[{"name":"mine","key":"secret-a","baseUrl":"https://a.test/v1","models":["m1"]}],"theme":"light"})
    assert r.status_code==200
    assert a.get("/api/v1/settings").json()["providers"][0]["key"]=="secret-a"
    rb=b.get("/api/v1/settings").json()
    assert rb["providers"]==[]
    assert rb["theme"]=="dark"


def test_member_reset_does_not_touch_instance_settings(tmp_path, monkeypatch):
    instance=tmp_path/"instance.json"
    instance.write_text('{"providers":[{"name":"admin","key":"admin-secret"}],"theme":"dark"}',encoding='utf-8')
    c=_client(tmp_path,monkeypatch,"user_c","member")
    c.put("/api/v1/settings",json={"theme":"light","providers":[{"name":"user","key":"own-secret"}]})
    r=c.post("/api/v1/settings/reset")
    assert r.status_code==200 and r.json()["scope"]=="user"
    assert 'admin-secret' in instance.read_text(encoding='utf-8')
    assert c.get("/api/v1/settings").json()["providers"]==[]


def test_unresolved_identity_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setattr(settings_api, "SETTINGS_FILE", tmp_path / "instance.json")
    settings_api.SETTINGS_FILE.write_text('{"providers":[{"key":"global-secret"}]}', encoding="utf-8")
    monkeypatch.setattr(settings_api, "_settings_identity", lambda request: ("", ""))
    app=FastAPI(); app.include_router(settings_api.router)
    response=TestClient(app).get("/api/v1/settings")
    assert response.status_code == 401
    assert "global-secret" not in response.text

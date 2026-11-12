from pathlib import Path
import sys
from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import backend.sessions as sessions


def _client(tmp_path, monkeypatch):
    storage = tmp_path / "storage" / "sessions"
    storage.mkdir(parents=True)
    monkeypatch.setattr(sessions, "STORAGE_DIR", storage)
    monkeypatch.setattr(sessions, "identity", lambda request: ("member-a", "member"))
    monkeypatch.setattr(sessions, "owner_user_id", lambda: "owner-a")
    app = FastAPI()
    app.include_router(sessions.router)
    return TestClient(app), storage


def test_create_session_rejects_path_traversal_ids(tmp_path, monkeypatch):
    client, storage = _client(tmp_path, monkeypatch)
    outside = tmp_path / "outside.json"
    for bad_id in ("../outside", "../../outside", str(tmp_path / "absolute")):
        response = client.post("/api/v1/sessions", json={"id": bad_id, "title": "x"})
        assert response.status_code == 422
    assert not outside.exists()
    assert list(storage.glob("*.json")) == []


def test_create_session_accepts_current_id_format(tmp_path, monkeypatch):
    client, storage = _client(tmp_path, monkeypatch)
    response = client.post("/api/v1/sessions", json={"id": "smuse03ls", "title": "ok"})
    assert response.status_code == 200
    assert (storage / "smuse03ls.json").is_file()

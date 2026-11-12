from pathlib import Path

import pytest

import backend.executor as executor


def test_default_member_storage_is_local(tmp_path, monkeypatch):
    monkeypatch.setattr(executor, "EXEC_ROOT", tmp_path)
    cfg = executor.load_config("user-a", "member")
    assert cfg["storage"]["mode"] == "local"


def test_remote_storage_never_local_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(executor, "EXEC_ROOT", tmp_path)
    cfg = executor.load_config("user-a", "member")
    cfg["mode"] = "disabled"
    executor.save_config("user-a", cfg)
    import asyncio
    with pytest.raises(PermissionError):
        asyncio.run(executor.remote_write_bytes("user-a", "member", "media/x.bin", b"x"))


def test_remote_storage_path_is_user_scoped(tmp_path, monkeypatch):
    monkeypatch.setattr(executor, "EXEC_ROOT", tmp_path)
    cfg = executor.load_config("user-a", "member")
    cfg["mode"] = "ssh"
    cfg["storage"] = {"mode": "remote", "path": "~/aios-data"}
    executor.save_config("user-a", cfg)
    loaded = executor.load_config("user-a", "member")
    assert loaded["storage"]["mode"] == "remote"
    assert loaded["storage"]["path"] == "~/aios-data"
    assert (tmp_path / "user-a" / "executor.json").exists()

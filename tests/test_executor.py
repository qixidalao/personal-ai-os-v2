"""Executor unit tests: SSRF policy, defaults, config persistence."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import backend.executor as ex  # noqa: E402


@pytest.fixture()
def tmp_exec(monkeypatch, tmp_path):
    monkeypatch.setattr(ex, "EXEC_ROOT", tmp_path)
    return tmp_path


def test_defaults():
    assert ex.default_config("owner")["mode"] == "local"
    assert ex.default_config("member")["mode"] == "disabled"


def test_member_blocks_local_targets():
    for bad in ("127.0.0.1", "localhost", "10.0.0.5", "192.168.1.1", "169.254.169.254", "::1"):
        with pytest.raises(ValueError):
            ex.validate_target(bad, "member", 22)


def test_owner_allows_local_target():
    assert ex.validate_target("127.0.0.1", "owner", 22) == "127.0.0.1"


def test_member_allows_public_ip():
    assert ex.validate_target("8.8.8.8", "member", 22) == "8.8.8.8"


def test_config_roundtrip(tmp_exec):
    cfg = ex.load_config("user_x", "member")
    assert cfg["mode"] == "disabled"
    cfg["mode"] = "ssh"
    cfg["ssh"] = {"host": "8.8.8.8", "port": 22, "user": "aios",
                  "image": "aios-runner:latest", "host_key": "8.8.8.8 ssh-ed25519 AAAA"}
    ex.save_config("user_x", cfg)
    loaded = ex.load_config("user_x", "member")
    assert loaded["mode"] == "ssh"
    assert loaded["ssh"]["host"] == "8.8.8.8"
    assert (tmp_exec / "user_x" / "ssh" / "known_hosts").exists()


def test_run_without_ssh_config_denied(tmp_exec):
    import asyncio
    with pytest.raises(PermissionError):
        asyncio.run(ex.run_remote("user_y", "member", "echo hi"))

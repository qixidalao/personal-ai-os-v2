"""P0 execution boundary regression tests."""
# 中文：P0 执行边界回归测试。
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from runtime.execution import ExecutionManager, ExecutionPolicy, WorkspaceViolation  # noqa: E402
from runtime.execution.sandbox import sandbox_available  # noqa: E402

requires_bwrap = pytest.mark.skipif(not sandbox_available(), reason="bwrap sandbox unavailable")


@pytest.fixture()
def manager(tmp_path):
    policy = ExecutionPolicy(
        enabled=True,
        allowed_roots=[str(tmp_path)],
        allow_shell=True,
        allow_python=True,
        allow_network=False,
        default_timeout=10,
        max_timeout=60,
        max_output_bytes=16 * 1024,
        max_concurrent=1,
    )
    return ExecutionManager(policy)


# ---------------- workspace path boundary (no sandbox needed) ----------------  ｜ ---------------- 工作区路径边界（无需沙箱） ----------------
def test_workspace_allows_inside(tmp_path):
    m = ExecutionManager(ExecutionPolicy(allowed_roots=[str(tmp_path)]))
    target = tmp_path / "a.txt"
    m.write_text(str(target), "hello")
    assert m.read_text(str(target)) == "hello"
    assert str(target) in m.list_dir(str(tmp_path))


def test_workspace_rejects_traversal(tmp_path):
    m = ExecutionManager(ExecutionPolicy(allowed_roots=[str(tmp_path)]))
    with pytest.raises(WorkspaceViolation):
        m.read_text(str(tmp_path / ".." / "etc" / "hostname"))


def test_workspace_rejects_absolute_outside(tmp_path):
    m = ExecutionManager(ExecutionPolicy(allowed_roots=[str(tmp_path)]))
    with pytest.raises(WorkspaceViolation):
        m.read_text("/etc/hostname")


def test_workspace_rejects_symlink_escape(tmp_path):
    m = ExecutionManager(ExecutionPolicy(allowed_roots=[str(tmp_path)]))
    link = tmp_path / "link"
    try:
        os.symlink("/etc/hostname", link)
    except (OSError, NotImplementedError):
        pytest.skip("symlink unsupported")
    with pytest.raises(WorkspaceViolation):
        m.read_text(str(link))


def test_workspace_rejects_prefix_collision(tmp_path):
    allowed = tmp_path / "work"
    allowed.mkdir()
    sibling = tmp_path / "work-secret"
    sibling.mkdir()
    m = ExecutionManager(ExecutionPolicy(allowed_roots=[str(allowed)]))
    with pytest.raises(WorkspaceViolation):
        m.read_text(str(sibling / "x.txt"))


# ---------------- sandbox execution ----------------  ｜ ---------------- 沙箱执行 ----------------
@requires_bwrap
def test_python_basic(manager):
    result = manager.execute_python("print('hello sandbox')")
    assert result["status"] == "succeeded", result
    assert "hello sandbox" in result["stdout"]


@requires_bwrap
def test_python_does_not_see_host_env(manager, monkeypatch):
    monkeypatch.setenv("AIOS_SECRET_TOKEN", "super-secret")
    result = manager.execute_python("import os; print(os.environ.get('AIOS_SECRET_TOKEN'))")
    assert result["status"] == "succeeded", result
    assert "super-secret" not in result["stdout"]
    assert result["stdout"].strip() == "None"


@requires_bwrap
def test_python_cannot_read_ssh_keys(manager):
    result = manager.execute_python("print(open('/root/.ssh/id_rsa').read()[:10])")
    assert result["status"] == "failed"
    assert "FileNotFoundError" in result["stderr"] or "PermissionError" in result["stderr"]


@requires_bwrap
def test_python_cannot_read_mnt(manager):
    result = manager.execute_python("import os; print(os.listdir('/mnt/c'))")
    assert result["status"] == "failed"


@requires_bwrap
def test_python_network_blocked(manager):
    code = "import socket; socket.create_connection(('1.1.1.1', 80), timeout=2); print('connected')"
    result = manager.execute_python(code)
    assert result["status"] == "failed"
    assert "connected" not in result["stdout"]


@requires_bwrap
def test_python_can_write_workspace(manager, tmp_path):
    target = tmp_path / "out.txt"
    code = f"open({str(target)!r}, 'w').write('ok'); print('done')"
    result = manager.execute_python(code)
    assert result["status"] == "succeeded", result
    assert target.read_text() == "ok"


@requires_bwrap
def test_timeout_kills_process(manager):
    result = manager.execute_python("while True: pass", timeout=2)
    assert result["status"] == "timeout"
    assert result["duration_ms"] < 15000


@requires_bwrap
def test_output_is_capped(manager):
    result = manager.execute_python("print('x' * 200000)")
    assert result["status"] == "succeeded"
    assert result["truncated"] is True
    assert len(result["stdout"].encode()) <= 16 * 1024 + 200


@requires_bwrap
def test_shell_basic(manager):
    result = manager.execute_shell("echo shell-ok && pwd")
    assert result["status"] == "succeeded", result
    assert "shell-ok" in result["stdout"]

"""bwrap based OS sandbox command builder."""
# 中文：基于 bwrap 的 OS 沙箱命令构造器。
from __future__ import annotations

import shutil
import subprocess
from functools import lru_cache

from .errors import SandboxUnavailable
from .models import ExecRequest

BWRAP = shutil.which("bwrap")


@lru_cache(maxsize=1)
def sandbox_available() -> bool:
    if not BWRAP:
        return False
    try:
        proc = subprocess.run(
            [BWRAP, "--ro-bind", "/", "/", "--dev", "/dev", "--", "/bin/true"],
            capture_output=True,
            timeout=8,
        )
        return proc.returncode == 0
    except Exception:
        return False


def sandbox_backend_name() -> str:
    return "bwrap" if sandbox_available() else "none"


def build_command(request: ExecRequest, roots: list[str], cwd: str) -> list[str]:
    """Build the bwrap argv for *request*.

    The host filesystem is mounted read-only, sensitive runtime directories are
    masked with tmpfs, and only the allowed workspace roots are bind-mounted
    read-write. Host environment variables are cleared.
    """
    # 中文：为 *request* 构造 bwrap argv。 主机文件系统以只读方式挂载；敏感运行时目录由 tmpfs 屏蔽；仅允许的工作区根目录以读写方式绑定挂载。主机环境变量会被清除。
    if not sandbox_available():
        raise SandboxUnavailable("bwrap 沙箱不可用（缺少 bwrap 或用户命名空间被禁用）")

    if request.python_code is not None:
        payload = ["python3", "-"]
    elif request.shell_command is not None:
        payload = ["bash", "-lc", request.shell_command]
    else:
        payload = list(request.argv)
    if not payload:
        raise SandboxUnavailable("执行请求为空")

    cmd: list[str] = [
        BWRAP or "bwrap",
        "--die-with-parent",
        "--new-session",
        "--unshare-all",
    ]
    if request.network:
        cmd.append("--share-net")

    cmd += [
        "--ro-bind", "/", "/",
        "--tmpfs", "/home",
        "--tmpfs", "/root",
        "--tmpfs", "/mnt",
        "--tmpfs", "/media",
        "--tmpfs", "/run",
        "--tmpfs", "/tmp",
        "--proc", "/proc",
        "--dev", "/dev",
    ]
    for root in roots:
        cmd += ["--bind", root, root]

    cmd += [
        "--chdir", cwd,
        "--clearenv",
        "--setenv", "PATH", "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "--setenv", "HOME", "/tmp/aios-home",
        "--setenv", "TMPDIR", "/tmp",
        "--setenv", "LANG", "C.UTF-8",
        "--setenv", "PYTHONUNBUFFERED", "1",
        "--setenv", "PYTHONDONTWRITEBYTECODE", "1",
        "--dir", "/tmp/aios-home",
        "--",
        *payload,
    ]
    return cmd

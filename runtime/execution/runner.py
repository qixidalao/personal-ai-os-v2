"""Low-level process runner with hard timeouts and output caps."""
# 中文：带硬超时和输出上限的底层进程运行器。
from __future__ import annotations

import os
import resource
import signal
import subprocess
import threading
import time
from typing import Callable

from .models import ExecResult

MAX_READ_CHUNK = 64 * 1024


def _limits(timeout_s: int, max_output_bytes: int):
    def apply() -> None:
        try:
            cpu = int(timeout_s) + 5
            resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu))
        except (ValueError, OSError):
            pass
        try:
            mem = 1536 * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_AS, (mem, mem))
        except (ValueError, OSError):
            pass
        try:
            # 注意：RLIMIT_NPROC 按 uid 统计，沙箱内进程也计入宿主用户，
            # 设太小会导致 bwrap clone() 直接 EAGAIN，这里只做宽松上限。
            resource.setrlimit(resource.RLIMIT_NPROC, (2048, 2048))
        except (ValueError, OSError):
            pass
        try:
            resource.setrlimit(resource.RLIMIT_NOFILE, (256, 256))
        except (ValueError, OSError):
            pass
        try:
            fsize = max(8 * 1024 * 1024, int(max_output_bytes) * 4)
            resource.setrlimit(resource.RLIMIT_FSIZE, (fsize, fsize))
        except (ValueError, OSError):
            pass
        try:
            resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        except (ValueError, OSError):
            pass

    return apply


def _drain(stream, cap: int, bucket: list[bytes], state: dict) -> None:
    total = 0
    try:
        while True:
            chunk = stream.read(MAX_READ_CHUNK)
            if not chunk:
                break
            room = cap - total
            if room > 0:
                piece = chunk[:room]
                bucket.append(piece)
                total += len(piece)
                if len(piece) < len(chunk):
                    state["truncated"] = True
            else:
                state["truncated"] = True
    except Exception:
        state["error"] = True
    finally:
        try:
            stream.close()
        except Exception:
            pass


def run_process(
    cmd: list[str],
    *,
    timeout_s: int,
    max_output_bytes: int,
    stdin_data: bytes | None = None,
    cwd: str | None = None,
    on_spawn: Callable[[subprocess.Popen], None] | None = None,
    sandbox: str = "bwrap",
) -> ExecResult:
    started = time.monotonic()
    proc: subprocess.Popen | None = None
    try:
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE if stdin_data is not None else subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=cwd,
            start_new_session=True,
            preexec_fn=_limits(timeout_s, max_output_bytes),
            close_fds=True,
        )
    except FileNotFoundError as exc:
        return ExecResult(status="failed", error=f"执行器不存在: {exc}", sandbox=sandbox,
                          duration_ms=int((time.monotonic() - started) * 1000))
    except OSError as exc:
        return ExecResult(status="failed", error=f"进程启动失败: {exc}", sandbox=sandbox,
                          duration_ms=int((time.monotonic() - started) * 1000))

    if on_spawn is not None:
        try:
            on_spawn(proc)
        except Exception:
            pass

    out_buf: list[bytes] = []
    err_buf: list[bytes] = []
    state = {"truncated": False, "error": False}
    assert proc.stdout is not None and proc.stderr is not None
    t_out = threading.Thread(target=_drain, args=(proc.stdout, max_output_bytes, out_buf, state), daemon=True)
    t_err = threading.Thread(target=_drain, args=(proc.stderr, max_output_bytes, err_buf, state), daemon=True)
    t_out.start()
    t_err.start()

    if stdin_data is not None and proc.stdin is not None:
        try:
            proc.stdin.write(stdin_data)
            proc.stdin.close()
        except (BrokenPipeError, OSError):
            pass

    timed_out = False
    try:
        proc.wait(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        timed_out = True
        _kill_group(proc)
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass

    t_out.join(timeout=3)
    t_err.join(timeout=3)

    stdout = b"".join(out_buf).decode("utf-8", "replace")
    stderr = b"".join(err_buf).decode("utf-8", "replace")
    duration = int((time.monotonic() - started) * 1000)

    if timed_out:
        return ExecResult(status="timeout", exit_code=proc.returncode, stdout=stdout, stderr=stderr,
                          truncated=state["truncated"], duration_ms=duration, sandbox=sandbox,
                          error=f"执行超时（>{timeout_s}s），进程组已被终止")
    status = "succeeded" if proc.returncode == 0 else "failed"
    return ExecResult(status=status, exit_code=proc.returncode, stdout=stdout, stderr=stderr,
                      truncated=state["truncated"], duration_ms=duration, sandbox=sandbox,
                      error=None if proc.returncode == 0 else f"退出码 {proc.returncode}")


def _kill_group(proc: subprocess.Popen) -> None:
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError):
        try:
            proc.kill()
        except Exception:
            pass

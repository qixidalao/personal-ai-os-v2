"""Execution manager: policy + sandbox + workspace in one boundary."""
# 中文：执行管理器：在同一边界内统一处理策略、沙箱和工作区。
from __future__ import annotations

import contextvars
import logging
import threading
from pathlib import Path
from typing import Any

from .errors import ExecutionDenied, SandboxUnavailable, WorkspaceViolation
from .models import ExecRequest, ExecResult
from .policy import PROJECT_ROOT, load_policy
from .runner import run_process
from .sandbox import build_command, sandbox_available, sandbox_backend_name
from .workspace import WorkspaceFS

log = logging.getLogger("aios.execution")

current_run: contextvars.ContextVar[str | None] = contextvars.ContextVar("aios_run_id", default=None)
current_tool_call: contextvars.ContextVar[str | None] = contextvars.ContextVar("aios_tool_call_id", default=None)


class ExecutionManager:
    def __init__(self, policy=None):
        self.policy = policy or load_policy()
        self.workspace = WorkspaceFS(self.policy.allowed_roots)
        self._sem = threading.BoundedSemaphore(self.policy.max_concurrent)
        self._running: dict[str, set[Any]] = {}
        self._lock = threading.Lock()
        self._backend = sandbox_backend_name()

    # ---------------- capabilities ----------------  ｜ ---------------- 功能 ----------------
    @property
    def backend(self) -> str:
        return self._backend

    def status(self) -> dict:
        return {
            "enabled": self.policy.enabled,
            "sandbox": self._backend,
            "sandboxAvailable": sandbox_available(),
            "allowedRoots": self.policy.allowed_roots,
            "allowShell": self.policy.allow_shell,
            "allowPython": self.policy.allow_python,
            "allowNetwork": self.policy.allow_network,
            "maxConcurrent": self.policy.max_concurrent,
            "maxTimeout": self.policy.max_timeout,
            "maxOutputBytes": self.policy.max_output_bytes,
        }

    # ---------------- lifecycle ----------------  ｜ ---------------- 生命周期 ----------------
    def cancel(self, run_id: str | None) -> int:
        if not run_id:
            return 0
        with self._lock:
            procs = list(self._running.pop(run_id, set()))
        killed = 0
        for proc in procs:
            try:
                import os
                import signal
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                killed += 1
            except Exception:
                try:
                    proc.kill()
                    killed += 1
                except Exception:
                    pass
        return killed

    def _register(self, run_id: str | None, proc) -> None:
        if not run_id:
            return
        with self._lock:
            self._running.setdefault(run_id, set()).add(proc)

    def _unregister(self, run_id: str | None, proc) -> None:
        if not run_id:
            return
        with self._lock:
            bucket = self._running.get(run_id)
            if bucket:
                bucket.discard(proc)
                if not bucket:
                    self._running.pop(run_id, None)

    # ---------------- entry points ----------------  ｜ ---------------- 入口点 ----------------
    def execute_python(self, code: str, *, timeout: int | None = None, network: bool | None = None) -> dict:
        request = ExecRequest(
            tool="python_exec",
            python_code=code,
            timeout_s=self.policy.clamp_timeout(timeout),
            max_output_bytes=self.policy.max_output_bytes,
            network=self.policy.allow_network if network is None else bool(network),
            run_id=current_run.get(),
            tool_call_id=current_tool_call.get(),
        )
        return self._execute(request, guard=lambda: self._check_python_allowed())

    def execute_shell(self, command: str, *, timeout: int | None = None, network: bool | None = None) -> dict:
        request = ExecRequest(
            tool="shell_exec",
            shell_command=command,
            timeout_s=self.policy.clamp_timeout(timeout),
            max_output_bytes=self.policy.max_output_bytes,
            network=self.policy.allow_network if network is None else bool(network),
            run_id=current_run.get(),
            tool_call_id=current_tool_call.get(),
        )
        return self._execute(request, guard=lambda: self._check_shell_allowed())

    def execute_argv(self, argv: list[str], *, cwd: str | None = None, timeout: int | None = None,
                     network: bool | None = None) -> dict:
        request = ExecRequest(
            tool="exec",
            argv=argv,
            cwd=cwd,
            timeout_s=self.policy.clamp_timeout(timeout),
            max_output_bytes=self.policy.max_output_bytes,
            network=self.policy.allow_network if network is None else bool(network),
            run_id=current_run.get(),
            tool_call_id=current_tool_call.get(),
        )
        return self._execute(request, guard=lambda: self._check_shell_allowed())

    # ---------------- core ----------------  ｜ ---------------- 核心 ----------------
    def _check_shell_allowed(self) -> None:
        if not self.policy.enabled or not self.policy.allow_shell:
            raise ExecutionDenied("shell 执行已被策略禁用（settings.execution.allowShell）")

    def _check_python_allowed(self) -> None:
        if not self.policy.enabled or not self.policy.allow_python:
            raise ExecutionDenied("Python 执行已被策略禁用（settings.execution.allowPython）")

    def _execute(self, request: ExecRequest, guard) -> dict:
        try:
            guard()
            if not sandbox_available():
                raise SandboxUnavailable("bwrap 沙箱不可用，已按 fail-closed 策略拒绝执行")
            cwd = self._resolve_cwd(request.cwd)
            cmd = build_command(request, self.policy.allowed_roots, str(cwd))
        except (ExecutionDenied, WorkspaceViolation) as exc:
            return self._denied(str(exc))
        except Exception as exc:  # noqa: BLE001 - boundary must never crash the tool call
            return self._denied(f"执行边界内部错误: {exc}")

        stdin_data = request.python_code.encode("utf-8") if request.python_code is not None else None
        acquired = self._sem.acquire(timeout=max(1, request.timeout_s))
        if not acquired:
            return self._denied("并发执行数已达上限，请稍后重试")
        try:
            proc_holder: list[Any] = []

            def on_spawn(proc) -> None:
                proc_holder.append(proc)
                self._register(request.run_id, proc)

            result = run_process(
                cmd,
                timeout_s=request.timeout_s,
                max_output_bytes=request.max_output_bytes,
                stdin_data=stdin_data,
                cwd=str(PROJECT_ROOT),
                on_spawn=on_spawn,
                sandbox=self._backend,
            )
            if proc_holder:
                self._unregister(request.run_id, proc_holder[0])
            return result.model_dump()
        finally:
            self._sem.release()

    def _resolve_cwd(self, raw: str | None) -> Path:
        if not raw:
            # 默认 cwd 必须是允许根目录之一；优先项目根（若在策略内），否则用第一个根。
            if any(self.workspace._is_within(PROJECT_ROOT, root) for root in self.workspace.roots):
                return self.workspace.resolve(str(PROJECT_ROOT))
            return self.workspace.resolve(str(self.workspace.roots[0]))
        return self.workspace.resolve(raw)

    @staticmethod
    def _denied(message: str) -> dict:
        return ExecResult(status="denied", sandbox=sandbox_backend_name(), error=message).model_dump()

    # ---------------- filesystem passthrough ----------------  ｜ ---------------- 文件系统透传 ----------------
    def read_text(self, path: str) -> str:
        return self.workspace.read_text(path)

    def write_text(self, path: str, content: str) -> str:
        return str(self.workspace.write_text(path, content))

    def list_dir(self, path: str = ".") -> list[str]:
        return self.workspace.list_dir(path)

    def delete(self, path: str) -> str:
        return str(self.workspace.delete(path))

    def info(self, path: str) -> dict:
        return self.workspace.info(path)


_manager: ExecutionManager | None = None
_manager_lock = threading.Lock()


def get_execution_manager() -> ExecutionManager:
    global _manager
    if _manager is None:
        with _manager_lock:
            if _manager is None:
                _manager = ExecutionManager()
    return _manager

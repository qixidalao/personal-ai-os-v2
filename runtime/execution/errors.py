"""Execution boundary errors."""
# 中文：执行边界错误。
from __future__ import annotations


class ExecutionError(Exception):
    """Base error for execution boundary."""
    # 中文：执行边界的基础错误。


class ExecutionDenied(ExecutionError):
    """Execution blocked by policy (disabled tool, sandbox unavailable, limits)."""
    # 中文：策略禁止执行（工具已禁用、沙箱不可用或超出限制）。


class SandboxUnavailable(ExecutionDenied):
    """No usable OS sandbox backend (bwrap missing / userns denied)."""
    # 中文：没有可用的 OS 沙箱后端（缺少 bwrap / userns 被拒绝）。


class WorkspaceViolation(ExecutionError):
    """Path escapes allowed roots or goes through a symlink."""
    # 中文：路径超出允许的根目录或经过符号链接。

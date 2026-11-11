"""AIOS execution boundary (P0).

Import surface used by tools and the chat runtime:

    from runtime.execution import get_execution_manager, current_run, current_tool_call
"""
# 中文：AIOS 执行边界（P0）。 工具和聊天运行时使用的导入接口： from runtime.execution import get_execution_manager, current_run, current_tool_call
from .errors import ExecutionDenied, ExecutionError, SandboxUnavailable, WorkspaceViolation
from .manager import ExecutionManager, current_run, current_tool_call, get_execution_manager
from .models import ExecRequest, ExecResult, ExecutionPolicy

__all__ = [
    "ExecutionManager",
    "ExecutionPolicy",
    "ExecRequest",
    "ExecResult",
    "ExecutionDenied",
    "ExecutionError",
    "SandboxUnavailable",
    "WorkspaceViolation",
    "current_run",
    "current_tool_call",
    "get_execution_manager",
]

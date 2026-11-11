"""Python execution tool executed inside the AIOS execution boundary (P0).

The code is run in a separate bwrap-sandboxed process; it never executes inside
the FastAPI process.
"""
# 中文：在 AIOS 执行边界内运行的 Python 执行工具（P0）。 代码在单独的 bwrap 沙箱进程中运行；不会在 FastAPI 进程内执行。
from tools import ToolRegistry

from runtime.execution import get_execution_manager

PERMISSIONS = ["exec"]


@ToolRegistry.register(
    "python_exec",
    "在受控沙箱内执行 Python 代码：只允许读写工作区、默认禁网、有超时与输出上限。",
    "python",
    # 中文：python
    permissions=PERMISSIONS,
)
def python_exec(code: str, timeout: int = 30) -> dict:
    result = get_execution_manager().execute_python(code, timeout=timeout)
    return {
        "stdout": result.get("stdout", ""),
        "stderr": result.get("stderr", ""),
        "return_code": result.get("exit_code"),
        "success": result.get("status") == "succeeded",
        "truncated": result.get("truncated", False),
        "duration_ms": result.get("duration_ms"),
        "sandbox": result.get("sandbox"),
        "error": result.get("error"),
    }

"""Shell tool executed inside the AIOS execution boundary (P0)."""
# 中文：在 AIOS 执行边界内运行的 Shell 工具（P0）。
from tools import ToolRegistry

from runtime.execution import get_execution_manager

PERMISSIONS = ["exec"]


@ToolRegistry.register(
    "shell_exec",
    "在受控沙箱内执行 Shell 命令：只允许读写工作区、默认禁网、有超时与输出上限。",
    "shell",
    # 中文：shell
    permissions=PERMISSIONS,
)
def shell_exec(command: str, timeout: int = 30) -> dict:
    result = get_execution_manager().execute_shell(command, timeout=timeout)
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

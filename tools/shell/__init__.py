"""
Shell 工具
"""
import subprocess
from tools import ToolRegistry


@ToolRegistry.register("shell_exec", "执行 Shell 命令", "shell")
def shell_exec(command: str, timeout: int = 30) -> dict:
    result = subprocess.run(
        command,
        shell=True,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return {
        "stdout": result.stdout,
        "stderr": result.stderr,
        "return_code": result.returncode,
        "success": result.returncode == 0,
    }

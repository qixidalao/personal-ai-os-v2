"""
Python 执行工具
"""
import sys
import io
import traceback
from tools import ToolRegistry


@ToolRegistry.register("python_exec", "执行 Python 代码", "python")
def python_exec(code: str, timeout: int = 30) -> dict:
    """执行 Python 代码并返回结果"""
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    sys.stdout = io.StringIO()
    sys.stderr = io.StringIO()

    try:
        compiled = compile(code, "<string>", "exec")
        exec(compiled, {"__builtins__": __builtins__})
        stdout = sys.stdout.getvalue()
        stderr = sys.stderr.getvalue()
        return {
            "stdout": stdout,
            "stderr": stderr,
            "success": True,
        }
    except Exception as e:
        return {
            "stdout": sys.stdout.getvalue(),
            "stderr": traceback.format_exc(),
            "success": False,
            "error": str(e),
        }
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr

"""
集成测试 — Shell 工具
"""

import pytest
import tools.shell
from tools import ToolRegistry


class TestShellExec:
    """测试 shell_exec 工具"""

    def test_simple_command(self):
        result = ToolRegistry.call("shell_exec", command="echo hello world")
        assert result["success"] is True
        assert result["return_code"] == 0
        assert "hello world" in result["stdout"]

    def test_command_with_stderr(self):
        """测试命令产生 stderr 输出"""
        result = ToolRegistry.call("shell_exec", command="echo error >&2")
        assert result["success"] is True
        assert "error" in result["stderr"]

    def test_failing_command(self):
        result = ToolRegistry.call("shell_exec", command="exit 42")
        assert result["success"] is False
        assert result["return_code"] == 42

    def test_empty_command(self):
        result = ToolRegistry.call("shell_exec", command="")
        assert result["success"] is True
        assert result["return_code"] == 0

    def test_pipeline(self):
        result = ToolRegistry.call("shell_exec", command="echo 'a b c' | wc -w")
        assert result["success"] is True
        assert "3" in result["stdout"].strip()

    def test_timeout_raises(self):
        """测试超时设置生效"""
        with pytest.raises(Exception):
            ToolRegistry.call("shell_exec", command="sleep 10", timeout=1)

    def test_custom_timeout(self):
        """测试自定义 timeout 参数"""
        result = ToolRegistry.call("shell_exec", command="echo quick", timeout=5)
        assert result["success"] is True

    def test_unicode_output(self):
        result = ToolRegistry.call("shell_exec", command="echo '中文测试 🎉'")
        assert "中文测试 🎉" in result["stdout"]

    def return_structure(self):
        """测试返回结构的完整性"""
        result = ToolRegistry.call("shell_exec", command="echo hi")
        assert "stdout" in result
        assert "stderr" in result
        assert "return_code" in result
        assert "success" in result

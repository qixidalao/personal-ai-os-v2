"""
🛠️ Agent 工具调用演示 — 正确版测试脚本
测试方式：导入工具模块触发注册 → 通过 ToolRegistry 调用
"""

import pytest
from pathlib import Path

# ============================================================
# 关键：导入工具模块，触发 @ToolRegistry.register 装饰器
# ============================================================
import tools.filesystem   # 注册 file_read, write_file, list_dir, delete_file, file_info
import tools.python       # 注册 python_exec

from tools import ToolRegistry


class TestPythonTool:
    """测试 python_exec 工具"""

    def test_python_eval_simple(self):
        """执行简单的 Python 表达式"""
        result = ToolRegistry.call("python_exec", code="x = 1 + 1")
        assert result["success"] is True

    def test_python_print_output(self):
        """执行带 print 的代码"""
        result = ToolRegistry.call("python_exec", code='print("Hello, Agent!")')
        assert result["success"] is True
        assert "Hello, Agent!" in result["stdout"]

    def test_python_with_import(self):
        """执行带 import 的代码"""
        result = ToolRegistry.call("python_exec", code="""
import math
print(math.sqrt(16))
""")
        assert result["success"] is True
        assert "4.0" in result["stdout"]

    def test_python_syntax_error(self):
        """语法错误应返回错误信息而非崩溃"""
        result = ToolRegistry.call("python_exec", code="def foo( : ")
        assert result["success"] is False
        assert "SyntaxError" in result["stderr"]


class TestFileSystemTools:
    """测试文件系统工具组"""

    def test_write_then_read(self, tmp_path: Path):
        """先用 write_file 写入，再用 file_read 读取"""
        test_file = tmp_path / "agent_test.txt"

        # 写入
        write_result = ToolRegistry.call(
            "write_file",
            path=str(test_file),
            content="Agent 测试内容 🚀"
        )
        assert test_file.exists()
        assert "已写入" in write_result

        # 读取
        read_result = ToolRegistry.call("file_read", path=str(test_file))
        assert read_result == "Agent 测试内容 🚀"

    def test_list_dir_contains_file(self, tmp_path: Path):
        """写入文件后 list_dir 能正确列出"""
        test_file = tmp_path / "list_check.txt"
        test_file.write_text("check")

        items = ToolRegistry.call("list_dir", path=str(tmp_path))
        paths_str = " ".join(str(p) for p in items)
        assert "list_check.txt" in paths_str

    def test_file_info(self, tmp_path: Path):
        """验证 file_info 返回正确信息"""
        test_file = tmp_path / "info_test.txt"
        test_file.write_text("hello")

        info = ToolRegistry.call("file_info", path=str(test_file))
        assert info["name"] == "info_test.txt"
        assert info["size"] == 5
        assert info["is_dir"] is False
        assert info["extension"] == ".txt"

    def test_delete_file(self, tmp_path: Path):
        """删除文件后文件应不存在"""
        test_file = tmp_path / "to_delete.txt"
        test_file.write_text("bye")
        assert test_file.exists()

        ToolRegistry.call("delete_file", path=str(test_file))
        assert not test_file.exists()


class TestEdgeCases:
    """边界场景测试"""

    def test_empty_python_code(self):
        """空代码执行"""
        result = ToolRegistry.call("python_exec", code="")
        assert result["success"] is True

    def test_python_list_creation(self):
        """创建列表类型"""
        result = ToolRegistry.call("python_exec", code="x = [1, 2, 3]; print(x)")
        assert result["success"] is True
        assert "[1, 2, 3]" in result["stdout"]

    def test_file_read_not_found(self):
        """读取不存在的文件应抛异常"""
        with pytest.raises(FileNotFoundError):
            ToolRegistry.call("file_read", path="/tmp/_nonexistent_xyz_")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

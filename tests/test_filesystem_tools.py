"""
集成测试 — 文件系统工具
"""

import os
import pytest
from pathlib import Path
import tools.filesystem
from tools import ToolRegistry


class TestFileRead:
    """测试 file_read 工具"""

    def test_read_existing_file(self, tmp_path: Path):
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello, World!")
        result = ToolRegistry.call("file_read", path=str(test_file))
        assert result == "Hello, World!"

    def test_read_nonexistent_file(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            ToolRegistry.call("file_read", path=str(tmp_path / "ghost.txt"))

    def test_read_empty_file(self, tmp_path: Path):
        test_file = tmp_path / "empty.txt"
        test_file.write_text("")
        result = ToolRegistry.call("file_read", path=str(test_file))
        assert result == ""

    def test_read_utf8_file(self, tmp_path: Path):
        test_file = tmp_path / "utf8.txt"
        test_file.write_text("中文测试 🎉")
        result = ToolRegistry.call("file_read", path=str(test_file))
        assert result == "中文测试 🎉"


class TestWriteFile:
    """测试 write_file 工具"""

    def test_write_new_file(self, tmp_path: Path):
        file_path = tmp_path / "new_file.txt"
        result = ToolRegistry.call("write_file", path=str(file_path), content="Hello")
        assert file_path.exists()
        assert file_path.read_text() == "Hello"
        assert "已写入" in result

    def test_overwrite_existing_file(self, tmp_path: Path):
        file_path = tmp_path / "overwrite.txt"
        file_path.write_text("old content")
        ToolRegistry.call("write_file", path=str(file_path), content="new content")
        assert file_path.read_text() == "new content"

    def test_write_creates_parent_dirs(self, tmp_path: Path):
        file_path = tmp_path / "a" / "b" / "c" / "deep.txt"
        ToolRegistry.call("write_file", path=str(file_path), content="nested")
        assert file_path.exists()
        assert file_path.read_text() == "nested"

    def test_write_empty_content(self, tmp_path: Path):
        file_path = tmp_path / "empty_write.txt"
        ToolRegistry.call("write_file", path=str(file_path), content="")
        assert file_path.exists()
        assert file_path.read_text() == ""


class TestListDir:
    """测试 list_dir 工具"""

    def test_list_current_directory(self, tmp_path: Path):
        # 创建一些文件和目录
        (tmp_path / "file1.txt").write_text("")
        (tmp_path / "file2.txt").write_text("")
        (tmp_path / "subdir").mkdir()

        result = ToolRegistry.call("list_dir", path=str(tmp_path))
        assert len(result) == 3
        # 结果中应包含路径
        paths = [str(p) for p in result]
        assert any("file1.txt" in p for p in paths)
        assert any("subdir" in p for p in paths)

    def test_list_empty_directory(self, tmp_path: Path):
        result = ToolRegistry.call("list_dir", path=str(tmp_path))
        assert result == []

    def test_list_nonexistent_directory(self):
        with pytest.raises(FileNotFoundError):
            ToolRegistry.call("list_dir", path="/nonexistent_path_xyz")

    def test_list_default_path(self):
        # 默认 path="."
        result = ToolRegistry.call("list_dir")
        assert len(result) > 0


class TestDeleteFile:
    """测试 delete_file 工具"""

    def test_delete_existing_file(self, tmp_path: Path):
        file_path = tmp_path / "to_delete.txt"
        file_path.write_text("bye")
        assert file_path.exists()

        result = ToolRegistry.call("delete_file", path=str(file_path))
        assert not file_path.exists()
        assert "已删除" in result

    def test_delete_nonexistent_file(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            ToolRegistry.call("delete_file", path=str(tmp_path / "ghost.txt"))


class TestFileInfo:
    """测试 file_info 工具"""

    def test_file_info_basic(self, tmp_path: Path):
        file_path = tmp_path / "info_test.txt"
        file_path.write_text("some content")

        info = ToolRegistry.call("file_info", path=str(file_path))
        assert info["name"] == "info_test.txt"
        assert info["size"] == len("some content")
        assert info["is_dir"] is False
        assert info["extension"] == ".txt"

    def test_file_info_directory(self, tmp_path: Path):
        dir_path = tmp_path / "infodir"
        dir_path.mkdir()

        info = ToolRegistry.call("file_info", path=str(dir_path))
        assert info["name"] == "infodir"
        assert info["is_dir"] is True
        assert info["extension"] == ""

    def test_file_info_nonexistent(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            ToolRegistry.call("file_info", path=str(tmp_path / "ghost.txt"))

    def test_file_info_has_modified_time(self, tmp_path: Path):
        file_path = tmp_path / "timed.txt"
        file_path.write_text("x")

        info = ToolRegistry.call("file_info", path=str(file_path))
        assert "modified" in info
        assert info["modified"] > 0


class TestReadFileAlias:
    """测试 read_file 别名兼容（模块级别名，非 ToolRegistry 注册项）"""

    def test_read_file_alias_function_exists(self):
        """read_file 是模块内的函数引用"""
        assert hasattr(tools.filesystem, "read_file")
        assert callable(tools.filesystem.read_file)

    def test_read_file_alias_works(self, tmp_path: Path):
        """read_file 函数可以直接调用"""
        test_file = tmp_path / "alias.txt"
        test_file.write_text("via alias")
        result = tools.filesystem.read_file(path=str(test_file))
        assert result == "via alias"

    def test_read_file_alias_is_file_read(self):
        """read_file 就是 file_read 的别名"""
        assert tools.filesystem.read_file is tools.filesystem.file_read

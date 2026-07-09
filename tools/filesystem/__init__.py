"""
文件系统工具
"""
from pathlib import Path
from tools import ToolRegistry


@ToolRegistry.register("file_read", "读取文件内容", "filesystem")
def file_read(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


# 兼容旧命名：read_file -> file_read
read_file = file_read


@ToolRegistry.register("write_file", "写入文件内容", "filesystem")
def write_file(path: str, content: str) -> str:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return f"✅ 文件已写入: {path}"


@ToolRegistry.register("list_dir", "列出目录内容", "filesystem")
def list_dir(path: str = ".") -> list:
    return [str(p) for p in Path(path).iterdir()]


@ToolRegistry.register("delete_file", "删除文件", "filesystem")
def delete_file(path: str) -> str:
    Path(path).unlink()
    return f"✅ 文件已删除: {path}"


@ToolRegistry.register("file_info", "获取文件信息", "filesystem")
def file_info(path: str) -> dict:
    p = Path(path)
    return {
        "name": p.name,
        "size": p.stat().st_size,
        "modified": p.stat().st_mtime,
        "is_dir": p.is_dir(),
        "extension": p.suffix,
    }

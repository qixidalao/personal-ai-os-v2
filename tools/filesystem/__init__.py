"""Filesystem tools bound to the AIOS workspace boundary (P0).

All paths must stay inside configured allowed roots; symlink components are
rejected; directory deletion is intentionally not supported in P0.
"""
# 中文：绑定到 AIOS 工作区边界的文件系统工具（P0）。 所有路径必须位于配置的允许根目录内；拒绝包含符号链接的路径；P0 暂不支持删除目录。
from tools import ToolRegistry

from runtime.execution import WorkspaceViolation, get_execution_manager

PERMISSIONS_READ = ["fs_read"]
PERMISSIONS_WRITE = ["fs_read", "fs_write"]


def _manager():
    return get_execution_manager()


@ToolRegistry.register(
    "file_read",
    "读取工作区内文件内容（必须位于允许的工作区根目录内）。",
    "filesystem",
    # 中文：filesystem
    permissions=PERMISSIONS_READ,
)
def file_read(path: str) -> str:
    try:
        return _manager().read_text(path)
    except WorkspaceViolation:
        raise


# 兼容旧命名：read_file -> file_read
read_file = file_read


@ToolRegistry.register(
    "write_file",
    "写入工作区内文件（目录会自动创建；路径必须位于允许的工作区根目录内）。",
    "filesystem",
    # 中文：filesystem
    permissions=PERMISSIONS_WRITE,
)
def write_file(path: str, content: str) -> str:
    try:
        resolved = _manager().write_text(path, content)
    except WorkspaceViolation:
        raise
    return f"✅ 文件已写入: {resolved}"


@ToolRegistry.register(
    "list_dir",
    "列出工作区内目录内容（必须位于允许的工作区根目录内）。",
    "filesystem",
    # 中文：filesystem
    permissions=PERMISSIONS_READ,
)
def list_dir(path: str = ".") -> list:
    try:
        return _manager().list_dir(path)
    except WorkspaceViolation:
        raise


@ToolRegistry.register(
    "delete_file",
    "删除工作区内单个文件（不支持删除目录；路径必须位于允许的工作区根目录内）。",
    "filesystem",
    # 中文：filesystem
    permissions=PERMISSIONS_WRITE,
)
def delete_file(path: str) -> str:
    try:
        resolved = _manager().delete(path)
    except WorkspaceViolation:
        raise
    return f"✅ 文件已删除: {resolved}"


@ToolRegistry.register(
    "file_info",
    "获取工作区内文件/目录信息（必须位于允许的工作区根目录内）。",
    "filesystem",
    # 中文：filesystem
    permissions=PERMISSIONS_READ,
)
def file_info(path: str) -> dict:
    try:
        return _manager().info(path)
    except WorkspaceViolation:
        raise

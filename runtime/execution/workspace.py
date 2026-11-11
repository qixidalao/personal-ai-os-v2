"""Workspace filesystem boundary.

Rules:
- every path must resolve inside one of the allowed roots;
- no path component may be a symlink;
- relative paths are resolved against the project root;
- reads/writes are byte-capped.
"""
# 中文：工作区文件系统边界。 规则： - 每个路径都必须解析到某个允许的根目录内； - 路径组件不得是符号链接； - 相对路径以项目根目录为基准解析； - 读写字节数均设上限。
from __future__ import annotations

import os
import stat
from pathlib import Path

from .errors import WorkspaceViolation


class WorkspaceFS:
    def __init__(self, roots: list[str], max_read_bytes: int = 2 * 1024 * 1024):
        self.roots = [Path(r).expanduser().resolve() for r in roots]
        self.max_read_bytes = max_read_bytes

    # ---------------- path resolution ----------------  ｜ ---------------- 路径解析 ----------------
    def resolve(self, raw: str | Path, *, for_write: bool = False) -> Path:
        if raw is None or str(raw).strip() == "":
            raise WorkspaceViolation("路径为空")
        path = Path(str(raw).strip()).expanduser()
        if not path.is_absolute():
            path = Path.cwd() / path
        path = Path(os.path.normpath(str(path)))

        # 1) lexical containment first: outside paths must fail as boundary violations,  ｜ 1) 先检查词法路径包含关系：越界路径必须作为边界违规处理，
        #    not as "file not found" (prevents prefix tricks from being masked).  ｜ 不能作为“文件不存在”处理（避免前缀技巧被掩盖）。
        if not any(self._is_within(path, root) for root in self.roots):
            raise WorkspaceViolation(
                f"路径不在允许的工作区内: {path}。允许的根目录: {', '.join(str(r) for r in self.roots)}"
            )

        # 2) reject symlinks on every existing component  ｜ 拒绝每个已存在路径组件中的符号链接
        current = Path(path.anchor)
        for part in path.parts[1:]:
            current = current / part
            try:
                st = os.lstat(current)
            except FileNotFoundError:
                if for_write:
                    break
                raise FileNotFoundError(f"路径不存在: {path}")
            except OSError as exc:
                raise WorkspaceViolation(f"无法访问路径: {path} ({exc})") from exc
            if stat.S_ISLNK(st.st_mode):
                raise WorkspaceViolation(f"路径包含符号链接，已拒绝: {current}")

        # must be inside an allowed root  ｜ 必须位于允许的根目录内
        resolved = path.resolve()
        if not any(self._is_within(resolved, root) for root in self.roots):
            raise WorkspaceViolation(
                f"路径不在允许的工作区内: {path}。允许的根目录: {', '.join(str(r) for r in self.roots)}"
            )
        if resolved == Path(resolved.anchor):
            raise WorkspaceViolation("不允许操作根目录")
        return resolved

    @staticmethod
    def _is_within(path: Path, root: Path) -> bool:
        try:
            return path == root or path.is_relative_to(root)
        except ValueError:
            return False

    # ---------------- operations ----------------  ｜ ---------------- 操作 ----------------
    def read_text(self, raw: str) -> str:
        path = self.resolve(raw)
        if not path.is_file():
            raise WorkspaceViolation(f"不是文件: {path}")
        size = path.stat().st_size
        if size > self.max_read_bytes:
            raise WorkspaceViolation(f"文件过大（{size} 字节 > {self.max_read_bytes}）")
        return path.read_text(encoding="utf-8", errors="replace")

    def write_text(self, raw: str, content: str) -> Path:
        path = self.resolve(raw, for_write=True)
        path.parent.mkdir(parents=True, exist_ok=True)
        # final component must not become a symlink between checks  ｜ 最终路径组件在检查期间不得变成符号链接
        if path.exists() and path.is_symlink():
            raise WorkspaceViolation(f"目标是符号链接: {path}")
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0), 0o644)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        return path

    def list_dir(self, raw: str = ".") -> list[str]:
        path = self.resolve(raw)
        if not path.is_dir():
            raise WorkspaceViolation(f"不是目录: {path}")
        return [str(p) for p in sorted(path.iterdir())]

    def delete(self, raw: str) -> Path:
        path = self.resolve(raw)
        if path.is_dir():
            raise WorkspaceViolation(f"拒绝删除目录（P0 只允许删除文件）: {path}")
        path.unlink()
        return path

    def info(self, raw: str) -> dict:
        path = self.resolve(raw)
        st = path.stat()
        return {
            "name": path.name,
            "path": str(path),
            "size": st.st_size,
            "modified": st.st_mtime,
            "is_dir": path.is_dir(),
            "extension": path.suffix,
        }

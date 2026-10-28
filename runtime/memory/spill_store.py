"""
溢出存储模块（SpillStore）
==========================
借鉴 DeepSeek Harness 的 spill 机制（dsh-spill-local + dsh-spill-policy）：
- 超长的工具结果不直接丢弃（现有 pruner 只保留 head/tail，中间段丢失）
- 而是把「完整内容」落盘到会话隔离的 spill 目录
- 模型侧只看到 head/tail 预览 + 定位符（locator），不占上下文
- 用户/前端可通过 locator 按需读取完整内容 —— 数据不丢，上下文不爆

设计要点（对齐 Harness）：
- 会话隔离：文件落在 ``storage/spills/<session_hash>/`` 下
- 路径穿越防护：resolve 时校验路径严格在 spill root 内
- best-effort：落盘失败绝不阻断主流程（返回 None，由调用方降级）
- 与 ToolResultPruner 互补：pruner 负责「省 token」，spill 负责「不丢数据」

用法::

    from runtime.memory.spill_store import SpillStore
    store = SpillStore()
    ref = store.spill(full_text, session_id="sess-abc", tool_name="web_fetch")
    # ref.locator -> "spill://sess-abc/20260824-103000-web_fetch-1a2b3c.txt"
    text = store.resolve(ref)          # 读取完整内容
"""

import hashlib
import os
import re
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

__all__ = ["SpillStore", "SpillRef", "parse_locator"]

# 默认 spill 根目录（相对项目根）
DEFAULT_ROOT = os.path.join("storage", "spills")

# 定位符前缀：spill://<session>/<filename>
LOCATOR_PREFIX = "spill://"

# 会话 id 清洗：只保留安全字符，防止路径穿越
_SAFE_SESSION_RE = re.compile(r"[^A-Za-z0-9._-]+")
# 工具名清洗：只保留安全字符
_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


@dataclass
class SpillRef:
    """一次落盘的结果引用。"""

    locator: str      # 定位符，如 spill://sess-abc/xxx.txt
    bytes: int        # 落盘字节数
    path: str         # 绝对路径（内部用，不暴露给模型）
    retrieval_hint: str = "完整结果已保存，可通过读取该定位符查看全部内容。"


def parse_locator(locator: str) -> Optional[tuple[str, str]]:
    """把 locator 解析为 (session_id, filename)。非法返回 None。"""
    if not locator or not locator.startswith(LOCATOR_PREFIX):
        return None
    rest = locator[len(LOCATOR_PREFIX):]
    if "/" not in rest:
        return None
    session_id, filename = rest.split("/", 1)
    if not session_id or not filename:
        return None
    if "/" in filename or ".." in filename or "\\" in filename:
        return None
    return session_id, filename


class SpillStore:
    """本地文件系统溢出存储。

    - ``spill(text, session_id, tool_name)``：完整落盘，返回 SpillRef
    - ``resolve(locator)``：按定位符读取完整内容（带路径穿越防护）
    - best-effort：spill 失败返回 None，绝不抛错阻断主流程
    """

    def __init__(self, root: str = DEFAULT_ROOT) -> None:
        self.root = os.path.abspath(root)

    # ------------------------------------------------------------------
    # 落盘
    # ------------------------------------------------------------------
    def spill(
        self,
        text: str,
        session_id: str = "default",
        tool_name: str = "tool",
        suggested_name: Optional[str] = None,
    ) -> Optional[SpillRef]:
        """把完整文本写入会话隔离的 spill 文件。

        失败时返回 None（调用方应降级为原始文本，不影响主流程）。
        """
        if not text:
            return None
        try:
            safe_session = _SAFE_SESSION_RE.sub("_", session_id) or "default"
            safe_name = _SAFE_NAME_RE.sub("_", tool_name) or "tool"
            session_dir = os.path.join(self.root, safe_session)
            os.makedirs(session_dir, exist_ok=True)

            # 文件名：时间戳-工具名-内容hash 前8位（防碰撞 + 可读）
            digest = hashlib.sha1(text.encode("utf-8", errors="replace")).hexdigest()[:8]
            ts = time.strftime("%Y%m%d-%H%M%S")
            fname = suggested_name or f"{ts}-{safe_name}-{digest}.txt"
            fname = _SAFE_NAME_RE.sub("_", fname) or f"{ts}-{safe_name}-{digest}.txt"

            full_path = os.path.join(session_dir, fname)
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(text)

            rel = f"{safe_session}/{fname}"
            return SpillRef(
                locator=f"{LOCATOR_PREFIX}{rel}",
                bytes=os.path.getsize(full_path),
                path=full_path,
            )
        except Exception:
            # best-effort：落盘失败不抛错，调用方降级
            return None

    # ------------------------------------------------------------------
    # 读取
    # ------------------------------------------------------------------
    def resolve(self, locator: str) -> Optional[str]:
        """按定位符读取完整内容。非法/不存在/越界返回 None。"""
        parsed = parse_locator(locator)
        if parsed is None:
            return None
        session_id, filename = parsed
        try:
            # 路径穿越防护：规范化后必须仍在 root 内
            root_abs = os.path.abspath(self.root)
            target = os.path.abspath(os.path.join(root_abs, session_id, filename))
            if not target.startswith(root_abs + os.sep):
                return None
            with open(target, "r", encoding="utf-8") as f:
                return f.read()
        except Exception:
            return None

    # ------------------------------------------------------------------
    # 列举 / 清理
    # ------------------------------------------------------------------
    def list_refs(self, session_id: str = "default", limit: int = 20) -> list[str]:
        """列出某会话最近落盘的定位符（按 mtime 倒序）。"""
        safe_session = _SAFE_SESSION_RE.sub("_", session_id) or "default"
        session_dir = os.path.join(self.root, safe_session)
        out: list[str] = []
        try:
            if not os.path.isdir(session_dir):
                return out
            files = [
                (os.path.getmtime(os.path.join(session_dir, f)), f)
                for f in os.listdir(session_dir)
                if f.endswith(".txt")
            ]
            files.sort(reverse=True)
            for _, fname in files[:limit]:
                out.append(f"{LOCATOR_PREFIX}{safe_session}/{fname}")
        except Exception:
            pass
        return out

    def __repr__(self) -> str:
        return f"SpillStore(root={self.root!r})"


# 模块级单例（与 memory_service 风格一致）
_spill_store: Optional[SpillStore] = None


def get_spill_store() -> SpillStore:
    global _spill_store
    if _spill_store is None:
        _spill_store = SpillStore()
    return _spill_store


def reset_spill_store() -> None:
    global _spill_store
    _spill_store = None

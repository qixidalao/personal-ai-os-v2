"""
工具结果裁剪模块（ToolResultPruner）
====================================
确定性、模型无关的超长工具输出裁剪，纯省 token。

思路参考 DeepSeek Harness 的 compaction-tool-result-pruner：
- 超过 threshold_chars 的输出，只保留 head_chars 开头 + tail_chars 结尾
- 中间替换为 PRUNE_MARKER 占位标记
- 不调用 LLM、无副作用、可随时开关

用法::

    pruner = ToolResultPruner()
    compact = pruner.prune(result_str)          # 超过阈值自动裁剪
    compact = pruner.prune(result_str, force=True)  # 强制裁剪
"""

from typing import Optional

__all__ = ["ToolResultPruner", "PRUNE_MARKER"]

# 固定占位标记：被裁剪掉的中间段
PRUNE_MARKER = "\n\n[... tool result middle pruned ...]\n\n"

# 低摩擦默认值（与 dsh 一致）
DEFAULT_THRESHOLD_CHARS = 8192
DEFAULT_HEAD_CHARS = 4096
DEFAULT_TAIL_CHARS = 1024


def code_point_length(text: str) -> int:
    """按 Unicode 码点计数（不拆代理对，中文/emoji 也算 1）。"""
    return len(list(text))


class ToolResultPruner:
    """确定性工具结果裁剪器。"""

    def __init__(
        self,
        threshold_chars: int = DEFAULT_THRESHOLD_CHARS,
        head_chars: int = DEFAULT_HEAD_CHARS,
        tail_chars: int = DEFAULT_TAIL_CHARS,
        enabled: bool = True,
    ) -> None:
        if threshold_chars <= 0:
            raise ValueError("threshold_chars must be positive")
        if head_chars < 0 or tail_chars < 0:
            raise ValueError("head_chars/tail_chars must be non-negative")
        if head_chars + code_point_length(PRUNE_MARKER) + tail_chars > threshold_chars:
            raise ValueError(
                f"head_chars + marker + tail_chars ({head_chars} + "
                f"{code_point_length(PRUNE_MARKER)} + {tail_chars}) must be "
                f"<= threshold_chars ({threshold_chars})"
            )
        self.threshold_chars = threshold_chars
        self.head_chars = head_chars
        self.tail_chars = tail_chars
        self.enabled = enabled

    def prune(self, text: str, force: bool = False) -> str:
        """裁剪超长文本。force=True 时无视 threshold 直接裁到 head+tail。"""
        if not self.enabled:
            return text
        if text is None:
            return ""
        n = code_point_length(text)
        if n <= self.threshold_chars and not force:
            return text
        head = text[: self.head_chars]
        tail = text[-self.tail_chars:] if self.tail_chars > 0 else ""
        return head + PRUNE_MARKER + tail

    def __repr__(self) -> str:
        return (
            f"ToolResultPruner(threshold={self.threshold_chars}, "
            f"head={self.head_chars}, tail={self.tail_chars}, "
            f"enabled={self.enabled})"
        )

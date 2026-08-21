"""
Token 计量模块（TokenMeter）
============================
轻量、零依赖的 token 估算器，为记忆压缩的触发决策提供依据。

不追求与各家 tokenizer 完全一致（那是 tokenizer 的活），
只提供一个足够好的近似，让"该不该压缩"的判断有量化依据。

估算规则（经验值，按字符数折算）：
- 英文/数字/符号: 约 4 字符 ≈ 1 token（chars_per_token=4.0）
- 中文/日文/韩文等 CJK: 约 1 字符 ≈ 1.5~2 token（cjk_per_token=0.6~0.7）
- 综合长文本默认取 1.8~2.5 字符/token 的保守值，避免低估上下文压力

用法::

    meter = TokenMeter()
    tokens = meter.estimate_text("你好 world")          # -> int
    total = meter.estimate_messages(messages)            # 支持 dict / LLMMessage
    pressure = meter.pressure(total, max_tokens=8192)    # -> 0.0 ~ 1.0+
"""

import re
from typing import Any, Dict, List, Sequence

__all__ = ["TokenMeter", "TokenPressure"]

# CJK 统一表意文字区（含扩展）
_CJK_RE = re.compile(
    r"[\u2E80-\u2EFF\u3040-\u30FF\u31C0-\u31EF\u3400-\u4DBF"
    r"\u4E00-\u9FFF\uF900-\uFAFF\uFF00-\uFFEF]"
)


class TokenPressure:
    """一次压缩决策的量化结果。"""

    __slots__ = ("tokens", "max_tokens", "ratio", "should_compact")

    def __init__(self, tokens: int, max_tokens: int, threshold_ratio: float) -> None:
        self.tokens = tokens
        self.max_tokens = max_tokens
        self.ratio = tokens / max_tokens if max_tokens > 0 else 1.0
        self.should_compact = self.ratio >= threshold_ratio

    def __repr__(self) -> str:
        return (
            f"TokenPressure(tokens={self.tokens}, max={self.max_tokens}, "
            f"ratio={self.ratio:.2%}, compact={self.should_compact})"
        )


class TokenMeter:
    """轻量 token 估算器。"""

    def __init__(
        self,
        chars_per_token: float = 4.0,
        cjk_weight: float = 2.2,
        per_message_overhead: int = 4,
    ) -> None:
        self.chars_per_token = chars_per_token
        self.cjk_weight = cjk_weight
        self.per_message_overhead = per_message_overhead

    def estimate_text(self, text: str) -> int:
        """估算单段文本的 token 数（CJK 加权）。"""
        if not text:
            return 0
        cjk = len(_CJK_RE.findall(text))
        other = len(list(text)) - cjk
        return max(1, int(cjk * self.cjk_weight + other / self.chars_per_token))

    def estimate_messages(
        self, messages: Sequence[Any], content_key: str = "content"
    ) -> int:
        """估算一组消息的总 token（含每条消息的开销）。

        messages 元素支持 dict（用 content_key 取正文）或带 .content 的对象。
        """
        total = 0
        for msg in messages:
            if isinstance(msg, dict):
                content = msg.get(content_key, "")
            else:
                content = getattr(msg, content_key, "")
            if isinstance(content, list):
                # OpenAI 多段 content（[{type,text}, ...]）
                parts = []
                for seg in content:
                    if isinstance(seg, dict):
                        parts.append(str(seg.get("text", "")))
                content = "".join(parts)
            total += self.per_message_overhead + self.estimate_text(str(content or ""))
        return total

    def pressure(
        self, messages: Sequence[Any], max_tokens: int, threshold_ratio: float = 0.8
    ) -> TokenPressure:
        """计算上下文压力，给出是否应触发压缩的结论。"""
        tokens = self.estimate_messages(messages)
        return TokenPressure(tokens, max_tokens, threshold_ratio)

    def __repr__(self) -> str:
        return (
            f"TokenMeter(chars_per_token={self.chars_per_token}, "
            f"cjk_weight={self.cjk_weight})"
        )

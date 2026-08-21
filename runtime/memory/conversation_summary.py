"""
对话摘要压缩模块（ConversationSummary）
========================================
动态记忆的核心：上下文压力过高时，把旧对话交给 LLM 生成摘要，
保留最近一小段原文，从而大幅削减历史 token 占用。

设计对应 DeepSeek Harness 的 compaction-basic：
- threshold_ratio: token 压力阈值（默认 0.8，达到 80% 触发）
- retain_ratio: 保留尾部原文比例（默认 0.16，最近的 16% 不压缩）
- max_tokens: 上下文预算（默认 8192）
- provider: 任意带 ``async chat(messages, **kwargs) -> dict`` 的 LLM 提供者

用法::

    from runtime.memory.conversation_summary import ConversationSummary
    summary = ConversationSummary(provider, max_tokens=8192)
    compacted = await summary.maybe_compact(messages)
"""

import json
from typing import Any, Dict, List, Optional

from .token_meter import TokenMeter

__all__ = ["ConversationSummary"]

# 摘要生成提示词：要求保留关键事实，而不是逐条复述
SUMMARY_SYSTEM_PROMPT = (
    "你是对话记忆压缩器。请把以下对话历史压缩成一份简洁、信息密集的摘要，"
    "供后续继续对话使用。要求：\n"
    "1. 保留用户的核心诉求、关键背景、已确认的事实与决定；\n"
    "2. 保留仍未解决或待办的事项；\n"
    "3. 保留重要的代码/配置/数据特征（文件名、关键字段、数值）；\n"
    "4. 丢弃寒暄、重复表达与无关细节；\n"
    "5. 用要点式中文输出，控制在原内容 1/5 长度以内。\n"
)


class ConversationSummary:
    """对话摘要压缩器。"""

    def __init__(
        self,
        provider: Any,
        max_tokens: int = 8192,
        threshold_ratio: float = 0.8,
        retain_ratio: float = 0.16,
        meter: Optional[TokenMeter] = None,
        summary_model: Optional[str] = None,
        enabled: bool = True,
    ) -> None:
        if not (0.0 < threshold_ratio <= 1.0):
            raise ValueError("threshold_ratio must be in (0, 1]")
        if not (0.0 <= retain_ratio < 1.0):
            raise ValueError("retain_ratio must be in [0, 1)")
        self.provider = provider
        self.max_tokens = max_tokens
        self.threshold_ratio = threshold_ratio
        self.retain_ratio = retain_ratio
        self.meter = meter or TokenMeter()
        self.summary_model = summary_model
        self.enabled = enabled

    @property
    def trigger_tokens(self) -> int:
        """触发压缩的 token 门槛。"""
        return int(self.max_tokens * self.threshold_ratio)

    async def maybe_compact(self, messages: List[Any]) -> List[Dict[str, Any]]:
        """压力超标时压缩；否则原样返回。

        messages: 按时间正序的对话消息（dict 或带 .role/.content 的对象）
        返回: 新的消息列表（可能含一个 system 摘要头 + 尾部原文）
        """
        if not self.enabled or not messages:
            return list(messages)

        tokens = self.meter.estimate_messages(messages)
        if tokens < self.trigger_tokens:
            return list(messages)

        # 需要压缩：头部摘要，尾部保留原文
        retain_count = max(1, int(len(messages) * self.retain_ratio))
        history = messages[:-retain_count]
        tail = messages[-retain_count:]

        summary_text = await self._summarize(history)
        if not summary_text:
            # 摘要失败时降级：只丢一半历史，避免丢失全部信息
            return list(messages[len(history) // 2:])

        summary_msg: Dict[str, Any] = {
            "role": "system",
            "content": (
                f"[对话历史摘要（已压缩 {len(history)} 条旧消息，"
                f"原 {tokens} tokens）]\n{summary_text}"
            ),
        }
        return [summary_msg, *tail]

    async def _summarize(self, history: List[Any]) -> str:
        """调用 LLM 生成历史摘要。"""
        rendered = self._render_history(history)
        if not rendered:
            return ""
        try:
            chat_kwargs: Dict[str, Any] = {}
            if self.summary_model:
                chat_kwargs["model"] = self.summary_model
            resp = await self.provider.chat(
                [
                    {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
                    {"role": "user", "content": rendered},
                ],
                **chat_kwargs,
            )
            if isinstance(resp, dict):
                content = resp.get("content") or ""
                if isinstance(content, list):
                    content = "".join(
                        str(seg.get("text", "")) for seg in content if isinstance(seg, dict)
                    )
                return str(content).strip()
            return str(resp).strip()
        except Exception:
            # 摘要失败不阻断主流程，返回空串由调用方降级
            return ""

    @staticmethod
    def _render_history(history: List[Any]) -> str:
        lines: List[str] = []
        for msg in history:
            if isinstance(msg, dict):
                role = msg.get("role", "unknown")
                content = msg.get("content", "")
            else:
                role = getattr(msg, "role", "unknown")
                content = getattr(msg, "content", "")
            if isinstance(content, list):
                content = "".join(
                    str(seg.get("text", "")) for seg in content if isinstance(seg, dict)
                )
            lines.append(f"[{role}] {content}")
        return "\n".join(lines)

    def __repr__(self) -> str:
        return (
            f"ConversationSummary(max={self.max_tokens}, "
            f"threshold={self.threshold_ratio:.0%}, "
            f"retain={self.retain_ratio:.0%}, enabled={self.enabled})"
        )

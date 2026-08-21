"""
记忆自取服务（MemoryService）
==============================
类人脑记忆的核心编排层 —— 动态记忆自取，模型无感。

哲学（区别于"压缩剪裁"那种遗忘式方案）：
- 记忆不是被动压缩历史，而是主动联想：遇到事情，相关记忆自动浮现
- 整个检索/注入过程由系统完成，LLM 不需要调用任何工具去"查记忆"
- 就像人脑：不用刻意翻档案，回忆自己就来了

流程（在每次 LLM 请求前自动执行）:
    用户输入
      → service.recall(query)      # 系统自动向量+关键词联想检索
      → service.build_injection() # 组织成记忆注入块
      → 注入 system 上下文          # LLM 无感，直接"记得"

用法::

    from runtime.memory.memory_service import get_memory_service
    svc = get_memory_service()
    await svc.remember("8月9日部署了端口4000网关", type="long")
    items = await svc.recall("网关部署", top_k=5)
    block = svc.build_injection(items)
"""

import time
import uuid
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from . import MemoryItem
from .long_memory import LongMemory
from .vector_memory import VectorMemory

__all__ = ["MemoryService", "get_memory_service"]

# 注入块的 system 前缀，提示 LLM 这些是"自动回忆起来的记忆"
INJECT_HEADER = (
    "[自动联想记忆] 以下是系统根据当前对话自动回忆出的历史记忆"
    "（非本次对话内容，供参考）："
)


class MemoryService:
    """记忆自取编排服务。"""

    def __init__(
        self,
        config: Optional[Dict] = None,
        embed_fn: Optional[Callable[[List[str]], Any]] = None,
    ) -> None:
        config = config or {}
        self.enabled = bool(config.get("enabled", True))
        self.top_k = int(config.get("top_k", 5))
        self.min_score = float(config.get("min_score", 0.05))
        self.remember_enabled = bool(config.get("remember_enabled", True))
        # 记忆库
        vcfg = dict(config.get("vector_memory", {}))
        vcfg.setdefault("db_path", "storage/sqlite/memory.db")
        lcfg = dict(config.get("long_memory", {}))
        lcfg.setdefault("db_path", "storage/sqlite/long_memory.db")
        self.vector = VectorMemory(vcfg, embed_fn=embed_fn)
        self.long = LongMemory(lcfg)
        self._embed_fn = embed_fn

    # ─── 记住（写入） ────────────────────────────────────────
    async def remember(
        self,
        content: str,
        mtype: str = "long",
        metadata: Optional[Dict] = None,
    ) -> bool:
        """自动存入一条记忆（同时进向量库与长期库）。"""
        if not self.remember_enabled or not content:
            return False
        item = MemoryItem(
            id=f"mem_{uuid.uuid4().hex[:12]}",
            content=content,
            type=mtype,
            metadata=metadata or {},
            timestamp=time.time(),
        )
        ok_v = await self.vector.store(item)
        ok_l = await self.long.store(item)
        return ok_v and ok_l

    # ─── 回忆（检索） ────────────────────────────────────────
    async def recall(self, query: str, top_k: Optional[int] = None) -> List[MemoryItem]:
        """用当前语境联想检索相关记忆（系统自动，模型无感）。"""
        if not self.enabled:
            return []
        k = top_k or self.top_k
        items: Dict[str, MemoryItem] = {}
        # ① 向量语义联想
        for it in await self.vector.retrieve(query, top_k=k):
            if it.score >= self.min_score:
                items[it.id] = it
        # ② 长期库时间线补充（带关键词命中）
        for it in await self.long.retrieve(query, top_k=k):
            if it.id not in items:
                items[it.id] = it
        ranked = sorted(items.values(), key=lambda x: x.score, reverse=True)
        return ranked[:k]

    # ─── 注入块 ──────────────────────────────────────────────
    def build_injection(self, items: List[MemoryItem]) -> str:
        """把检索到的记忆组织成注入上下文块（无记忆时返回空串）。"""
        if not items:
            return ""
        lines = [INJECT_HEADER]
        for it in items[: self.top_k]:
            ts = datetime.fromtimestamp(it.timestamp).strftime("%Y-%m-%d %H:%M")
            score = f" (相关度{it.score:.2f})" if it.score else ""
            lines.append(f"- [{ts}][{it.type}]{score} {it.content}")
        return "\n".join(lines)

    # ─── 对话自动记忆（可选：抽重要内容入库） ─────────────────
    def _extract_notable(self, user_text: str) -> Optional[str]:
        """轻量规则：抽出用户话语里值得长期记住的内容（偏好/事实/重要声明）。"""
        text = user_text.strip()
        if not text:
            return None
        markers = (
            "我喜欢", "我不喜欢", "我需要", "我要", "我是",
            "我的", "我住在", "我在用", "我常用的", "记住",
            "别忘", "以后", "每次", "一定要", "千万",
        )
        if any(m in text for m in markers):
            return text[:200]
        return None

    async def auto_remember(self, user_text: str) -> bool:
        """对用户输入做轻量记忆：命中偏好/事实标记时自动入库。"""
        notable = self._extract_notable(user_text)
        if notable:
            return await self.remember(
                notable, mtype="fact", metadata={"source": "auto"}
            )
        return False

    def __repr__(self) -> str:
        return (
            f"MemoryService(enabled={self.enabled}, top_k={self.top_k}, "
            f"vector={self.vector.count()}, long={self.long.count()})"
        )


# ─── 全局单例（供后端无感接入） ──────────────────────────────
_service: Optional[MemoryService] = None


def get_memory_service(
    config: Optional[Dict] = None,
    embed_fn: Optional[Callable[[List[str]], Any]] = None,
) -> MemoryService:
    """获取记忆自取服务单例。

    config 缺省时尝试读取 config/memory.yaml（失败则用内置默认）。
    """
    global _service
    if _service is None:
        cfg: Dict = {}
        try:
            import yaml

            from pathlib import Path

            p = Path("config/memory.yaml")
            if p.exists():
                loaded = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
                cfg = loaded.get("memory", loaded)
        except Exception:
            pass
        _service = MemoryService(cfg, embed_fn=embed_fn)
    return _service


def reset_memory_service() -> None:
    """重置单例（测试用）。"""
    global _service
    _service = None

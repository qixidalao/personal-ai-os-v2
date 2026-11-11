"""
runtime.runs — Run / ToolCall 状态与审计存储（P0）。

对外只暴露 :class:`RunStore` 及状态常量 / 序列化小工具：

    from runtime.runs import RunStore

    store = RunStore()  # 默认 storage/runs.db（WAL）

模块本身不依赖 backend / FastAPI，可被 core、SSE 生成器与测试直接复用。
"""

from .store import (
    DEFAULT_DB_PATH,
    DEFAULT_RUN_LIMIT,
    INTERRUPTED_ERROR,
    MAX_RUN_LIMIT,
    RUN_STATUSES,
    RUN_TERMINAL_STATUSES,
    TOOL_CALL_ACTIVE_STATUSES,
    TOOL_CALL_STATUSES,
    TOOL_CALL_TERMINAL_STATUSES,
    RunStore,
    args_hash,
    canonical_json,
    get_run_store,
    reset_run_store,
    utc_now_iso,
)

__all__ = [
    "DEFAULT_DB_PATH",
    "DEFAULT_RUN_LIMIT",
    "INTERRUPTED_ERROR",
    "MAX_RUN_LIMIT",
    "RUN_STATUSES",
    "RUN_TERMINAL_STATUSES",
    "TOOL_CALL_ACTIVE_STATUSES",
    "TOOL_CALL_STATUSES",
    "TOOL_CALL_TERMINAL_STATUSES",
    "RunStore",
    "args_hash",
    "canonical_json",
    "get_run_store",
    "reset_run_store",
    "utc_now_iso",
]

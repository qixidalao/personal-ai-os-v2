"""
Personal AI OS — Run / ToolCall 状态与审计存储
=============================================

P0 目标：工具调用从「只有 SSE 瞬时事件」升级为「可持久、可审计的状态」。
SSE 断开 / 服务重启后，仍能回答：这次 run 是否执行过？某个 tool call 到哪一步了？

设计要点
--------
- SQLite 单文件（默认 ``storage/runs.db``），WAL 日志模式，``check_same_thread=False``，
  所有读写串行化在 ``threading.Lock`` 后 —— FastAPI 线程池 / 工具线程可安全共用同一实例。
- 时间统一 UTC ISO8601（毫秒精度、``Z`` 后缀）；JSON 一律 ``ensure_ascii=False``。
- ``args_hash = sha256(规范 JSON(sort_keys, 紧凑分隔符))``，同参数不同 key 顺序得到同一 hash。
- 状态机（详见 notes-p0-runs.md）::

      run:       running → succeeded | failed | cancelled | unknown
      tool_call: prepared → dispatched → succeeded | failed | cancelled | unknown

- 服务启动时调用 ``mark_interrupted_runs()``，把上次进程残留的 ``running`` / 未收尾
  tool call 标为 ``unknown``，并写入 ``run.interrupted`` / ``tool_call.interrupted`` 审计事件。

本模块只依赖标准库，不依赖 backend / FastAPI，可被 core 代码与测试独立使用。
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

__all__ = [
    "DEFAULT_DB_PATH",
    "DEFAULT_RUN_LIMIT",
    "MAX_RUN_LIMIT",
    "RUN_STATUSES",
    "RUN_TERMINAL_STATUSES",
    "TOOL_CALL_STATUSES",
    "TOOL_CALL_TERMINAL_STATUSES",
    "TOOL_CALL_ACTIVE_STATUSES",
    "RunStore",
    "args_hash",
    "canonical_json",
    "get_run_store",
    "reset_run_store",
    "utc_now_iso",
]

DEFAULT_DB_PATH = "storage/runs.db"
DEFAULT_RUN_LIMIT = 50
MAX_RUN_LIMIT = 1000

RUN_STATUSES = frozenset({"running", "succeeded", "failed", "cancelled", "unknown"})
RUN_TERMINAL_STATUSES = frozenset({"succeeded", "failed", "cancelled", "unknown"})

TOOL_CALL_STATUSES = frozenset({"prepared", "dispatched", "succeeded", "failed", "cancelled", "unknown"})
TOOL_CALL_TERMINAL_STATUSES = frozenset({"succeeded", "failed", "cancelled", "unknown"})
TOOL_CALL_ACTIVE_STATUSES = frozenset({"prepared", "dispatched"})

INTERRUPTED_ERROR = "interrupted: server restarted"

_SCHEMA: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS runs (
        id          TEXT PRIMARY KEY,
        session_id  TEXT,
        model       TEXT,
        status      TEXT NOT NULL,
        started_at  TEXT NOT NULL,
        finished_at TEXT,
        error       TEXT,
        meta        TEXT NOT NULL DEFAULT '{}'
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_runs_session ON runs(session_id, started_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_runs_status ON runs(status)",
    "CREATE INDEX IF NOT EXISTS idx_runs_started ON runs(started_at DESC)",
    """
    CREATE TABLE IF NOT EXISTS tool_calls (
        id                  TEXT PRIMARY KEY,
        run_id              TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
        name                TEXT NOT NULL,
        args_json           TEXT NOT NULL DEFAULT '{}',
        args_hash           TEXT NOT NULL,
        status              TEXT NOT NULL,
        permission_decision TEXT NOT NULL DEFAULT 'allow',
        started_at          TEXT NOT NULL,
        finished_at         TEXT,
        error               TEXT,
        output_bytes        INTEGER
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_tool_calls_run ON tool_calls(run_id)",
    "CREATE INDEX IF NOT EXISTS idx_tool_calls_status ON tool_calls(status)",
    "CREATE INDEX IF NOT EXISTS idx_tool_calls_hash ON tool_calls(args_hash)",
    """
    CREATE TABLE IF NOT EXISTS events (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id    TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
        seq       INTEGER NOT NULL,
        type      TEXT NOT NULL,
        data_json TEXT NOT NULL DEFAULT '{}',
        ts        TEXT NOT NULL,
        UNIQUE(run_id, seq)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_events_run_seq ON events(run_id, seq)",
)


# ---------------------------------------------------------------------------
# 时间 / JSON 工具
# ---------------------------------------------------------------------------
def utc_now_iso() -> str:
    """当前 UTC 时间：ISO8601、毫秒精度、``Z`` 后缀（例：``2026-11-11T04:57:12.345Z``）。"""
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _normalize_args(args: Any) -> Any:
    """把 tool 参数统一成可 JSON 化的对象：None→{}；JSON 字符串→解析后的对象。"""
    if args is None:
        return {}
    if isinstance(args, bytes):
        try:
            args = args.decode("utf-8")
        except UnicodeDecodeError:
            return repr(args)
    if isinstance(args, str):
        try:
            return json.loads(args)
        except (json.JSONDecodeError, TypeError):
            return args
    return args


def canonical_json(value: Any) -> str:
    """规范化 JSON：key 排序、紧凑分隔符、中文不转义 —— 保证同参数同 hash。"""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def args_hash(args: Any) -> str:
    """``sha256(规范 JSON(args))`` 的十六进制摘要，用于参数去重与审计对照。"""
    return hashlib.sha256(canonical_json(_normalize_args(args)).encode("utf-8")).hexdigest()


def _dumps(value: Any) -> str:
    return json.dumps({} if value is None else value, ensure_ascii=False, default=str)


def _loads(raw: Any, default: Any = None) -> Any:
    if raw is None or raw == "":
        return default
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return raw


class RunStore:
    """Run / ToolCall 审计存储（SQLite + 进程内锁，线程安全）。

    用法::

        store = RunStore()                       # → storage/runs.db
        store = RunStore(tmp_path / "runs.db")   # 测试 / 多实例
        store.create_run("run_abc", "sess_1", "gpt-4o")
        store.create_tool_call("call_1", "run_abc", "shell", {"cmd": "ls"})
        store.update_tool_call("call_1", "dispatched")
        store.update_tool_call("call_1", "succeeded", output_bytes=42)
        store.finish_run("run_abc", "succeeded")
        store.get_run("run_abc")                 # → {run, tool_calls, events}
    """

    def __init__(self, path: str | Path | None = None) -> None:
        raw = str(path) if path is not None else DEFAULT_DB_PATH
        self.path: Path | None = Path(raw) if raw != ":memory:" else None
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn: sqlite3.Connection | None = sqlite3.connect(
            raw, check_same_thread=False, timeout=30.0
        )
        self._conn.row_factory = sqlite3.Row
        try:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
            self._conn.execute("PRAGMA busy_timeout=5000")
            self._init_schema()
        except Exception:
            conn = self._conn
            self._conn = None
            if conn is not None:
                conn.close()
            raise

    # ---------------- 连接与 schema ----------------
    def _init_schema(self) -> None:
        with self._lock, self._require_conn() as conn:
            for statement in _SCHEMA:
                conn.execute(statement)

    def _require_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("RunStore is closed")
        return self._conn

    def close(self) -> None:
        """关闭底层连接（幂等）。"""
        with self._lock:
            conn, self._conn = self._conn, None
            if conn is not None:
                try:
                    conn.close()
                except Exception:  # pragma: no cover - close 失败不影响调用方
                    pass

    def __enter__(self) -> "RunStore":
        return self

    def __exit__(self, *exc_info: Any) -> None:
        self.close()

    def __repr__(self) -> str:  # pragma: no cover - 调试用
        return f"RunStore(path={self.path!r})"

    # ---------------- 状态校验 / 行转换 ----------------
    @staticmethod
    def _check_run_status(status: str) -> str:
        if status not in RUN_STATUSES:
            raise ValueError(f"invalid run status: {status!r}; allowed={sorted(RUN_STATUSES)}")
        return status

    @staticmethod
    def _check_terminal_run_status(status: str) -> str:
        if status not in RUN_TERMINAL_STATUSES:
            raise ValueError(
                f"invalid terminal run status: {status!r}; "
                f"allowed={sorted(RUN_TERMINAL_STATUSES)}"
            )
        return status

    @staticmethod
    def _check_tool_status(status: str) -> str:
        if status not in TOOL_CALL_STATUSES:
            raise ValueError(f"invalid tool_call status: {status!r}; allowed={sorted(TOOL_CALL_STATUSES)}")
        return status

    @staticmethod
    def _now() -> str:
        return utc_now_iso()

    @staticmethod
    def _run_row(row: sqlite3.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None
        data = dict(row)
        data["meta"] = _loads(data.get("meta"), {})
        return data

    @staticmethod
    def _tool_row(row: sqlite3.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None
        data = dict(row)
        data["args"] = _loads(data.pop("args_json", None), {})
        return data

    @staticmethod
    def _event_row(row: sqlite3.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None
        data = dict(row)
        data["data"] = _loads(data.pop("data_json", None), {})
        return data

    # ---------------- run 生命周期 ----------------
    def create_run(
        self,
        run_id: str,
        session_id: str | None = None,
        model: str | None = None,
        meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """登记一次 run（状态 ``running``）并返回 run dict；重复 id 抛 ``ValueError``。"""
        if not isinstance(run_id, str) or not run_id:
            raise ValueError("run_id must be a non-empty string")
        started_at = self._now()
        with self._lock, self._require_conn() as conn:
            try:
                conn.execute(
                    """
                    INSERT INTO runs (id, session_id, model, status, started_at, finished_at, error, meta)
                    VALUES (?, ?, ?, 'running', ?, NULL, NULL, ?)
                    """,
                    (run_id, session_id, model, started_at, _dumps(meta or {})),
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError(f"run already exists: {run_id}") from exc
            row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        return self._run_row(row)  # type: ignore[return-value]

    def finish_run(
        self,
        run_id: str,
        status: str,
        error: str | None = None,
    ) -> dict[str, Any] | None:
        """把 run 落到终态并返回 run dict；run 不存在返回 ``None``。

        - ``status`` 必须是 ``succeeded / failed / cancelled / unknown``。
        - 幂等：首次终态生效，重复调用不会覆盖既有 ``status / finished_at``
          （避免「取消」与「正常结束」竞争时互相改写）；``error`` 为 ``None`` 时保留原值。
        """
        self._check_terminal_run_status(status)
        finished_at = self._now()
        with self._lock, self._require_conn() as conn:
            conn.execute(
                """
                UPDATE runs
                   SET status = ?, finished_at = ?, error = COALESCE(?, error)
                 WHERE id = ? AND status = 'running'
                """,
                (status, finished_at, error, run_id),
            )
            row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        return self._run_row(row)

    # ---------------- tool call 生命周期 ----------------
    def create_tool_call(
        self,
        call_id: str,
        run_id: str,
        name: str,
        args: Any = None,
        permission: str = "allow",
        status: str = "prepared",
    ) -> dict[str, Any]:
        """登记一次工具调用（默认 ``prepared``）并返回 tool call dict。

        - ``args`` 可为 dict / JSON 字符串 / None，落库为规范 JSON；
        - ``args_hash = sha256(规范 JSON(args))``；
        - run 不存在或 call_id 重复时抛 ``ValueError``。
        """
        self._check_tool_status(status)
        if not isinstance(call_id, str) or not call_id:
            raise ValueError("call_id must be a non-empty string")
        if not isinstance(name, str) or not name:
            raise ValueError("tool name must be a non-empty string")
        if args is None:
            args = {}
        canonical_args = canonical_json(_normalize_args(args))
        digest = hashlib.sha256(canonical_args.encode("utf-8")).hexdigest()
        started_at = self._now()
        finished_at = self._now() if status in TOOL_CALL_TERMINAL_STATUSES else None
        with self._lock, self._require_conn() as conn:
            if conn.execute("SELECT 1 FROM runs WHERE id = ?", (run_id,)).fetchone() is None:
                raise ValueError(f"run not found: {run_id}")
            try:
                conn.execute(
                    """
                    INSERT INTO tool_calls (
                        id, run_id, name, args_json, args_hash, status,
                        permission_decision, started_at, finished_at, error, output_bytes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL)
                    """,
                    (
                        call_id,
                        run_id,
                        name,
                        canonical_args,
                        digest,
                        status,
                        permission,
                        started_at,
                        finished_at,
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError(f"tool call already exists: {call_id}") from exc
            row = conn.execute("SELECT * FROM tool_calls WHERE id = ?", (call_id,)).fetchone()
        return self._tool_row(row)  # type: ignore[return-value]

    def update_tool_call(
        self,
        call_id: str,
        status: str,
        error: str | None = None,
        output_bytes: int | None = None,
        permission: str | None = None,
    ) -> dict[str, Any] | None:
        """更新 tool call 状态；不存在返回 ``None``。

        - 进入终态（succeeded/failed/cancelled/unknown）时写入 ``finished_at``（只写一次）；
        - ``error`` / ``output_bytes`` 为 ``None`` 时保留旧值。
        """
        self._check_tool_status(status)
        if output_bytes is not None:
            if not isinstance(output_bytes, int) or isinstance(output_bytes, bool):
                raise ValueError("output_bytes must be an int")
            if output_bytes < 0:
                raise ValueError("output_bytes must be >= 0")
        finished_at = self._now() if status in TOOL_CALL_TERMINAL_STATUSES else None
        with self._lock, self._require_conn() as conn:
            cursor = conn.execute(
                """
                UPDATE tool_calls
                   SET status = ?,
                       error = COALESCE(?, error),
                       output_bytes = COALESCE(?, output_bytes),
                       permission_decision = COALESCE(?, permission_decision),
                       finished_at = COALESCE(?, finished_at)
                 WHERE id = ?
                """,
                (status, error, output_bytes, permission, finished_at, call_id),
            )
            if cursor.rowcount == 0:
                return None
            row = conn.execute("SELECT * FROM tool_calls WHERE id = ?", (call_id,)).fetchone()
        return self._tool_row(row)

    # ---------------- 事件流 ----------------
    def _next_seq_locked(self, conn: sqlite3.Connection, run_id: str) -> int:
        row = conn.execute(
            "SELECT COALESCE(MAX(seq), 0) FROM events WHERE run_id = ?", (run_id,)
        ).fetchone()
        return int(row[0]) + 1

    def _insert_event_locked(
        self, conn: sqlite3.Connection, run_id: str, event_type: str, data: Any
    ) -> int:
        seq = self._next_seq_locked(conn, run_id)
        conn.execute(
            "INSERT INTO events (run_id, seq, type, data_json, ts) VALUES (?, ?, ?, ?, ?)",
            (run_id, seq, event_type, _dumps(data), self._now()),
        )
        return seq

    def next_seq(self, run_id: str) -> int:
        """预读下一个事件序号（只读，不落库）；run 不存在抛 ``ValueError``。"""
        with self._lock, self._require_conn() as conn:
            if conn.execute("SELECT 1 FROM runs WHERE id = ?", (run_id,)).fetchone() is None:
                raise ValueError(f"run not found: {run_id}")
            return self._next_seq_locked(conn, run_id)

    def add_event(self, run_id: str, type: str, data: Any = None) -> int:
        """追加一条审计事件，返回其在 run 内单调递增的 ``seq``；run 不存在抛 ``ValueError``。"""
        if not isinstance(type, str) or not type:
            raise ValueError("event type must be a non-empty string")
        with self._lock, self._require_conn() as conn:
            if conn.execute("SELECT 1 FROM runs WHERE id = ?", (run_id,)).fetchone() is None:
                raise ValueError(f"run not found: {run_id}")
            return self._insert_event_locked(conn, run_id, type, data or {})

    # ---------------- 查询 ----------------
    def get_run(self, run_id: str) -> dict[str, Any] | None:
        """返回 ``{run, tool_calls, events}``；不存在返回 ``None``。"""
        with self._lock:
            conn = self._require_conn()
            run_row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
            if run_row is None:
                return None
            tool_rows = conn.execute(
                "SELECT * FROM tool_calls WHERE run_id = ? ORDER BY started_at ASC, id ASC",
                (run_id,),
            ).fetchall()
            event_rows = conn.execute(
                "SELECT * FROM events WHERE run_id = ? ORDER BY seq ASC", (run_id,)
            ).fetchall()
        return {
            "run": self._run_row(run_row),
            "tool_calls": [self._tool_row(row) for row in tool_rows],
            "events": [self._event_row(row) for row in event_rows],
        }

    def list_runs(self, session_id: str | None = None, limit: int = DEFAULT_RUN_LIMIT,
                  offset: int = 0) -> list[dict[str, Any]]:
        """按 ``started_at`` 倒序列出 run（不含 tool_calls/events），可按会话过滤分页。"""
        sql = "SELECT * FROM runs"
        params: list[Any] = []
        if session_id is not None:
            sql += " WHERE session_id = ?"
            params.append(session_id)
        sql += " ORDER BY started_at DESC, id DESC LIMIT ? OFFSET ?"
        normalized_limit = max(1, min(int(limit or DEFAULT_RUN_LIMIT), MAX_RUN_LIMIT))
        normalized_offset = max(0, int(offset or 0))
        params.extend([normalized_limit, normalized_offset])
        with self._lock:
            rows = self._require_conn().execute(sql, params).fetchall()
        return [self._run_row(row) for row in rows]  # type: ignore[misc]

    def count_runs(self, session_id: str | None = None) -> int:
        """返回 run 总数（可按会话过滤）。"""
        sql = "SELECT COUNT(*) FROM runs"
        params: list[Any] = []
        if session_id is not None:
            sql += " WHERE session_id = ?"
            params.append(session_id)
        with self._lock:
            row = self._require_conn().execute(sql, params).fetchone()
        return int(row[0]) if row else 0

    def list_events(self, run_id: str, after_seq: int = 0) -> list[dict[str, Any]]:
        """按 ``seq`` 升序返回事件；``after_seq`` 用于增量拉取（seq > after_seq）。"""
        threshold = max(0, int(after_seq or 0))
        with self._lock:
            rows = self._require_conn().execute(
                "SELECT * FROM events WHERE run_id = ? AND seq > ? ORDER BY seq ASC",
                (run_id, threshold),
            ).fetchall()
        return [self._event_row(row) for row in rows]  # type: ignore[misc]

    # ---------------- 启动恢复 ----------------
    def mark_interrupted_runs(self, now: str | None = None) -> int:
        """把残留的 ``running`` run 标为 ``unknown``（服务重启后调用），返回处理的 run 数。

        同时把这些 run 下仍处于 ``prepared / dispatched`` 的 tool call 标为 ``unknown``，
        并为每个 run / tool call 写一条审计事件（``run.interrupted`` /
        ``tool_call.interrupted``），从而证明「这次调用被中断、结果未知」而非「成功」。
        """
        timestamp = now or self._now()
        with self._lock, self._require_conn() as conn:
            running_rows = conn.execute("SELECT id FROM runs WHERE status = 'running'").fetchall()
            for row in running_rows:
                run_id = row["id"]
                active_calls = conn.execute(
                    "SELECT id, name FROM tool_calls WHERE run_id = ? AND status IN ('prepared', 'dispatched')",
                    (run_id,),
                ).fetchall()
                conn.execute(
                    """
                    UPDATE runs
                       SET status = 'unknown', finished_at = ?, error = COALESCE(error, ?)
                     WHERE id = ?
                    """,
                    (timestamp, INTERRUPTED_ERROR, run_id),
                )
                conn.execute(
                    """
                    UPDATE tool_calls
                       SET status = 'unknown',
                           finished_at = COALESCE(finished_at, ?),
                           error = COALESCE(error, ?)
                     WHERE run_id = ? AND status IN ('prepared', 'dispatched')
                    """,
                    (timestamp, INTERRUPTED_ERROR, run_id),
                )
                self._insert_event_locked(
                    conn,
                    run_id,
                    "run_interrupted",
                    {
                        "previous_status": "running",
                        "status": "unknown",
                        "reason": "server_restart",
                    },
                )
                for call in active_calls:
                    self._insert_event_locked(
                        conn,
                        run_id,
                        "tool_call_interrupted",
                        {
                            "tool_call_id": call["id"],
                            "name": call["name"],
                            "status": "unknown",
                            "reason": "server_restart",
                        },
                    )
            return len(running_rows)


# ---------------------------------------------------------------------------
# 进程内默认单例（供 backend / lifecycle 直接复用，避免多实例双连接写同一 DB）
# ---------------------------------------------------------------------------
_default_store: RunStore | None = None
_default_store_lock = threading.Lock()


def get_run_store(path: str | Path | None = None) -> RunStore:
    """进程内默认 :class:`RunStore` 单例（懒创建、线程安全）。

    ``backend/chat_api.py`` / ``backend/runs_api.py`` / lifespan 应共用本函数，
    这样 API 查询与写入走同一连接、同一把锁。首次调用的 ``path`` 决定 DB 位置。

    测试请直接实例化 ``RunStore(tmp_path / "runs.db")``，不要用本单例。
    """
    global _default_store
    if _default_store is None:
        with _default_store_lock:
            if _default_store is None:
                _default_store = RunStore(path)
    return _default_store


def reset_run_store() -> None:
    """关闭并丢弃默认单例（测试 / 进程重启模拟用）。"""
    global _default_store
    with _default_store_lock:
        store, _default_store = _default_store, None
        if store is not None:
            store.close()

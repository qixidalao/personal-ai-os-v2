"""Approval store with session-scoped grants (P2)."""
# 中文：带会话范围授权的审批存储（P2）。
from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

DEFAULT_DB_PATH = "storage/approvals.db"
DEFAULT_TIMEOUT = 120

_SCHEMA = (
    """
    CREATE TABLE IF NOT EXISTS approvals (
        id           TEXT PRIMARY KEY,
        session_id   TEXT,
        run_id       TEXT NOT NULL,
        tool_call_id TEXT NOT NULL,
        tool         TEXT NOT NULL,
        args_json    TEXT NOT NULL DEFAULT '{}',
        args_hash    TEXT NOT NULL,
        risk         TEXT NOT NULL DEFAULT 'medium',
        status       TEXT NOT NULL DEFAULT 'pending',
        created_at   TEXT NOT NULL,
        expires_at   TEXT,
        decided_at   TEXT,
        decided_by   TEXT,
        reason       TEXT
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_approvals_run ON approvals(run_id)",
    "CREATE INDEX IF NOT EXISTS idx_approvals_status ON approvals(status)",
    """
    CREATE TABLE IF NOT EXISTS session_grants (
        session_id TEXT NOT NULL,
        tool       TEXT NOT NULL,
        run_id     TEXT,
        granted_at TEXT NOT NULL,
        PRIMARY KEY (session_id, tool)
    )
    """,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso(value: datetime) -> str:
    return value.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def canonical_json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def args_hash(args) -> str:
    return hashlib.sha256(canonical_json(args).encode("utf-8")).hexdigest()


class ApprovalStore:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path or DEFAULT_DB_PATH)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False, timeout=30)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA busy_timeout=5000")
            for stmt in _SCHEMA:
                self._conn.execute(stmt)
            cols = {row[1] for row in self._conn.execute("PRAGMA table_info(approvals)")}
            if "session_id" not in cols:
                self._conn.execute("ALTER TABLE approvals ADD COLUMN session_id TEXT")
            self._conn.commit()

    def _row(self, row: sqlite3.Row | None) -> dict | None:
        return dict(row) if row else None

    def create(self, run_id: str, tool_call_id: str, tool: str, args: dict,
               risk: str = "medium", timeout_s: int = DEFAULT_TIMEOUT,
               session_id: str | None = None) -> dict:
        now = utc_now()
        record = {
            "id": f"apv_{uuid.uuid4().hex[:12]}",
            "session_id": session_id,
            "run_id": run_id,
            "tool_call_id": tool_call_id,
            "tool": tool,
            "args_json": canonical_json(args),
            "args_hash": args_hash(args),
            "risk": risk,
            "status": "pending",
            "created_at": iso(now),
            "expires_at": iso(now + timedelta(seconds=max(5, int(timeout_s)))),
            "decided_at": None,
            "decided_by": None,
            "reason": None,
        }
        with self._lock:
            self._conn.execute(
                "INSERT INTO approvals (id, session_id, run_id, tool_call_id, tool, args_json, args_hash, risk, "
                "status, created_at, expires_at, decided_at, decided_by, reason) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (record["id"], session_id, run_id, tool_call_id, tool, record["args_json"], record["args_hash"],
                 risk, "pending", record["created_at"], record["expires_at"], None, None, None),
            )
            self._conn.commit()
        return record

    def get(self, approval_id: str) -> dict | None:
        with self._lock:
            row = self._conn.execute("SELECT * FROM approvals WHERE id=?", (approval_id,)).fetchone()
        record = self._row(row)
        if record and record["status"] == "pending" and self._is_expired(record):
            self.expire_stale()
            record["status"] = "expired"
        return record

    @staticmethod
    def _is_expired(record: dict) -> bool:
        try:
            expires = datetime.fromisoformat(record["expires_at"].replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return False
        return utc_now() > expires

    def decide(self, approval_id: str, decision: str, decided_by: str = "user", reason: str | None = None) -> dict | None:
        decision = "approved" if decision in ("approve", "approved") else "denied"
        now = utc_now()
        with self._lock:
            row = self._conn.execute("SELECT * FROM approvals WHERE id=?", (approval_id,)).fetchone()
            record = self._row(row)
            if not record:
                return None
            if record["status"] != "pending":
                return record
            if self._is_expired(record):
                self._conn.execute(
                    "UPDATE approvals SET status='expired', decided_at=?, decided_by='system' WHERE id=? AND status='pending'",
                    (iso(now), approval_id),
                )
                self._conn.commit()
                record["status"] = "expired"
                return record
            self._conn.execute(
                "UPDATE approvals SET status=?, decided_at=?, decided_by=?, reason=? WHERE id=? AND status='pending'",
                (decision, iso(now), decided_by, reason, approval_id),
            )
            self._conn.commit()
            row = self._conn.execute("SELECT * FROM approvals WHERE id=?", (approval_id,)).fetchone()
        return self._row(row)

    def expire_stale(self) -> int:
        now = utc_now()
        with self._lock:
            rows = self._conn.execute("SELECT id, expires_at FROM approvals WHERE status='pending'").fetchall()
            expired = []
            for row in rows:
                try:
                    expires = datetime.fromisoformat(row["expires_at"].replace("Z", "+00:00"))
                except (TypeError, ValueError):
                    continue
                if now > expires:
                    expired.append(row["id"])
            for approval_id in expired:
                self._conn.execute(
                    "UPDATE approvals SET status='expired', decided_at=?, decided_by='system' WHERE id=? AND status='pending'",
                    (iso(now), approval_id),
                )
            self._conn.commit()
        return len(expired)

    def list_pending(self, limit: int = 50) -> list[dict]:
        self.expire_stale()
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM approvals WHERE status='pending' ORDER BY created_at DESC LIMIT ?", (int(limit),)
            ).fetchall()
        return [dict(r) for r in rows]

    def list_by_session(self, session_id: str) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM approvals WHERE session_id=? ORDER BY created_at DESC", (session_id,)
            ).fetchall()
        return [dict(r) for r in rows]

    def list_by_run(self, run_id: str) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM approvals WHERE run_id=? ORDER BY created_at ASC", (run_id,)
            ).fetchall()
        return [dict(r) for r in rows]

    # ---------------- session grants ----------------  ｜ ---------------- 会话授权 ----------------
    def add_grant(self, session_id: str, tool: str, run_id: str | None = None) -> None:
        if not session_id:
            return
        with self._lock:
            self._conn.execute(
                "INSERT INTO session_grants (session_id, tool, run_id, granted_at) VALUES (?,?,?,?) "
                "ON CONFLICT(session_id, tool) DO UPDATE SET run_id=excluded.run_id, granted_at=excluded.granted_at",
                (session_id, tool, run_id, iso(utc_now())),
            )
            self._conn.commit()

    def has_grant(self, session_id: str | None, tool: str) -> bool:
        if not session_id:
            return False
        with self._lock:
            row = self._conn.execute(
                "SELECT 1 FROM session_grants WHERE session_id=? AND tool=? LIMIT 1", (session_id, tool)
            ).fetchone()
        return row is not None

    def list_grants(self, session_id: str) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM session_grants WHERE session_id=? ORDER BY granted_at DESC", (session_id,)
            ).fetchall()
        return [dict(r) for r in rows]

    def revoke_grant(self, session_id: str, tool: str) -> bool:
        with self._lock:
            cur = self._conn.execute(
                "DELETE FROM session_grants WHERE session_id=? AND tool=?", (session_id, tool)
            )
            self._conn.commit()
        return cur.rowcount > 0

    def consume(self, approval_id: str) -> bool:
        """Mark an approved record as consumed (single execution)."""
        # 中文：将已批准记录标记为已消耗（仅执行一次）。
        with self._lock:
            cur = self._conn.execute(
                "UPDATE approvals SET status='consumed' WHERE id=? AND status='approved'", (approval_id,)
            )
            self._conn.commit()
        return cur.rowcount > 0

    def list_all_grants(self) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM session_grants ORDER BY granted_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def close(self) -> None:
        with self._lock:
            self._conn.close()


_store: ApprovalStore | None = None
_store_lock = threading.Lock()


def get_approval_store(path: str | Path | None = None) -> ApprovalStore:
    global _store
    if _store is None or path is not None:
        with _store_lock:
            if _store is None or path is not None:
                _store = ApprovalStore(path)
    return _store

"""P3 tests: approval consumption, grants listing, policy reuse guards."""
# 中文：P3 测试：审批消费、授权列表、策略复用保护。
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from runtime.approvals import ApprovalStore  # noqa: E402
from runtime.approvals.store import args_hash  # noqa: E402


@pytest.fixture()
def store(tmp_path):
    s = ApprovalStore(tmp_path / "approvals.db")
    yield s
    s.close()


def test_consume_only_approved(store):
    rec = store.create("run-1", "call-1", "shell_exec", {"command": "echo hi"}, timeout_s=60)
    assert store.consume(rec["id"]) is False  # 还没批准
    store.decide(rec["id"], "approve")
    assert store.consume(rec["id"]) is True
    assert store.get(rec["id"])["status"] == "consumed"
    assert store.consume(rec["id"]) is False  # 只能消费一次


def test_list_all_grants(store):
    store.add_grant("sess-a", "shell_exec", run_id="run-1")
    store.add_grant("sess-b", "write_file", run_id="run-2")
    grants = store.list_all_grants()
    assert len(grants) == 2
    pairs = {(g["session_id"], g["tool"]) for g in grants}
    assert ("sess-a", "shell_exec") in pairs


def test_args_hash_matches_approval(store):
    rec = store.create("run-1", "call-1", "write_file", {"path": "a.txt", "content": "x"}, timeout_s=60)
    assert rec["args_hash"] == args_hash({"path": "a.txt", "content": "x"})
    # 参数变体（key 顺序不同）应得到同一 hash
    assert args_hash({"content": "x", "path": "a.txt"}) == rec["args_hash"]


def test_approval_session_binding(store):
    rec = store.create("run-1", "call-1", "shell_exec", {"command": "ls"}, session_id="sess-1", timeout_s=60)
    assert rec["session_id"] == "sess-1"
    store.decide(rec["id"], "approve")
    store.add_grant(rec["session_id"], rec["tool"], rec["run_id"])
    assert store.has_grant("sess-1", "shell_exec")


def test_expired_cannot_be_consumed(store):
    rec = store.create("run-1", "call-1", "shell_exec", {"command": "ls"}, timeout_s=5)
    past = (datetime.now(timezone.utc) - timedelta(seconds=10)).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    with store._lock:
        store._conn.execute("UPDATE approvals SET expires_at=? WHERE id=?", (past, rec["id"]))
        store._conn.commit()
    assert store.get(rec["id"])["status"] == "expired"
    assert store.consume(rec["id"]) is False

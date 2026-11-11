"""P0.5 approval store + policy tests."""
# 中文：P0.5 审批存储与策略测试。
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from runtime.approvals import ApprovalStore  # noqa: E402
from runtime.approvals.policy import ApprovalDecision, approval_timeout, classify_risk, decide  # noqa: E402


@pytest.fixture()
def store(tmp_path):
    s = ApprovalStore(tmp_path / "approvals.db")
    yield s
    s.close()


def test_create_and_get(store):
    record = store.create("run-1", "call-1", "shell_exec", {"command": "ls"}, risk="high", timeout_s=60)
    assert record["status"] == "pending"
    assert record["risk"] == "high"
    fetched = store.get(record["id"])
    assert fetched and fetched["tool"] == "shell_exec"
    assert json.loads(fetched["args_json"]) == {"command": "ls"}


def test_approve_and_deny(store):
    a = store.create("run-1", "call-1", "shell_exec", {"command": "ls"})
    approved = store.decide(a["id"], "approve", reason="ok")
    assert approved["status"] == "approved"
    assert approved["decided_by"] == "user"
    # 终态幂等
    again = store.decide(a["id"], "deny")
    assert again["status"] == "approved"

    b = store.create("run-1", "call-2", "python_exec", {"code": "1"})
    denied = store.decide(b["id"], "deny", reason="no")
    assert denied["status"] == "denied"
    assert denied["reason"] == "no"


def test_unknown_approval(store):
    assert store.get("apv_missing") is None
    assert store.decide("apv_missing", "approve") is None


def test_expiry(store):
    record = store.create("run-1", "call-1", "shell_exec", {"command": "ls"}, timeout_s=5)
    # 手动把 expires_at 改到过去
    past = (datetime.now(timezone.utc) - timedelta(seconds=10)).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    conn = store._conn
    with store._lock:
        conn.execute("UPDATE approvals SET expires_at=? WHERE id=?", (past, record["id"]))
        conn.commit()
    assert store.get(record["id"])["status"] == "expired"
    assert store.decide(record["id"], "approve")["status"] == "expired"
    assert store.expire_stale() == 0


def test_expire_stale_and_pending_list(store):
    a = store.create("run-1", "call-1", "shell_exec", {"command": "ls"})
    b = store.create("run-1", "call-2", "write_file", {"path": "x", "content": "y"})
    assert len(store.list_pending()) == 2
    past = (datetime.now(timezone.utc) - timedelta(seconds=10)).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    with store._lock:
        store._conn.execute("UPDATE approvals SET expires_at=? WHERE id=?", (past, a["id"]))
        store._conn.commit()
    assert store.expire_stale() == 1
    pending = store.list_pending()
    assert [r["id"] for r in pending] == [b["id"]]


def test_list_by_run(store):
    store.create("run-1", "call-1", "shell_exec", {"command": "ls"})
    store.create("run-1", "call-2", "write_file", {"path": "x", "content": "y"})
    store.create("run-2", "call-3", "shell_exec", {"command": "pwd"})
    assert len(store.list_by_run("run-1")) == 2
    assert len(store.list_by_run("run-2")) == 1


# ---------------- policy ----------------  ｜ ---------------- 策略 ----------------
def test_risk_classification():
    assert classify_risk("shell_exec") == "high"
    assert classify_risk("python_exec") == "high"
    assert classify_risk("write_file") == "medium"
    assert classify_risk("file_read") == "low"


def test_policy_confirm_default():
    settings = {"execution": {"approvalMode": "confirm"}}
    assert decide("file_read", {}, settings).kind == "allow"
    assert decide("shell_exec", {}, settings).kind == "confirm"
    assert decide("python_exec", {}, settings).kind == "confirm"
    assert decide("write_file", {}, settings).kind == "confirm"


def test_policy_auto_mode():
    settings = {"execution": {"approvalMode": "auto"}}
    assert decide("shell_exec", {}, settings).kind == "allow"


def test_policy_deny_list():
    settings = {"execution": {"approvalMode": "confirm", "denyTools": ["shell_exec"]}}
    decision = decide("shell_exec", {}, settings)
    assert decision.kind == "deny"


def test_policy_custom_confirm_tools():
    settings = {"execution": {"approvalMode": "confirm", "confirmTools": ["file_read"]}}
    assert decide("file_read", {}, settings).kind == "confirm"
    assert decide("shell_exec", {}, settings).kind == "allow"


def test_approval_timeout_setting():
    assert approval_timeout({"execution": {"approvalTimeoutSeconds": 30}}) == 30
    assert approval_timeout({}) == 120
    assert approval_timeout({"execution": {"approvalTimeoutSeconds": "bad"}}) == 120

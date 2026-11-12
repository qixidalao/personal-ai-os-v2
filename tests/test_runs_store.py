"""
P0 — RunStore 单元测试
======================

覆盖：
- run / tool_call 完整生命周期（prepared → dispatched → succeeded）
- failed / cancelled / unknown 终态与错误信息
- args_hash 规范化（key 顺序无关）
- 事件 seq 单调、after_seq 增量、中文 JSON 落库
- list_runs 会话过滤 / limit / 排序
- mark_interrupted_runs（running → unknown + 写事件，幂等）
- run / tool call 不存在时的行为、非法状态拒绝
- 10 线程并发写不丢（同一 run 的 tool_calls + events；以及并发创建 run）

运行（项目根目录）::

    pytest tests/test_runs_store.py -q
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from datetime import datetime
from typing import Any

import pytest

from runtime.runs.store import RunStore, args_hash


@pytest.fixture()
def store(tmp_path):
    """每个测试独立 DB 文件（WAL），结束后关闭连接。"""
    instance = RunStore(tmp_path / "runs.db")
    try:
        yield instance
    finally:
        instance.close()


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


# ---------------------------------------------------------------------------
# 生命周期
# ---------------------------------------------------------------------------
def test_run_and_tool_call_lifecycle(store: RunStore) -> None:
    run = store.create_run("run-1", "sess-1", "gpt-4o")
    assert run["id"] == "run-1"
    assert run["session_id"] == "sess-1"
    assert run["model"] == "gpt-4o"
    assert run["status"] == "running"
    assert run["finished_at"] is None
    assert run["meta"] == {}
    # UTC ISO8601，带 Z 且可解析出时区
    assert run["started_at"].endswith("Z")
    assert _parse_iso(run["started_at"]).utcoffset() is not None

    args = {"path": "/tmp/a.txt", "offset": 2}
    call = store.create_tool_call("call-1", "run-1", "read_file", args)
    assert call["status"] == "prepared"
    assert call["permission_decision"] == "allow"
    assert call["args"] == args
    assert call["finished_at"] is None
    assert call["output_bytes"] is None
    expected_hash = hashlib.sha256(
        json.dumps(args, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    assert call["args_hash"] == expected_hash

    dispatched = store.update_tool_call("call-1", "dispatched")
    assert dispatched is not None
    assert dispatched["status"] == "dispatched"
    assert dispatched["finished_at"] is None

    succeeded = store.update_tool_call("call-1", "succeeded", output_bytes=17)
    assert succeeded is not None
    assert succeeded["status"] == "succeeded"
    assert succeeded["output_bytes"] == 17
    assert succeeded["error"] is None
    assert succeeded["finished_at"] is not None
    assert succeeded["finished_at"].endswith("Z")

    finished = store.finish_run("run-1", "succeeded")
    assert finished is not None
    assert finished["status"] == "succeeded"
    assert finished["finished_at"] is not None
    assert finished["error"] is None

    snapshot = store.get_run("run-1")
    assert snapshot is not None
    assert snapshot["run"]["status"] == "succeeded"
    assert [item["id"] for item in snapshot["tool_calls"]] == ["call-1"]
    assert snapshot["tool_calls"][0]["status"] == "succeeded"
    assert snapshot["tool_calls"][0]["output_bytes"] == 17
    assert isinstance(snapshot["events"], list)


def test_failed_cancelled_unknown_states(store: RunStore) -> None:
    # 失败：工具报错 + run 失败
    store.create_run("run-f", "s", "m")
    store.create_tool_call("call-f", "run-f", "shell", {"cmd": "false"})
                                              # 中文：shell

    failed_call = store.update_tool_call("call-f", "failed", error="exit code 1")
    assert failed_call is not None
    assert failed_call["status"] == "failed"
    assert failed_call["error"] == "exit code 1"
    failed_run = store.finish_run("run-f", "failed", error="tool exploded")
    assert failed_run is not None
    assert failed_run["status"] == "failed"
    assert failed_run["error"] == "tool exploded"

    # 取消：客户端断连
    store.create_run("run-c", "s", "m")
    store.create_tool_call("call-c", "run-c", "shell", {})
                                              # 中文：shell

    store.update_tool_call("call-c", "cancelled", error="client disconnected")
    cancelled = store.finish_run("run-c", "cancelled", error="client disconnected")
    assert cancelled is not None
    assert cancelled["status"] == "cancelled"

    # unknown：无法证明执行结果
    store.create_run("run-u", "s", "m")
    store.create_tool_call("call-u", "run-u", "shell", {})
                                              # 中文：shell

    store.update_tool_call("call-u", "unknown")
    unknown = store.finish_run("run-u", "unknown", error="process killed")
    assert unknown is not None
    assert unknown["status"] == "unknown"
    assert unknown["error"] == "process killed"

    snapshot = store.get_run("run-u")
    assert snapshot is not None
    assert snapshot["tool_calls"][0]["status"] == "unknown"
    assert snapshot["tool_calls"][0]["finished_at"] is not None


def test_args_hash_is_key_order_independent(store: RunStore) -> None:
    store.create_run("run-h", "s", "m")
    first = store.create_tool_call("c1", "run-h", "tool", {"a": 1, "b": [2, 3]})
    second = store.create_tool_call("c2", "run-h", "tool", {"b": [2, 3], "a": 1})
    third = store.create_tool_call("c3", "run-h", "tool", {"a": 2, "b": [2, 3]})
    assert first["args_hash"] == second["args_hash"]
    assert first["args_hash"] != third["args_hash"]
    assert args_hash({"b": [2, 3], "a": 1}) == first["args_hash"]
    assert args_hash("not-json") == args_hash("not-json")

    # JSON 字符串入参按解析后的对象规范化
    from_json = store.create_tool_call("c4", "run-h", "tool", '{"b": [2, 3], "a": 1}')
    assert from_json["args"] == {"a": 1, "b": [2, 3]}
    assert from_json["args_hash"] == first["args_hash"]


# ---------------------------------------------------------------------------
# 事件
# ---------------------------------------------------------------------------
def test_events_seq_monotonic_and_after_seq(store: RunStore) -> None:
    store.create_run("run-e", "s", "m")
    assert store.add_event("run-e", "run.started", {"round": 0}) == 1
    assert store.next_seq("run-e") == 2
    assert store.add_event("run-e", "tool_call.prepared", {"tool_call_id": "c1"}) == 2
    assert store.add_event("run-e", "run.finished", {"status": "succeeded", "msg": "中文"}) == 3

    snapshot = store.get_run("run-e")
    assert snapshot is not None
    events = snapshot["events"]
    assert [event["seq"] for event in events] == [1, 2, 3]
    assert [event["type"] for event in events] == [
        "run.started",
        "tool_call.prepared",
        "run.finished",
    ]
    assert events[0]["data"] == {"round": 0}
    assert events[2]["data"]["msg"] == "中文"
    assert events[0]["ts"].endswith("Z")

    tail = store.list_events("run-e", after_seq=1)
    assert [event["seq"] for event in tail] == [2, 3]

    with pytest.raises(ValueError):
        store.add_event("run-missing", "x", {})


def test_events_persist_across_reopen(tmp_path) -> None:
    path = tmp_path / "runs.db"
    first = RunStore(path)
    try:
        first.create_run("run-p", "s", "m")
        first.add_event("run-p", "note", {"text": "持久化"})
    finally:
        first.close()

    second = RunStore(path)
    try:
        snapshot = second.get_run("run-p")
        assert snapshot is not None
        assert snapshot["events"][0]["data"] == {"text": "持久化"}
    finally:
        second.close()


# ---------------------------------------------------------------------------
# 列表 / 缺失 / 非法状态
# ---------------------------------------------------------------------------
def test_list_runs_filter_limit_and_order(store: RunStore) -> None:
    store.create_run("r1", "s1", "m")
    time.sleep(0.012)
    store.create_run("r2", "s1", "m")
    time.sleep(0.012)
    store.create_run("r3", "s2", "m")
    store.finish_run("r2", "succeeded")

    all_runs = store.list_runs()
    assert [run["id"] for run in all_runs] == ["r3", "r2", "r1"]
    assert all(isinstance(run["meta"], dict) for run in all_runs)

    s1_runs = store.list_runs(session_id="s1")
    assert [run["id"] for run in s1_runs] == ["r2", "r1"]
    assert store.list_runs(limit=1)[0]["id"] == "r3"
    assert store.list_runs(session_id="nope") == []


def test_missing_entities_return_none(store: RunStore) -> None:
    assert store.get_run("nope") is None
    assert store.list_events("nope") == []
    assert store.finish_run("nope", "succeeded") is None
    assert store.update_tool_call("nope", "succeeded") is None
    with pytest.raises(ValueError):
        store.next_seq("nope")
    with pytest.raises(ValueError):
        store.create_tool_call("call-x", "run-nope", "tool", {})


def test_invalid_statuses_and_duplicates_rejected(store: RunStore) -> None:
    store.create_run("run-x", "s", "m")
    with pytest.raises(ValueError):
        store.create_run("run-x", "s", "m")  # 重复 run id
    with pytest.raises(ValueError):
        store.finish_run("run-x", "running")  # 非终态不能 finish
    with pytest.raises(ValueError):
        store.finish_run("run-x", "done")  # 未知状态
    with pytest.raises(ValueError):
        store.update_tool_call("call-x", "bogus")

    store.create_tool_call("call-x", "run-x", "tool", {})
    with pytest.raises(ValueError):
        store.create_tool_call("call-x", "run-x", "tool", {})  # 重复 call id
    with pytest.raises(ValueError):
        store.update_tool_call("call-x", "succeeded", output_bytes=-1)


# ---------------------------------------------------------------------------
# 重启恢复
# ---------------------------------------------------------------------------
def test_mark_interrupted_runs(store: RunStore) -> None:
    store.create_run("run-a", "s1", "m")
    store.create_run("run-b", "s1", "m")
    store.create_run("run-done", "s1", "m")
    store.finish_run("run-done", "succeeded")

    store.create_tool_call("call-a1", "run-a", "shell", {"cmd": "sleep 10"})
                                               # 中文：shell

    store.update_tool_call("call-a1", "dispatched")
    store.create_tool_call("call-b1", "run-b", "read_file", {})
    store.create_tool_call("call-done", "run-done", "read_file", {})
    store.update_tool_call("call-done", "succeeded")

    fixed = "2026-11-11T00:00:00.000Z"
    assert store.mark_interrupted_runs(now=fixed) == 2
    # 幂等：第二次没有 running 可处理
    assert store.mark_interrupted_runs() == 0

    run_a = store.get_run("run-a")
    assert run_a is not None
    assert run_a["run"]["status"] == "unknown"
    assert run_a["run"]["finished_at"] == fixed
    assert run_a["run"]["error"]
    assert run_a["tool_calls"][0]["status"] == "unknown"
    assert run_a["tool_calls"][0]["finished_at"] == fixed

    interrupted = [event for event in run_a["events"] if event["type"] == "run_interrupted"]
    assert len(interrupted) == 1
    assert interrupted[0]["data"]["previous_status"] == "running"
    tool_interrupted = [
        event for event in run_a["events"] if event["type"] == "tool_call_interrupted"
    ]
    assert len(tool_interrupted) == 1
    assert tool_interrupted[0]["data"]["tool_call_id"] == "call-a1"

    run_b = store.get_run("run-b")
    assert run_b is not None
    assert run_b["run"]["status"] == "unknown"
    assert run_b["tool_calls"][0]["status"] == "unknown"

    run_done = store.get_run("run-done")
    assert run_done is not None
    assert run_done["run"]["status"] == "succeeded"
    assert run_done["tool_calls"][0]["status"] == "succeeded"
    assert all(event["type"] != "run_interrupted" for event in run_done["events"])


# ---------------------------------------------------------------------------
# 并发
# ---------------------------------------------------------------------------
def _run_threads(count: int, target) -> list[BaseException]:
    """启动 count 个线程同时执行 target(idx)，返回捕获到的异常。"""
    barrier = threading.Barrier(count)
    errors: list[BaseException] = []
    errors_lock = threading.Lock()

    def wrapper(idx: int) -> None:
        try:
            barrier.wait(timeout=10)
            target(idx)
        except BaseException as exc:  # noqa: BLE001 - 测试需要收集所有线程异常
            with errors_lock:
                errors.append(exc)

    threads = [threading.Thread(target=wrapper, args=(idx,)) for idx in range(count)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    assert all(not thread.is_alive() for thread in threads), "worker thread did not finish"
    return errors


def test_concurrent_writes_on_same_run(store: RunStore) -> None:
    store.create_run("run-conc", "s", "m")
    threads_count = 10
    calls_per_thread = 5
    events_per_thread = 20

    def worker(idx: int) -> None:
        store.create_tool_call(f"call-{idx}-0", "run-conc", "tool", {"worker": idx})
        for j in range(1, calls_per_thread):
            store.create_tool_call(f"call-{idx}-{j}", "run-conc", "tool", {"worker": idx, "j": j})
        for j in range(events_per_thread):
            store.add_event("run-conc", "worker.event", {"worker": idx, "j": j})

    errors = _run_threads(threads_count, worker)
    assert errors == []

    snapshot = store.get_run("run-conc")
    assert snapshot is not None
    assert len(snapshot["tool_calls"]) == threads_count * calls_per_thread
    assert len(snapshot["events"]) == threads_count * events_per_thread
    seqs = [event["seq"] for event in snapshot["events"]]
    assert seqs == list(range(1, threads_count * events_per_thread + 1))
    # 每个 worker 的参数都已落库且 hash 一致
    hashes = {call["args_hash"] for call in snapshot["tool_calls"]}
    assert len(hashes) == threads_count * calls_per_thread


def test_concurrent_create_runs(store: RunStore) -> None:
    total = 10

    def worker(idx: int) -> None:
        run_id = f"run-{idx}"
        store.create_run(run_id, "session-hot", "m")
        for j in range(5):
            store.add_event(run_id, "worker.event", {"i": idx, "j": j})

    errors = _run_threads(total, worker)
    assert errors == []

    runs = store.list_runs(session_id="session-hot", limit=100)
    assert len(runs) == total
    for run in runs:
        snapshot = store.get_run(run["id"])
        assert snapshot is not None
        assert [event["seq"] for event in snapshot["events"]] == [1, 2, 3, 4, 5]


def test_audit_args_redact_sensitive_values_but_preserve_hash(store: RunStore) -> None:
    args = {"api_key": "secret-value", "nested": {"password": "pw", "query": "hello"}}
    store.create_run("run-redact", "s", "m")
    call = store.create_tool_call("call-redact", "run-redact", "tool", args)
    assert call["args"]["api_key"] == "[REDACTED]"
    assert call["args"]["nested"]["password"] == "[REDACTED]"
    assert call["args"]["nested"]["query"] == "hello"
    assert call["args_hash"] == args_hash(args)

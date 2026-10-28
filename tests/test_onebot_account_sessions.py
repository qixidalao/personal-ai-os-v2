import json

from backend.event import EventBus
from backend.onebot.adapter import OneBotChatWorker


def make_worker(tmp_path, monkeypatch):
    worker = OneBotChatWorker(EventBus())
    worker._accounts_path = tmp_path / "onebot_accounts.json"
    monkeypatch.setattr(worker, "_load_settings", lambda: {"qq_systemPrompt": "旧提示词"})
    return worker


def event(nickname):
    return {"sender": {"nickname": nickname, "sex": "male", "age": 18}}


def test_private_group_and_group_members_are_isolated(tmp_path, monkeypatch):
    worker = make_worker(tmp_path, monkeypatch)

    private = worker._get_session("10001", "私聊", "", event("小明"))
    group_a = worker._get_session("10001", "群聊", "20001", event("小明"))
    group_b = worker._get_session("10001", "群聊", "20002", event("小明"))
    other_member = worker._get_session("10002", "群聊", "20001", event("小红"))

    private["系统提示词"] = "私聊提示词"
    group_a["系统提示词"] = "群 A 提示词"
    group_b["系统提示词"] = "群 B 提示词"
    other_member["系统提示词"] = "另一位群友提示词"

    assert len({
        private["系统提示词"], group_a["系统提示词"],
        group_b["系统提示词"], other_member["系统提示词"],
    }) == 4


def test_group_history_keeps_six_rounds(tmp_path, monkeypatch):
    worker = make_worker(tmp_path, monkeypatch)
    history = [{"role": "user", "content": str(i)} for i in range(14)]
    history[:] = history[-12:]
    assert [m["content"] for m in history] == [str(i) for i in range(2, 14)]


def test_account_shape_and_persistence(tmp_path, monkeypatch):
    worker = make_worker(tmp_path, monkeypatch)
    worker._get_session("123456", "群聊", "654321", event("小明"))

    data = json.loads(worker._accounts_path.read_text(encoding="utf-8"))
    account = data["123456"]
    assert account["账号基本信息"] == {"账号": "123456", "昵称": "小明", "性别": "男", "年龄": 18}
    assert "私聊" in account
    assert "654321" in account["群聊"]
    assert account["群聊"]["654321"]["系统提示词"] == "旧提示词"

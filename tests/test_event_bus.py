"""
单元测试 — EventBus 事件总线
"""

import asyncio
import pytest
from backend.event.event_bus import EventBus, Event, EventPriority


class TestEventBus:
    """EventBus 核心功能测试"""

    @pytest.fixture
    def bus(self):
        """每次测试前创建新的事件总线实例"""
        return EventBus()

    @pytest.mark.asyncio
    async def test_emit_and_subscribe(self, bus):
        """测试基本的事件发布与订阅"""
        received = []

        async def handler(event):
            received.append(event)

        bus.subscribe("test.event", handler)
        await bus.emit("test.event", {"msg": "hello"})

        assert len(received) == 1
        assert received[0].type == "test.event"
        assert received[0].data["msg"] == "hello"

    @pytest.mark.asyncio
    async def test_wildcard_subscriber(self, bus):
        """测试通配符 '*' 监听所有事件"""
        received = []

        async def wildcard_handler(event):
            received.append(event.type)

        bus.subscribe("*", wildcard_handler)

        await bus.emit("event.a")
        await bus.emit("event.b")
        await bus.emit("event.c")

        assert len(received) == 3
        assert received == ["event.a", "event.b", "event.c"]

    @pytest.mark.asyncio
    async def test_no_subscriber(self, bus):
        """测试没有订阅者时 emit 不报错"""
        event = await bus.emit("orphan.event", {"data": "no one listens"})
        assert event.type == "orphan.event"
        assert event.data == {"data": "no one listens"}

    @pytest.mark.asyncio
    async def test_multiple_subscribers_same_event(self, bus):
        """测试同一事件的多个订阅者都被调用"""
        results = []

        async def handler_a(event):
            results.append("a")

        async def handler_b(event):
            results.append("b")

        bus.subscribe("multi.event", handler_a)
        bus.subscribe("multi.event", handler_b)

        await bus.emit("multi.event")
        assert len(results) == 2
        assert "a" in results
        assert "b" in results

    @pytest.mark.asyncio
    async def test_unsubscribe(self, bus):
        """测试取消订阅后不再收到事件"""
        received = []

        async def handler(event):
            received.append(event)

        bus.subscribe("temp.event", handler)
        await bus.emit("temp.event")
        assert len(received) == 1

        bus.unsubscribe("temp.event", handler)
        await bus.emit("temp.event")
        # 取消后不应再收到
        assert len(received) == 1

    @pytest.mark.asyncio
    async def test_event_object_defaults(self, bus):
        """测试 Event 对象的默认值"""
        event = Event(type="test.event", data={"key": "value"})

        assert event.type == "test.event"
        assert event.data == {"key": "value"}
        assert event.source == ""  # 默认空
        assert event.priority == EventPriority.NORMAL
        assert event.id is not None
        assert len(event.id) > 0
        assert event.metadata == {}

    @pytest.mark.asyncio
    async def test_event_custom_priority(self, bus):
        """测试自定义优先级的事件"""
        event = await bus.emit(
            "critical.event",
            data={"alert": "danger"},
            priority=EventPriority.CRITICAL,
            source="test",
        )
        assert event.priority == EventPriority.CRITICAL
        assert event.source == "test"

    @pytest.mark.asyncio
    async def test_on_decorator(self, bus):
        """测试 @bus.on() 装饰器方式订阅"""
        received = []

        @bus.on("decorator.event")
        async def decorated_handler(event):
            received.append(event.type)

        await bus.emit("decorator.event")
        assert len(received) == 1
        assert received[0] == "decorator.event"

    @pytest.mark.asyncio
    async def test_event_history(self, bus):
        """测试事件历史记录"""
        await bus.emit("event.1", "data1")
        await bus.emit("event.2", "data2")
        await bus.emit("event.1", "data3")

        history = bus.get_history()
        assert len(history) == 3
        assert history[0].data == "data1"
        assert history[2].data == "data3"

        filtered = bus.get_history("event.1")
        assert len(filtered) == 2
        assert all(e.type == "event.1" for e in filtered)

    @pytest.mark.asyncio
    async def test_event_history_limit(self, bus):
        """测试历史记录 limit 参数"""
        for i in range(10):
            await bus.emit("test.event", i)

        full = bus.get_history(limit=100)
        limited = bus.get_history(limit=3)

        assert len(full) == 10
        assert len(limited) == 3

    @pytest.mark.asyncio
    async def test_clear_history(self, bus):
        """测试清空历史记录"""
        await bus.emit("event.a")
        await bus.emit("event.b")
        assert len(bus.get_history()) == 2

        bus.clear_history()
        assert len(bus.get_history()) == 0

    @pytest.mark.asyncio
    async def test_max_history_bounded(self, bus):
        """测试历史记录最大数量限制"""
        # 构造一个 max_history=5 的总线
        bus._max_history = 5
        for i in range(10):
            await bus.emit("burst.event", i)

        history = bus.get_history(limit=100)
        assert len(history) == 5
        # 应保留最后 5 个
        assert [e.data for e in history] == [5, 6, 7, 8, 9]

    @pytest.mark.asyncio
    async def test_add_filter(self, bus):
        """测试事件过滤器"""
        received = []

        async def handler(event):
            received.append(event)

        bus.subscribe("filtered.event", handler)

        # 添加过滤器：丢弃 data 为 None 的事件
        bus.add_filter("filtered.event", lambda e: e.data is None)

        await bus.emit("filtered.event", "has_data")
        await bus.emit("filtered.event", None)  # 应被过滤
        await bus.emit("filtered.event", "also_data")

        assert len(received) == 2

    @pytest.mark.asyncio
    async def test_sync_handler_support(self, bus):
        """测试同步函数也能作为订阅者"""
        received = []

        def sync_handler(event):
            received.append(event.type)

        bus.subscribe("sync.event", sync_handler)
        await bus.emit("sync.event")

        assert len(received) == 1
        assert received[0] == "sync.event"

    @pytest.mark.asyncio
    async def test_handler_exception_does_not_break(self, bus):
        """测试某个处理器抛出异常不影响其他处理器"""

        async def broken_handler(event):
            raise RuntimeError("I am broken")

        async def good_handler(event):
            good_handler.called = True

        good_handler.called = False

        bus.subscribe("error.event", broken_handler)
        bus.subscribe("error.event", good_handler)

        # 不应抛出异常
        await bus.emit("error.event", "test")
        assert good_handler.called is True

    @pytest.mark.asyncio
    async def test_handler_exception_emits_error_event(self, bus):
        """测试处理器异常时会发射 error 事件"""
        error_events = []

        async def error_listener(event):
            error_events.append(event)

        bus.subscribe("error", error_listener)

        async def failing_handler(event):
            raise ValueError("fail")

        bus.subscribe("source.event", failing_handler)

        await bus.emit("source.event")

        # 应该有 error 事件被发出
        assert len(error_events) >= 1
        assert error_events[0].type == "error"
        assert "fail" in str(error_events[0].data.get("error", ""))

    @pytest.mark.asyncio
    async def test_bus_isolated_instances(self, bus):
        """测试不同 EventBus 实例相互隔离"""
        bus2 = EventBus()

        received_bus1 = []
        received_bus2 = []

        async def handler1(e):
            received_bus1.append(e.type)

        async def handler2(e):
            received_bus2.append(e.type)

        bus.subscribe("test", handler1)
        bus2.subscribe("test", handler2)

        await bus.emit("test")
        assert len(received_bus1) == 1
        assert len(received_bus2) == 0

        await bus2.emit("test")
        assert len(received_bus1) == 1  # bus1 不应收到 bus2 的事件
        assert len(received_bus2) == 1

    @pytest.mark.asyncio
    async def test_event_has_timestamp(self, bus):
        """测试事件包含时间戳"""
        import time
        before = time.time()
        event = await bus.emit("timed.event")
        after = time.time()

        assert before <= event.timestamp <= after

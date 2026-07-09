"""
集成测试 — 核心流程
"""
import pytest


class TestCoreFlow:
    """核心流程测试"""

    def test_config_loading(self):
        """测试配置加载"""
        from backend.config.loader import ConfigLoader
        from pathlib import Path

        loader = ConfigLoader(Path("config"))
        configs = loader.load_all()
        assert "app" in configs
        assert "api" in configs
        assert configs["app"]["app"]["name"] == "Personal AI OS"

    def test_event_bus(self):
        """测试事件总线"""
        import asyncio
        from backend.event.event_bus import EventBus

        async def test():
            bus = EventBus()
            received = []

            async def handler(event):
                received.append(event)

            bus.subscribe("test.event", handler)
            await bus.emit("test.event", {"msg": "hello"})

            assert len(received) == 1
            assert received[0].type == "test.event"
            assert received[0].data["msg"] == "hello"

        asyncio.run(test())

    def test_tool_registry(self):
        """测试工具注册"""
        from tools import ToolRegistry

        tools = ToolRegistry.list()
        assert len(tools) > 0

        filesystem_tools = ToolRegistry.list("filesystem")
        assert len(filesystem_tools) > 0

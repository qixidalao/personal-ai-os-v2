"""
单元测试 — Memory 记忆系统
"""

import pytest
from datetime import datetime
from runtime.memory import (
    BaseMemory, SessionMemory, MemoryItem,
)


class TestMemoryItem:
    """MemoryItem 数据类测试"""

    def test_default_timestamp(self):
        """测试 MemoryItem 自动生成时间戳"""
        before = datetime.now().timestamp()
        item = MemoryItem(id="1", content="test", type="session")
        after = datetime.now().timestamp()
        assert before <= item.timestamp <= after

    def test_custom_timestamp(self):
        """测试 MemoryItem 支持自定义时间戳"""
        item = MemoryItem(id="2", content="custom", type="fact", timestamp=12345.0)
        assert item.timestamp == 12345.0

    def test_default_score(self):
        """测试默认 score 为 0.0"""
        item = MemoryItem(id="3", content="no score", type="session")
        assert item.score == 0.0

    def test_all_fields(self):
        """测试 MemoryItem 所有字段"""
        item = MemoryItem(
            id="4",
            content="full item",
            type="vector",
            timestamp=100.0,
            metadata={"source": "test"},
            embedding=[0.1, 0.2, 0.3],
            score=0.95,
        )
        assert item.id == "4"
        assert item.content == "full item"
        assert item.type == "vector"
        assert item.metadata == {"source": "test"}
        assert item.embedding == [0.1, 0.2, 0.3]
        assert item.score == 0.95


class TestBaseMemory:
    """BaseMemory 基类测试"""

    def test_abstract_methods_raise(self):
        """测试基类方法抛出 NotImplementedError"""
        mem = BaseMemory({"enabled": True})

        with pytest.raises(NotImplementedError):
            import asyncio
            asyncio.run(mem.store(MemoryItem(id="1", content="x", type="test")))

        with pytest.raises(NotImplementedError):
            import asyncio
            asyncio.run(mem.retrieve("query"))

        with pytest.raises(NotImplementedError):
            import asyncio
            asyncio.run(mem.delete("1"))

    def test_enabled_config(self):
        """测试 enabled 配置项"""
        mem_enabled = BaseMemory({"enabled": True})
        mem_disabled = BaseMemory({"enabled": False})
        assert mem_enabled.enabled is True
        assert mem_disabled.enabled is False

    def test_default_enabled(self):
        """测试默认 enabled 为 True"""
        mem = BaseMemory({})
        assert mem.enabled is True


class TestSessionMemory:
    """SessionMemory 会话记忆测试"""

    @pytest.fixture
    def session_mem(self):
        """创建 SessionMemory 实例"""
        return SessionMemory({"max_messages": 10})

    @pytest.mark.asyncio
    async def test_store_and_retrieve(self, session_mem):
        """测试存储和检索消息"""
        item = MemoryItem(
            id="msg_1",
            content="Hello",
            type="session",
            metadata={"role": "user"},
        )
        await session_mem.store(item)

        items = await session_mem.retrieve()
        assert len(items) == 1
        assert items[0].content == "Hello"
        assert items[0].metadata["role"] == "user"
        assert items[0].type == "session"

    @pytest.mark.asyncio
    async def test_store_multiple_messages(self, session_mem):
        """测试存储多条消息并按序检索"""
        for i in range(5):
            role = "user" if i % 2 == 0 else "assistant"
            item = MemoryItem(
                id=f"msg_{i}",
                content=f"Message {i}",
                type="session",
                metadata={"role": role},
            )
            await session_mem.store(item)

        items = await session_mem.retrieve()
        assert len(items) == 5
        assert items[0].content == "Message 0"
        assert items[1].content == "Message 1"
        # msg_3 索引为 3, 3%2=1 → role=assistant
        assert items[3].metadata["role"] == "assistant"

    @pytest.mark.asyncio
    async def test_max_messages_limit(self, session_mem):
        """测试超过 max_messages 时丢弃最早的消息"""
        for i in range(15):
            item = MemoryItem(
                id=f"msg_{i}",
                content=f"Message {i}",
                type="session",
                metadata={"role": "user"},
            )
            await session_mem.store(item)

        # max_messages=10，所以只保留最后 10 条
        items = await session_mem.retrieve()
        assert len(items) == 10
        assert items[0].content == "Message 5"
        assert items[-1].content == "Message 14"

    @pytest.mark.asyncio
    async def test_get_messages(self, session_mem):
        """测试 get_messages 返回字典列表"""
        await session_mem.store(MemoryItem(
            id="1", content="Hi", type="session", metadata={"role": "user"}
        ))
        await session_mem.store(MemoryItem(
            id="2", content="Hello!", type="session", metadata={"role": "assistant"}
        ))

        messages = await session_mem.get_messages()
        assert len(messages) == 2
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "Hi"
        assert messages[1]["role"] == "assistant"
        assert messages[1]["content"] == "Hello!"

    @pytest.mark.asyncio
    async def test_clear(self, session_mem):
        """测试清空记忆"""
        for i in range(3):
            await session_mem.store(MemoryItem(
                id=f"msg_{i}", content=f"M{i}", type="session", metadata={"role": "user"}
            ))

        assert len(await session_mem.retrieve()) == 3
        await session_mem.clear()
        assert len(await session_mem.retrieve()) == 0
        assert len(await session_mem.get_messages()) == 0

    @pytest.mark.asyncio
    async def test_retrieve_empty(self, session_mem):
        """测试空记忆检索返回空列表"""
        items = await session_mem.retrieve()
        assert items == []

    @pytest.mark.asyncio
    async def test_custom_max_messages(self):
        """测试自定义 max_messages"""
        mem = SessionMemory({"max_messages": 3})
        for i in range(5):
            await mem.store(MemoryItem(
                id=f"msg_{i}", content=f"M{i}", type="session", metadata={"role": "user"}
            ))

        assert len(await mem.retrieve()) == 3

    @pytest.mark.asyncio
    async def test_store_returns_true(self, session_mem):
        """测试 store 返回 True"""
        result = await session_mem.store(MemoryItem(
            id="1", content="test", type="session", metadata={"role": "user"}
        ))
        assert result is True

    @pytest.mark.asyncio
    async def test_messages_ordered_by_insertion(self, session_mem):
        """测试消息按插入顺序排列"""
        for i in range(4):
            await session_mem.store(MemoryItem(
                id=f"msg_{i}", content=f"M{i}", type="session", metadata={"role": "user"}
            ))

        messages = await session_mem.get_messages()
        assert [m["content"] for m in messages] == ["M0", "M1", "M2", "M3"]

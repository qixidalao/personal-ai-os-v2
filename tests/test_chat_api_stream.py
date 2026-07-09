"""
集成测试 — chat_api.py 流式 API
（Mock LLM HTTP 调用，测试工具循环编排逻辑）
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from backend.main import app


# ── Mock SSE 数据：模拟 OpenAI 流式响应 ──
MOCK_SSE_CHUNKS = [
    b'data: {"choices":[{"delta":{"role":"assistant"},"index":0}]}\n\n',
    b'data: {"choices":[{"delta":{"content":"Hello"},"index":0}]}\n\n',
    b'data: {"choices":[{"delta":{"content":"!"},"index":0}]}\n\n',
    b'data: {"choices":[{"delta":{},"finish_reason":"stop","index":0}]}\n\n',
    b"data: [DONE]\n\n",
]


class MockStreamResponse:
    """模拟 httpx 流式响应，实现 async context manager + aiter_bytes。"""
    def __init__(self, chunks: list[bytes]):
        self.status_code = 200
        self._chunks = chunks

    async def __aenter__(self) -> "MockStreamResponse":
        return self

    async def __aexit__(self, *args) -> None:
        pass

    async def aiter_bytes(self):
        for chunk in self._chunks:
            yield chunk


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def mock_llm_stream():
    """
    自动 mock httpx.AsyncClient 的 stream 方法，
    返回模拟的 SSE 数据，避免真实 HTTP 调用。

    ⚠️ 关键设计：
    - httpx.AsyncClient.__aenter__ 返回自身 → AsyncMock
    - httpx.AsyncClient.stream() 是普通方法（非协程）→ MagicMock
    - stream() 返回 async context manager → MockStreamResponse
    """
    with patch("backend.chat_api.httpx.AsyncClient") as mock_client_cls:
        mock_response = MockStreamResponse(MOCK_SSE_CHUNKS)

        # mock client：__aenter__ 返回自身，stream 返回 mock response
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.stream = MagicMock(return_value=mock_response)

        mock_client_cls.return_value = mock_client
        yield


class TestChatStreamEndpoint:
    """测试 /api/v1/chat/stream SSE 端点（已 mock LLM）"""

    def test_stream_requires_post(self, client):
        """测试 GET 请求被拒绝"""
        response = client.get("/api/v1/chat/stream")
        assert response.status_code != 200

    def test_stream_accepts_post(self, client):
        """测试 POST 请求返回 StreamingResponse"""
        response = client.post(
            "/api/v1/chat/stream",
            json={
                "messages": [{"role": "user", "content": "Hello"}],
                "model": "gpt-4o",
                "baseUrl": "http://fake-api.test/v1",
            },
        )
        assert response.status_code == 200

    def test_stream_content_type(self, client):
        """测试响应为 SSE 格式"""
        response = client.post(
            "/api/v1/chat/stream",
            json={
                "messages": [{"role": "user", "content": "Hi"}],
                "model": "gpt-4o",
                "baseUrl": "http://fake-api.test/v1",
            },
        )
        content_type = response.headers.get("content-type", "")
        assert "text/event-stream" in content_type

    def test_stream_has_cache_control(self, client):
        """测试 SSE 响应包含 Cache-Control 头"""
        response = client.post(
            "/api/v1/chat/stream",
            json={
                "messages": [{"role": "user", "content": "Hi"}],
                "model": "gpt-4o",
                "baseUrl": "http://fake-api.test/v1",
            },
        )
        assert "Cache-Control" in response.headers

    def test_stream_has_request_id(self, client):
        """测试 SSE 响应包含 X-Stream-Request-Id 头"""
        response = client.post(
            "/api/v1/chat/stream",
            json={
                "messages": [{"role": "user", "content": "Hi"}],
                "model": "gpt-4o",
                "baseUrl": "http://fake-api.test/v1",
            },
        )
        assert "X-Stream-Request-Id" in response.headers

    def test_stream_returns_sse_events(self, client):
        """测试返回的 SSE 事件格式正确"""
        response = client.post(
            "/api/v1/chat/stream",
            json={
                "messages": [{"role": "user", "content": "Hello"}],
                "model": "gpt-4o",
                "baseUrl": "http://fake-api.test/v1",
            },
        )
        text = response.text
        lines = [l.strip() for l in text.strip().split("\n") if l.strip()]

        # 所有非空行应以 "data: " 开头
        for line in lines:
            assert line.startswith("data: "), f"Bad line: {line}"

    def test_stream_ends_with_done_marker(self, client):
        """测试 SSE 流以 data: [DONE] 结尾"""
        response = client.post(
            "/api/v1/chat/stream",
            json={
                "messages": [{"role": "user", "content": "Hello"}],
                "model": "gpt-4o",
                "baseUrl": "http://fake-api.test/v1",
            },
        )
        text = response.text.strip()
        assert text.endswith("data: [DONE]")

    def test_stream_events_are_valid_json(self, client):
        """测试每个 SSE data 都是合法 JSON"""
        response = client.post(
            "/api/v1/chat/stream",
            json={
                "messages": [{"role": "user", "content": "Hello"}],
                "model": "gpt-4o",
                "baseUrl": "http://fake-api.test/v1",
            },
        )
        for line in response.text.strip().split("\n"):
            line = line.strip()
            if not line or line == "data: [DONE]":
                continue
            assert line.startswith("data: ")
            payload = line[6:]
            event = json.loads(payload)
            assert "type" in event

    def test_stream_contains_content_event(self, client):
        """测试流中包含 content 类型的事件"""
        response = client.post(
            "/api/v1/chat/stream",
            json={
                "messages": [{"role": "user", "content": "Hello"}],
                "model": "gpt-4o",
                "baseUrl": "http://fake-api.test/v1",
            },
        )
        events = []
        for line in response.text.strip().split("\n"):
            line = line.strip()
            if line.startswith("data: ") and line != "data: [DONE]":
                events.append(json.loads(line[6:]))

        types = [e["type"] for e in events]
        assert "content" in types

    def test_stream_contains_done_event(self, client):
        """测试流中包含 done 类型的事件"""
        response = client.post(
            "/api/v1/chat/stream",
            json={
                "messages": [{"role": "user", "content": "Hello"}],
                "model": "gpt-4o",
                "baseUrl": "http://fake-api.test/v1",
            },
        )
        events = []
        for line in response.text.strip().split("\n"):
            line = line.strip()
            if line.startswith("data: ") and line != "data: [DONE]":
                events.append(json.loads(line[6:]))

        types = [e["type"] for e in events]
        assert "done" in types

    def test_stream_invalid_body(self, client):
        """测试请求体缺少必要字段返回 422"""
        response = client.post(
            "/api/v1/chat/stream",
            json={"messages": []},
        )
        assert response.status_code == 422


class TestChatCompletionsEndpoint:
    """测试 /api/v1/chat/completions 一次性接口（已 mock LLM）"""

    def test_completions_invalid_body(self, client):
        """测试请求体缺少必要字段"""
        response = client.post(
            "/api/v1/chat/completions",
            json={"messages": []},
        )
        assert response.status_code == 422

    def test_completions_success(self, client):
        """测试正常请求返回 ChatResponse"""
        response = client.post(
            "/api/v1/chat/completions",
            json={
                "messages": [{"role": "user", "content": "Hello"}],
                "model": "gpt-4o",
                "baseUrl": "http://fake-api.test/v1",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "reply" in data
        assert "model" in data
        assert "rounds" in data

    def test_completions_reply_content(self, client):
        """测试回复内容正确"""
        response = client.post(
            "/api/v1/chat/completions",
            json={
                "messages": [{"role": "user", "content": "Hello"}],
                "model": "gpt-4o",
                "baseUrl": "http://fake-api.test/v1",
            },
        )
        data = response.json()
        assert data["reply"] == "Hello!"
        assert data["model"] == "gpt-4o"


class TestChatApiUnit:
    """chat_api 纯单元测试"""

    def test_get_enabled_tools_returns_list(self):
        """测试 _get_enabled_tools 返回正确结构"""
        from backend.chat_api import _get_enabled_tools

        tools = _get_enabled_tools()
        assert len(tools) > 0

        for tool in tools:
            assert tool["type"] == "function"
            assert "function" in tool
            fn = tool["function"]
            assert "name" in fn
            assert "description" in fn
            assert "parameters" in fn

    def test_tool_registry_has_filesystem_tools(self):
        """测试 chat_api import 后文件系统工具已注册"""
        from tools import ToolRegistry
        file_tool = ToolRegistry.get("file_read")
        assert file_tool is not None
        assert file_tool.category == "filesystem"

    def test_all_tool_categories_present(self):
        """测试所有工具类别都已注册"""
        from tools import ToolRegistry
        categories = set(t.category for t in ToolRegistry.list())
        assert "filesystem" in categories

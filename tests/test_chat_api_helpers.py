"""
单元测试 — chat_api.py 工具函数
（不依赖 LLM 网络调用的纯函数）
"""

import json
import pytest
from backend.chat_api import (
    _normalize_base_url,
    _normalize_tool_schema,
    _tool_result_to_str,
    _extract_reasoning_from_message,
    _split_think_tags,
    _preview,
    _read_settings,
    ChatRequest,
    ChatResponse,
)


class TestNormalizeBaseUrl:
    """测试 _normalize_base_url"""

    def test_strips_trailing_slash(self):
        assert _normalize_base_url("https://api.openai.com/v1/") == "https://api.openai.com/v1"

    def test_no_trailing_slash(self):
        assert _normalize_base_url("https://api.openai.com/v1") == "https://api.openai.com/v1"

    def test_empty_string(self):
        assert _normalize_base_url("") == ""

    def test_single_slash(self):
        assert _normalize_base_url("/") == ""

    def test_multiple_trailing_slashes(self):
        assert _normalize_base_url("http://test.com//") == "http://test.com"


class TestNormalizeToolSchema:
    """测试 _normalize_tool_schema"""

    def make_mock_spec(self, params: dict):
        """创建模拟的 ToolSpec 对象"""
        class MockSpec:
            parameters = params
        return MockSpec()

    def test_empty_parameters(self):
        spec = self.make_mock_spec({})
        result = _normalize_tool_schema(spec)
        assert result == {"type": "object", "properties": {}}

    def test_none_parameters(self):
        spec = self.make_mock_spec(None)
        result = _normalize_tool_schema(spec)
        assert result == {"type": "object", "properties": {}}

    def test_string_type_normalization(self):
        spec = self.make_mock_spec({
            "properties": {
                "name": {"type": "str"},
                "desc": {"type": "string"},
                "age": {"type": "int"},
            }
        })
        result = _normalize_tool_schema(spec)
        assert result["properties"]["name"]["type"] == "string"
        assert result["properties"]["desc"]["type"] == "string"
        assert result["properties"]["age"]["type"] == "integer"

    def test_class_repr_type_normalization(self):
        spec = self.make_mock_spec({
            "properties": {
                "x": {"type": "<class 'str'>"},
                "y": {"type": "<class 'int'>"},
                "z": {"type": "<class 'dict'>"},
                "w": {"type": "<class 'float'>"},
            }
        })
        result = _normalize_tool_schema(spec)
        assert result["properties"]["x"]["type"] == "string"
        assert result["properties"]["y"]["type"] == "integer"
        assert result["properties"]["z"]["type"] == "object"
        assert result["properties"]["w"]["type"] == "string"  # float 默认 fallback

    def test_unknown_type_fallback(self):
        spec = self.make_mock_spec({
            "properties": {
                "data": {"type": "binary"},
            }
        })
        result = _normalize_tool_schema(spec)
        assert result["properties"]["data"]["type"] == "string"


class TestToolResultToStr:
    """测试 _tool_result_to_str"""

    def test_string_returned_as_is(self):
        assert _tool_result_to_str("hello") == "hello"

    def test_empty_string(self):
        assert _tool_result_to_str("") == ""

    def test_dict_to_json(self):
        result = _tool_result_to_str({"key": "value", "num": 42})
        assert json.loads(result) == {"key": "value", "num": 42}

    def test_list_to_json(self):
        result = _tool_result_to_str([1, 2, 3])
        assert json.loads(result) == [1, 2, 3]

    def test_int_to_str(self):
        result = _tool_result_to_str(42)
        assert result == "42"

    def test_none_to_str(self):
        result = _tool_result_to_str(None)
        assert result == "null"

    def test_circular_ref_fallback(self):
        class Loop:
            def __init__(self):
                self.self = self

        result = _tool_result_to_str(Loop())
        # 应该 fallback 到 str()
        assert isinstance(result, str)


class TestExtractReasoningFromMessage:
    """测试 _extract_reasoning_from_message"""

    def test_reasoning_content(self):
        msg = {"reasoning_content": "thinking step 1"}
        assert _extract_reasoning_from_message(msg) == "thinking step 1"

    def test_reasoning_key(self):
        msg = {"reasoning": "thinking step 1"}
        assert _extract_reasoning_from_message(msg) == "thinking step 1"

    def test_reasoning_text(self):
        msg = {"reasoning_text": "thinking step 1"}
        assert _extract_reasoning_from_message(msg) == "thinking step 1"

    def test_no_reasoning(self):
        msg = {"content": "just content"}
        assert _extract_reasoning_from_message(msg) == ""

    def test_empty_reasoning(self):
        msg = {"reasoning_content": ""}
        assert _extract_reasoning_from_message(msg) == ""

    def test_priority_content(self):
        """reasoning_content 优先于 reasoning"""
        msg = {"reasoning_content": "primary", "reasoning": "secondary"}
        assert _extract_reasoning_from_message(msg) == "primary"


class TestSplitThinkTags:
    """测试 _split_think_tags"""

    def test_no_think_tags(self):
        content, reasoning = _split_think_tags("Hello world")
        assert content == "Hello world"
        assert reasoning == ""

    def test_simple_think_tag(self):
        content, reasoning = _split_think_tags("Answer<think>I need to think</think>Final")
        assert "I need to think" in reasoning
        assert "Answer" in content
        assert "Final" in content
        assert "<think>" not in content

    def test_multiple_think_tags(self):
        """多个 think 标签：标签被移除，内容合并，reasoning 拼接"""
        content, reasoning = _split_think_tags(
            "A<think>first</think>B<think>second</think>C"
        )
        assert "first" in reasoning
        assert "second" in reasoning
        # 移除标签后 "A"+"B"+"C" → "ABC"
        assert "A" in content and "B" in content and "C" in content
        assert "<think>" not in content

    def test_existing_reasoning_appended(self):
        content, reasoning = _split_think_tags(
            "Answer<think>new thought</think>",
            existing_reasoning="previous thought"
        )
        assert "previous thought" in reasoning
        assert "new thought" in reasoning

    def test_unclosed_tag(self):
        content, reasoning = _split_think_tags("Text<think>unclosed")
        assert "<think>" in content  # 不匹配的标签留在内容里
        assert reasoning == ""

    def test_empty_think_content(self):
        content, reasoning = _split_think_tags("A<think>  </think>B")
        # 空白内容不追加到 reasoning
        assert reasoning == ""
        # 标签被移除
        assert "<think>" not in content
        assert "A" in content and "B" in content

    def test_case_insensitive(self):
        content, reasoning = _split_think_tags("Hi<THINK>secret</THINK>Bye")
        assert "secret" in reasoning
        assert "<THINK>" not in content

    def test_newlines_in_think(self):
        """think 标签内的换行符"""
        content, reasoning = _split_think_tags(
            "Result<think>\nline1\nline2\n</think>Done"
        )
        assert "line1" in reasoning
        assert "line2" in reasoning
        assert "<think>" not in content
        assert "Result" in content and "Done" in content


class TestPreview:
    """测试 _preview"""

    def test_short_string(self):
        assert _preview("hello") == "hello"

    def test_exact_limit(self):
        s = "a" * 80
        assert _preview(s) == s

    def test_exceeds_limit(self):
        s = "a" * 100
        result = _preview(s, limit=80)
        assert len(result) == 80 + 1  # 80 chars + …
        assert result.endswith("…")

    def test_newline_replacement(self):
        result = _preview("hello\nworld")
        assert "\\n" in result

    def test_none_input(self):
        """None → str(None or '') → str('') → ''"""
        assert _preview(None) == ""

    def test_number_input(self):
        assert _preview(42) == "42"

    def test_custom_limit(self):
        result = _preview("abcdefghij", limit=5)
        assert result == "abcde…"


class TestChatRequest:
    """测试 ChatRequest Pydantic 模型"""

    def test_valid_request(self):
        req = ChatRequest(
            messages=[{"role": "user", "content": "Hi"}],
            model="gpt-4o",
            baseUrl="https://api.openai.com/v1",
        )
        assert req.messages == [{"role": "user", "content": "Hi"}]
        assert req.model == "gpt-4o"
        assert req.temperature == 0.7  # 默认值
        assert req.maxTokens == 4096  # 默认值

    def test_custom_values(self):
        req = ChatRequest(
            messages=[],
            model="claude-3",
            baseUrl="https://api.anthropic.com",
            apiKey="sk-test",
            temperature=0.9,
            maxTokens=2048,
        )
        assert req.apiKey == "sk-test"
        assert req.temperature == 0.9
        assert req.maxTokens == 2048


class TestChatResponse:
    """测试 ChatResponse Pydantic 模型"""

    def test_minimal_response(self):
        resp = ChatResponse(reply="Hello", model="gpt-4o")
        assert resp.reply == "Hello"
        assert resp.model == "gpt-4o"
        assert resp.usage is None
        assert resp.reasoning is None
        assert resp.tools == []
        assert resp.rounds == 0

    def test_full_response(self):
        resp = ChatResponse(
            reply="Hello!",
            model="claude-3",
            usage={"prompt_tokens": 10, "completion_tokens": 20},
            reasoning="thinking",
            tools=[{"name": "search", "result": "data"}],
            rounds=3,
        )
        assert resp.usage["prompt_tokens"] == 10
        assert resp.reasoning == "thinking"
        assert len(resp.tools) == 1
        assert resp.rounds == 3


class TestReadSettings:
    """测试 _read_settings"""

    def test_settings_file_not_found(self, tmp_path):
        import backend.chat_api as chat_api
        original = chat_api.SETTINGS_FILE
        chat_api.SETTINGS_FILE = tmp_path / "nonexistent.json"
        try:
            result = _read_settings()
            assert result == {}
        finally:
            chat_api.SETTINGS_FILE = original

    def test_settings_file_valid(self, sample_settings_json):
        import backend.chat_api as chat_api
        original = chat_api.SETTINGS_FILE
        chat_api.SETTINGS_FILE = sample_settings_json
        try:
            result = _read_settings()
            assert "agentParams" in result
            assert result["agentParams"]["maxToolRounds"] == 6
        finally:
            chat_api.SETTINGS_FILE = original

    def test_settings_file_invalid_json(self, tmp_path):
        import backend.chat_api as chat_api
        bad_file = tmp_path / "bad_settings.json"
        bad_file.write_text("{invalid json")
        original = chat_api.SETTINGS_FILE
        chat_api.SETTINGS_FILE = bad_file
        try:
            result = _read_settings()
            assert result == {}
        finally:
            chat_api.SETTINGS_FILE = original

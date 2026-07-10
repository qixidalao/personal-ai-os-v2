"""
单元测试 — ToolRegistry 工具注册中心
"""

import pytest
from tools import ToolRegistry, ToolSpec


class TestToolRegistry:
    """ToolRegistry 核心功能测试"""

    def setup_method(self):
        """每个测试前隔离注册表，同时保留应用的原始工具。"""
        self._original_tools = ToolRegistry._tools.copy()
        ToolRegistry._tools.clear()

    def teardown_method(self):
        """恢复原始工具，避免测试状态泄漏到后续模块。"""
        ToolRegistry._tools.clear()
        ToolRegistry._tools.update(self._original_tools)

    def test_register_decorator(self):
        """测试装饰器方式注册工具"""
        @ToolRegistry.register("test_tool", "A test tool", "testing")
        def test_tool(param1: str, param2: int):
            """Do something"""
            return f"{param1}:{param2}"

        tool = ToolRegistry.get("test_tool")
        assert tool is not None
        assert tool.name == "test_tool"
        assert tool.description == "A test tool"
        assert tool.category == "testing"
        assert tool.enabled is True

    def test_register_without_category(self):
        """测试注册时不指定 category，应使用默认值 'custom'"""
        @ToolRegistry.register("custom_tool", "Custom tool")
        def custom_tool():
            pass

        tool = ToolRegistry.get("custom_tool")
        assert tool.category == "custom"

    def test_get_nonexistent_tool(self):
        """测试获取未注册的工具返回 None"""
        tool = ToolRegistry.get("nonexistent_tool")
        assert tool is None

    def test_call_registered_tool(self):
        """测试调用已注册的工具"""
        @ToolRegistry.register("add", "Add two numbers", "math")
        def add(a: int, b: int) -> int:
            return a + b

        result = ToolRegistry.call("add", a=3, b=7)
        assert result == 10

    def test_call_nonexistent_tool_raises(self):
        """测试调用未注册的工具应抛出 ValueError"""
        with pytest.raises(ValueError, match="未注册"):
            ToolRegistry.call("ghost_tool")

    def test_call_disabled_tool_raises(self):
        """测试调用已禁用的工具应抛出 ValueError"""

        @ToolRegistry.register("secret_tool", "Secret", "hidden")
        def secret_tool():
            return "secret"

        ToolRegistry.disable("secret_tool")
        with pytest.raises(ValueError, match="已禁用"):
            ToolRegistry.call("secret_tool")

    def test_list_all_tools(self):
        """测试列出所有已启用的工具"""
        @ToolRegistry.register("tool_a", "Tool A", "alpha")
        def tool_a():
            pass

        @ToolRegistry.register("tool_b", "Tool B", "beta")
        def tool_b():
            pass

        @ToolRegistry.register("tool_c", "Tool C", "alpha")
        def tool_c():
            pass

        all_tools = ToolRegistry.list()
        assert len(all_tools) == 3

    def test_list_by_category(self):
        """测试按 category 筛选工具列表"""

        @ToolRegistry.register("tool_a", "Alpha tool", "alpha")
        def tool_a():
            pass

        @ToolRegistry.register("tool_b", "Beta tool", "beta")
        def tool_b():
            pass

        alpha_tools = ToolRegistry.list("alpha")
        beta_tools = ToolRegistry.list("beta")
        gamma_tools = ToolRegistry.list("gamma")

        assert len(alpha_tools) == 1
        assert alpha_tools[0].name == "tool_a"
        assert len(beta_tools) == 1
        assert beta_tools[0].name == "tool_b"
        assert len(gamma_tools) == 0

    def test_list_excludes_disabled(self):
        """测试列出的工具不应包含已禁用的"""

        @ToolRegistry.register("enabled_tool", "Enabled", "alpha")
        def enabled_tool():
            pass

        @ToolRegistry.register("disabled_tool", "Disabled", "alpha")
        def disabled_tool():
            pass

        ToolRegistry.disable("disabled_tool")
        all_tools = ToolRegistry.list()
        names = [t.name for t in all_tools]
        assert "enabled_tool" in names
        assert "disabled_tool" not in names

    def test_enable_disable_toggle(self):
        """测试 enable/disable 切换"""

        @ToolRegistry.register("toggle_tool", "Toggle", "testing")
        def toggle_tool():
            pass

        assert ToolRegistry.get("toggle_tool").enabled is True

        ToolRegistry.disable("toggle_tool")
        assert ToolRegistry.get("toggle_tool").enabled is False
        assert len(ToolRegistry.list()) == 0

        ToolRegistry.enable("toggle_tool")
        assert ToolRegistry.get("toggle_tool").enabled is True
        assert len(ToolRegistry.list()) == 1

    def test_double_register_overwrites(self):
        """测试重复注册同名工具应覆盖"""

        @ToolRegistry.register("dup", "First", "alpha")
        def dup_first():
            return "first"

        @ToolRegistry.register("dup", "Second", "beta")
        def dup_second():
            return "second"

        assert ToolRegistry.get("dup").description == "Second"
        assert ToolRegistry.get("dup").category == "beta"
        result = ToolRegistry.call("dup")
        assert result == "second"

    def test_tool_spec_attributes(self):
        """测试 ToolSpec 数据类的属性完整性"""

        def handler():
            pass

        spec = ToolSpec(
            name="test_spec",
            description="Spec description",
            parameters={"type": "object", "properties": {}},
            handler=handler,
            category="testing",
            timeout=60,
        )
        assert spec.name == "test_spec"
        assert spec.description == "Spec description"
        assert spec.timeout == 60
        assert spec.enabled is True

    def test_tool_with_multiple_parameters(self):
        """
        测试注册带多个参数的工具。
        注意：ToolRegistry.call(name, **kwargs) 中 name 既用于查工具名
        又可能出现在 kwargs 里，因此参数名避开 'name'。
        """

        @ToolRegistry.register("multi_param", "Multi-param tool", "testing")
        def multi_param(username: str, age: int, active: bool):
            return {"username": username, "age": age, "active": active}

        result = ToolRegistry.call("multi_param", username="Alice", age=30, active=True)
        assert result["username"] == "Alice"
        assert result["age"] == 30
        assert result["active"] is True

    def test_list_returns_copies_or_same_objects(self):
        """测试 list 返回的对象不被外部修改影响注册表"""

        @ToolRegistry.register("immutable_test", "Immutable check", "testing")
        def imm():
            pass

        tools_before = ToolRegistry.list()
        # 尝试修改返回的列表
        tools_before.clear()

        tools_after = ToolRegistry.list()
        assert len(tools_after) == 1

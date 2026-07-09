"""
Tools 注册中心 — 万物皆插件
所有工具通过注册表统一管理
"""
from typing import Any, Callable, Dict, List, Optional, Type
from dataclasses import dataclass, field


@dataclass
class ToolSpec:
    """工具规格定义"""
    name: str
    description: str
    parameters: Dict
    handler: Callable
    enabled: bool = True
    category: str = "custom"
    timeout: int = 30


class ToolRegistry:
    """工具注册中心"""

    _tools: Dict[str, ToolSpec] = {}

    @classmethod
    def register(cls, name: str, description: str = "", category: str = "custom"):
        """注册工具装饰器"""
        def decorator(func):
            import inspect
            sig = inspect.signature(func)
            params = []
            for p_name, p_param in sig.parameters.items():
                if p_name == "self":
                    continue
                param_info = {
                    "name": p_name,
                    "type": str(p_param.annotation) if p_param.annotation != inspect.Parameter.empty else "string",
                    "required": p_param.default == inspect.Parameter.empty,
                }
                params.append(param_info)

            cls._tools[name] = ToolSpec(
                name=name,
                description=description or func.__doc__ or "",
                parameters={"type": "object", "properties": {p["name"]: {"type": p["type"]} for p in params}},
                handler=func,
                category=category,
            )
            return func
        return decorator

    @classmethod
    def get(cls, name: str) -> Optional[ToolSpec]:
        return cls._tools.get(name)

    @classmethod
    def list(cls, category: Optional[str] = None) -> List[ToolSpec]:
        if category:
            return [t for t in cls._tools.values() if t.category == category and t.enabled]
        return [t for t in cls._tools.values() if t.enabled]

    @classmethod
    def call(cls, name: str, **kwargs) -> Any:
        tool = cls.get(name)
        if not tool:
            raise ValueError(f"工具 '{name}' 未注册")
        if not tool.enabled:
            raise ValueError(f"工具 '{name}' 已禁用")
        return tool.handler(**kwargs)

    @classmethod
    def enable(cls, name: str):
        if name in cls._tools:
            cls._tools[name].enabled = True

    @classmethod
    def disable(cls, name: str):
        if name in cls._tools:
            cls._tools[name].enabled = False

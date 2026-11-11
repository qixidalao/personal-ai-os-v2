"""Tools 注册中心 —— 工具契约（显式 JSON Schema）+ 注册 + 校验 + 调用。

P0 工具契约层
-------------
* 每个工具由 :class:`ToolSpec` 描述：``input_schema``（JSON Schema draft 2020-12）、
  ``permissions``、``timeout``、``max_output_bytes`` 等；
* 注册时优先使用 ``tools/schemas.py`` 中的同名显式 schema
  （装饰器 ``schema=None`` 时自动查 ``schemas.SCHEMAS``）；
* 没有显式 schema 时回退用函数签名生成合法 JSON 类型
  （str→string、int→integer、float→number、bool→boolean、list→array、dict→object），
  ``required`` 由无默认值参数决定，绝不出现 ``"<class 'str'>"``；
* :meth:`ToolRegistry.call` 先做参数校验再执行 handler：非法类型、缺失必填、
  未知参数、enum/边界违规都在进入 handler 之前被拒绝（``ToolValidationError``）。

向后兼容
--------
* ``@ToolRegistry.register("name", "desc", "category")`` 用法保持不变；
* ``ToolSpec.parameters`` 属性继续返回 ``input_schema``，
  供 ``backend/settings_api.py``、``backend/onebot/adapter.py`` 等旧代码读取；
* ``ToolSpec(parameters=...)`` 旧式构造继续可用。

jsonschema 是可选依赖：已安装（>=4.x 的 Draft 2020-12 校验器）时使用标准校验，
未安装或 schema 无法编译时自动回退到内置校验（required / additionalProperties /
type / enum / 数值与字符串边界），行为保持可预期。
"""
from __future__ import annotations

import copy
import inspect
import json
import re
import types
import typing
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional

# ---------------------------------------------------------------------------
# 显式 schema / 权限 / 限额（来自 tools/schemas.py；缺失时安静降级）
# ---------------------------------------------------------------------------
try:
    from tools import schemas as _schemas
except Exception:  # pragma: no cover - 允许 tools 包在缺少 schemas.py 时独立使用
    _schemas = None  # type: ignore[assignment]

_EXPLICIT_SCHEMAS: Dict[str, Dict[str, Any]] = dict(
    getattr(_schemas, "SCHEMAS", {}) or {}
)
_EXPLICIT_PERMISSIONS: Dict[str, List[str]] = dict(
    getattr(_schemas, "TOOL_PERMISSIONS", {}) or {}
)
_EXPLICIT_LIMITS: Dict[str, Dict[str, int]] = dict(
    getattr(_schemas, "TOOL_LIMITS", {}) or {}
)

#: ToolSpec.permissions 的合法取值
PERMISSION_VALUES: tuple[str, ...] = ("fs_read", "fs_write", "exec", "net", "media")
                                                                            # 中文：媒体

#: 未显式声明权限时的按分类回退（仅用于自定义工具）
_CATEGORY_PERMISSIONS: Dict[str, List[str]] = {
    "filesystem": ["fs_read", "fs_write"],
    # 中文：filesystem
    "shell": ["exec"],
    # 中文：shell
    "python": ["exec"],
    # 中文：python
    "search": ["net"],
    "browser": ["net"],
    "media": ["media"],
              # 中文：媒体
    # 中文：媒体
    "skills": ["fs_read"],
    # 中文：技能
}

#: 回退 schema 的 JSON 类型映射
_SIMPLE_JSON_TYPES: Dict[Any, str] = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    list: "array",
    tuple: "array",
    set: "array",
    frozenset: "array",
    dict: "object",
    bytes: "string",
    type(None): "null",
}

_STRING_JSON_TYPES: Dict[str, str] = {
    "str": "string",
    "string": "string",
    "int": "integer",
    "integer": "integer",
    "float": "number",
    "number": "number",
    "bool": "boolean",
    "boolean": "boolean",
    "list": "array",
    "array": "array",
    "tuple": "array",
    "set": "array",
    "dict": "object",
    "object": "object",
    "mapping": "object",
    "none": "null",
    "nonetype": "null",
}

# ---------------------------------------------------------------------------
# jsonschema（可选）
# ---------------------------------------------------------------------------
try:
    from jsonschema import Draft202012Validator as _Draft202012Validator  # type: ignore
    from jsonschema.exceptions import SchemaError as _JsonSchemaError  # type: ignore

    _JSONSCHEMA_AVAILABLE = True
except Exception:  # pragma: no cover - 未安装 jsonschema 时走内置校验
    _Draft202012Validator = None  # type: ignore[assignment]
    _JsonSchemaError = Exception  # type: ignore[assignment,misc]
    _JSONSCHEMA_AVAILABLE = False


# ---------------------------------------------------------------------------
# 异常
# ---------------------------------------------------------------------------
class ToolError(Exception):
    """工具层异常基类。"""


class ToolNotFoundError(ToolError, ValueError):
    """工具未注册。

    继承 ``ValueError`` 以兼容旧代码/旧测试里的 ``pytest.raises(ValueError)``。
    """

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"工具 '{name}' 未注册")


class ToolDisabledError(ToolError, ValueError):
    """工具已被禁用。"""

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"工具 '{name}' 已禁用")


class ToolSchemaError(ToolError, ValueError):
    """工具注册时 input_schema 不是合法 JSON Schema。"""

    def __init__(self, name: str, detail: str) -> None:
        self.name = name
        self.detail = detail
        super().__init__(f"工具 '{name}' 的 input_schema 非法: {detail}")


class ToolValidationError(ToolError, ValueError):
    """工具参数校验失败。

    ``errors`` 是字段级错误列表，每项形如::

        {"field": "timeout", "message": "30 is greater than the maximum of 5",
         "validator": "maximum"}

    ``arguments`` 是本次实际参与校验的参数（已做安全归一化）。
    """

    def __init__(
        self,
        name: str,
        errors: Iterable[Mapping[str, Any]],
        arguments: Optional[Mapping[str, Any]] = None,
    ) -> None:
        self.name = name
        self.tool_name = name
        self.errors: List[Dict[str, Any]] = [dict(item) for item in errors]
        self.arguments: Dict[str, Any] = dict(arguments or {})
        if self.errors:
            preview = "；".join(
                f"{item.get('field', '$')}: {item.get('message', '非法值')}"
                for item in self.errors[:5]
            )
            if len(self.errors) > 5:
                preview += f"；…共 {len(self.errors)} 处错误"
        else:
            preview = "参数不符合工具契约"
        super().__init__(f"工具 '{name}' 参数校验失败: {preview}")


# ---------------------------------------------------------------------------
# schema 工具函数
# ---------------------------------------------------------------------------
def _load_explicit_schemas() -> Dict[str, Dict[str, Any]]:
    """惰性加载 tools.schemas.SCHEMAS（防止导入顺序问题）。"""
    global _EXPLICIT_SCHEMAS, _EXPLICIT_PERMISSIONS, _EXPLICIT_LIMITS
    if _EXPLICIT_SCHEMAS:
        return _EXPLICIT_SCHEMAS
    try:
        from tools import schemas

        _EXPLICIT_SCHEMAS = dict(getattr(schemas, "SCHEMAS", {}) or {})
        _EXPLICIT_PERMISSIONS = dict(getattr(schemas, "TOOL_PERMISSIONS", {}) or {})
        _EXPLICIT_LIMITS = dict(getattr(schemas, "TOOL_LIMITS", {}) or {})
    except Exception:  # pragma: no cover
        _EXPLICIT_SCHEMAS = {}
    return _EXPLICIT_SCHEMAS


def _empty_object_schema() -> Dict[str, Any]:
    return {
        "type": "object",
        "properties": {},
        "required": [],
        "additionalProperties": False,
    }


def normalize_input_schema(schema: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    """补齐对象 schema 的必要字段并做深拷贝，保证不出现非法结构。"""
    if not isinstance(schema, Mapping) or not schema:
        return _empty_object_schema()
    result = copy.deepcopy(dict(schema))
    result.setdefault("type", "object")
    if not isinstance(result.get("properties"), dict):
        result["properties"] = {}
    if not isinstance(result.get("required"), list):
        result["required"] = []
    result.setdefault("additionalProperties", False)
    return result


def _json_type_for(annotation: Any) -> str:
    """把 Python 类型注解映射成合法 JSON Schema type（回退 schema 用）。"""
    if annotation is inspect.Parameter.empty or annotation is Any:
        return "string"
    if isinstance(annotation, str):
        # from __future__ import annotations 时注解是字符串
        text = annotation.strip()
        for candidate in text.replace("typing.", "").replace("Optional[", "").split("|"):
            candidate = candidate.strip().split("[")[0]
            mapped = _STRING_JSON_TYPES.get(candidate.lower())
            if mapped and mapped != "null":
                return mapped
        return "string"
    if isinstance(annotation, types.UnionType):  # X | Y
        for arg in typing.get_args(annotation):
            if arg is type(None):
                continue
            return _json_type_for(arg)
        return "string"
    origin = getattr(annotation, "__origin__", None)
    if origin is not None:
        if origin in (list, tuple, set, frozenset):
            return "array"
        if origin is dict:
            return "object"
        if origin is typing.Union:
            for arg in typing.get_args(annotation):
                if arg is type(None):
                    continue
                return _json_type_for(arg)
        return "string"
    if annotation in _SIMPLE_JSON_TYPES:
        return _SIMPLE_JSON_TYPES[annotation]
    name = getattr(annotation, "__name__", "")
    return _STRING_JSON_TYPES.get(str(name).lower(), "string")


def _json_default(value: Any) -> Any:
    """把 Python 默认值转成 JSON 可序列化值（失败时降级为字符串）。"""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    try:
        json.dumps(value)
    except Exception:  # noqa: BLE001
        return str(value)
    return value


def schema_from_signature(func: Callable[..., Any]) -> Dict[str, Any]:
    """用函数签名生成**合法**的 JSON Schema（无显式 schema 时的回退）。"""
    try:
        signature = inspect.signature(func)
    except (TypeError, ValueError):  # pragma: no cover - 内置函数等
        return _empty_object_schema()

    properties: Dict[str, Any] = {}
    required: List[str] = []
    for name, param in signature.parameters.items():
        if name in ("self", "cls"):
            continue
        if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
            continue
        prop: Dict[str, Any] = {"type": _json_type_for(param.annotation)}
        if param.default is inspect.Parameter.empty:
            required.append(name)
        else:
            prop["default"] = _json_default(param.default)
        properties[name] = prop
    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


def _normalize_permissions(
    permissions: Optional[Iterable[str]],
    *,
    name: str = "",
    category: str = "",
) -> List[str]:
    """校验并归一化权限标签；None 时按显式配置/分类回退。"""
    if permissions is None:
        if name and name in _EXPLICIT_PERMISSIONS:
            permissions = _EXPLICIT_PERMISSIONS[name]
        elif category in _CATEGORY_PERMISSIONS:
            permissions = _CATEGORY_PERMISSIONS[category]
    if permissions is None:
        return []
    if isinstance(permissions, str):
        permissions = [permissions]
    result: List[str] = []
    for item in permissions:
        if item not in PERMISSION_VALUES:
            raise ValueError(
                f"工具 '{name or category}' 声明了未知权限 {item!r}；"
                f"合法取值为 {', '.join(PERMISSION_VALUES)}"
            )
        if item not in result:
            result.append(item)
    return result


# ---------------------------------------------------------------------------
# ToolSpec  ｜ ToolSpec
# ---------------------------------------------------------------------------
class ToolSpec:
    """工具规格定义（P0 工具契约）。

    正式字段：``name``、``description``、``category``、``input_schema``、
    ``output_schema``（可选）、``permissions``、``timeout``（秒）、
    ``max_output_bytes``（字节）、``handler``、``enabled``。

    兼容字段/属性：``parameters``（= ``input_schema``）、``schema`` 别名，
    以兼容旧代码（settings_api / onebot adapter）与旧测试。
    """

    def __init__(
        self,
        name: str,
        description: str = "",
        category: str = "custom",
        *,
        input_schema: Optional[Mapping[str, Any]] = None,
        output_schema: Optional[Mapping[str, Any]] = None,
        permissions: Optional[Iterable[str]] = None,
        timeout: int = 30,
        max_output_bytes: int = 65536,
        handler: Optional[Callable[..., Any]] = None,
        enabled: bool = True,
        # 向后兼容：旧式 ToolSpec(parameters=...) 构造
        parameters: Optional[Mapping[str, Any]] = None,
        schema: Optional[Mapping[str, Any]] = None,
    ) -> None:
        raw_schema = input_schema
        if raw_schema is None:
            raw_schema = parameters if parameters is not None else schema
        self.name = name
        self.description = description or ""
        self.category = category or "custom"
        self.input_schema: Dict[str, Any] = normalize_input_schema(raw_schema)
        self.output_schema: Optional[Dict[str, Any]] = (
            copy.deepcopy(dict(output_schema)) if isinstance(output_schema, Mapping) else None
        )
        self.permissions: List[str] = _normalize_permissions(
            permissions, name=name, category=self.category
        )
        self.timeout: int = int(timeout) if timeout is not None else 30
        self.max_output_bytes: int = (
            int(max_output_bytes) if max_output_bytes is not None else 65536
        )
        self.handler: Optional[Callable[..., Any]] = handler
        self.enabled: bool = bool(enabled)

    # -- 旧接口兼容 ------------------------------------------------------
    @property
    def parameters(self) -> Dict[str, Any]:
        """旧字段名：等价于 ``input_schema``（JSON Schema）。"""
        return self.input_schema

    @property
    def schema(self) -> Dict[str, Any]:
        """旧字段名：等价于 ``input_schema``。"""
        return self.input_schema

    # -- 序列化 ----------------------------------------------------------
    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "input_schema": copy.deepcopy(self.input_schema),
            "permissions": list(self.permissions),
            "timeout": self.timeout,
            "max_output_bytes": self.max_output_bytes,
            "enabled": self.enabled,
        }
        if self.output_schema is not None:
            data["output_schema"] = copy.deepcopy(self.output_schema)
        return data

    def __repr__(self) -> str:  # pragma: no cover - 调试用
        return (
            f"ToolSpec(name={self.name!r}, category={self.category!r}, "
            f"permissions={self.permissions!r}, timeout={self.timeout}, "
            f"enabled={self.enabled})"
        )


# ---------------------------------------------------------------------------
# 校验辅助
# ---------------------------------------------------------------------------
_INT_TEXT = re.compile(r"^[+-]?\d+$")
_NUMBER_TEXT = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$")


def _coerce_value(prop: Mapping[str, Any], value: Any) -> Any:
    """对少量常见模型输出做安全归一化（"30"→30、"true"→True、30.0→30）。"""
    prop_type = prop.get("type")
    if isinstance(prop_type, list):
        return value
    if prop_type == "integer":
        if isinstance(value, bool):
            return value
        if isinstance(value, float) and value.is_integer():
            return int(value)
        if isinstance(value, str):
            text = value.strip()
            if _INT_TEXT.match(text):
                try:
                    return int(text)
                except ValueError:  # pragma: no cover - 正则已限定
                    pass
        return value
    if prop_type == "number":
        if isinstance(value, str):
            text = value.strip()
            if _NUMBER_TEXT.match(text):
                try:
                    return float(text)
                except ValueError:  # pragma: no cover
                    pass
        return value
    if prop_type == "boolean" and isinstance(value, str):
        text = value.strip().lower()
        if text in ("true", "false"):
            return text == "true"
    return value


def _matches_type(type_name: Any, value: Any) -> bool:
    """内置校验使用的严格 JSON 类型判断（bool 不算 integer/number）。"""
    if isinstance(type_name, list):
        return any(_matches_type(item, value) for item in type_name)
    if type_name == "string":
        return isinstance(value, str)
    if type_name == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if type_name == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if type_name == "boolean":
        return isinstance(value, bool)
    if type_name == "array":
        return isinstance(value, list)
    if type_name == "object":
        return isinstance(value, dict)
    if type_name == "null":
        return value is None
    return True


def _enum_contains(enum_values: Iterable[Any], value: Any) -> bool:
    """enum 比较：区分 True/1，但允许 int/float 数值等价。"""
    for item in enum_values:
        if type(item) is type(value) and item == value:
            return True
        if (
            isinstance(item, (int, float))
            and not isinstance(item, bool)
            and isinstance(value, (int, float))
            and not isinstance(value, bool)
            and float(item) == float(value)
        ):
            return True
    return False


def _join_path(path: str, key: Any) -> str:
    key_text = str(key)
    return f"{path}.{key_text}" if path else key_text


def _builtin_errors(
    schema: Mapping[str, Any],
    value: Any,
    path: str = "",
) -> List[Dict[str, Any]]:
    """内置 JSON Schema 校验（jsonschema 不可用时的回退）。"""
    errors: List[Dict[str, Any]] = []
    if not isinstance(schema, Mapping):
        return errors
    field = path or "$"

    enum_values = schema.get("enum")
    if isinstance(enum_values, list) and enum_values and not _enum_contains(enum_values, value):
        errors.append(
            {
                "field": field,
                "message": f"取值必须是 {enum_values!r} 之一，实际为 {value!r}",
                "validator": "enum",
            }
        )

    expected_type = schema.get("type")
    if expected_type is not None and not _matches_type(expected_type, value):
        errors.append(
            {
                "field": field,
                "message": f"类型应为 {expected_type}，实际为 {type(value).__name__}",
                "validator": "type",
            }
        )
        return errors

    if isinstance(value, str):
        if isinstance(schema.get("minLength"), int) and len(value) < schema["minLength"]:
            errors.append(
                {
                    "field": field,
                    "message": f"长度不能小于 {schema['minLength']}（当前 {len(value)}）",
                    "validator": "minLength",
                }
            )
        if isinstance(schema.get("maxLength"), int) and len(value) > schema["maxLength"]:
            errors.append(
                {
                    "field": field,
                    "message": f"长度不能大于 {schema['maxLength']}（当前 {len(value)}）",
                    "validator": "maxLength",
                }
            )
        pattern = schema.get("pattern")
        if isinstance(pattern, str):
            try:
                matched = re.search(pattern, value) is not None
            except re.error:  # pragma: no cover - 非法 pattern 由注册期校验拦截
                matched = True
            if not matched:
                errors.append(
                    {
                        "field": field,
                        "message": f"格式不匹配 pattern {pattern!r}",
                        "validator": "pattern",
                    }
                )

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if isinstance(schema.get("minimum"), (int, float)) and value < schema["minimum"]:
            errors.append(
                {
                    "field": field,
                    "message": f"取值不能小于 {schema['minimum']}",
                    "validator": "minimum",
                }
            )
        if isinstance(schema.get("maximum"), (int, float)) and value > schema["maximum"]:
            errors.append(
                {
                    "field": field,
                    "message": f"取值不能大于 {schema['maximum']}",
                    "validator": "maximum",
                }
            )

    if isinstance(value, dict):
        properties = schema.get("properties")
        properties = properties if isinstance(properties, dict) else {}
        required = schema.get("required")
        required = required if isinstance(required, list) else []
        for key in required:
            if key not in value:
                errors.append(
                    {
                        "field": _join_path(path, key),
                        "message": f"缺少必填参数 '{key}'",
                        "validator": "required",
                    }
                )
        if schema.get("additionalProperties") is False:
            for key in value:
                if key not in properties:
                    errors.append(
                        {
                            "field": _join_path(path, key),
                            "message": f"未知参数 '{key}' 不被允许",
                            "validator": "additionalProperties",
                        }
                    )
        for key, item in value.items():
            if key in properties:
                errors.extend(
                    _builtin_errors(properties[key], item, _join_path(path, key))
                )
    elif isinstance(value, list):
        items_schema = schema.get("items")
        if isinstance(items_schema, Mapping):
            for index, item in enumerate(value):
                errors.extend(
                    _builtin_errors(items_schema, item, f"{path}[{index}]")
                )
        if isinstance(schema.get("minItems"), int) and len(value) < schema["minItems"]:
            errors.append(
                {
                    "field": field,
                    "message": f"元素数量不能小于 {schema['minItems']}",
                    "validator": "minItems",
                }
            )
        if isinstance(schema.get("maxItems"), int) and len(value) > schema["maxItems"]:
            errors.append(
                {
                    "field": field,
                    "message": f"元素数量不能大于 {schema['maxItems']}",
                    "validator": "maxItems",
                }
            )
    return errors


def _json_schema_error_entries(
    raw_errors: Iterable[Any], arguments: Mapping[str, Any]
) -> List[Dict[str, Any]]:
    """把 jsonschema 的 ValidationError 转成字段级中文错误列表。"""
    entries: List[Dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    def add(field: str, message: str, validator: Any) -> None:
        key = (field, str(validator))
        if key in seen:
            return
        seen.add(key)
        entries.append({"field": field, "message": message, "validator": validator})

    for error in raw_errors:
        validator = error.validator
        if validator == "required":
            missing = [
                name
                for name in (error.validator_value or [])
                if isinstance(name, str) and name not in arguments
            ]
            if missing:
                for name in missing:
                    add(name, f"缺少必填参数 '{name}'", "required")
                continue
        if validator == "additionalProperties":
            schema_props = {}
            schema = getattr(error, "schema", None)
            if isinstance(schema, Mapping) and isinstance(schema.get("properties"), dict):
                schema_props = schema["properties"]
            extra_keys = [key for key in arguments if key not in schema_props]
            for key in extra_keys:
                add(str(key), f"未知参数 '{key}' 不被允许", "additionalProperties")
            if extra_keys:
                continue
        path = ".".join(str(part) for part in getattr(error, "absolute_path", ())) or "$"
        add(path, error.message, validator)
    return entries


# ---------------------------------------------------------------------------
# ToolRegistry  ｜ ToolRegistry
# ---------------------------------------------------------------------------
class ToolRegistry:
    """工具注册中心（类级单例注册表，import 副作用完成注册）。"""

    _tools: Dict[str, ToolSpec] = {}
    _validators: Dict[str, Any] = {}

    # ------------------------------------------------------------------
    # 注册
    # ------------------------------------------------------------------
    @classmethod
    def register(
        cls,
        name: str,
        description: str = "",
        category: str = "custom",
        schema: Optional[Mapping[str, Any]] = None,
        permissions: Optional[Iterable[str]] = None,
        timeout: int = 30,
        max_output_bytes: int = 65536,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """注册工具装饰器。

        用法::

            @ToolRegistry.register("shell_exec", "执行 Shell 命令", "shell")
            def shell_exec(command: str, timeout: int = 30) -> dict: ...

        * ``schema=None`` 时：先查 ``tools/schemas.py`` 的同名显式 schema，
          没有则用函数签名生成合法 JSON 类型；
        * ``permissions=None`` 时：先查 ``TOOL_PERMISSIONS``，再按 category 回退。
        """

        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            explicit = _load_explicit_schemas().get(name)
            resolved_schema = schema if schema is not None else explicit
            if resolved_schema is None:
                resolved_schema = schema_from_signature(func)
            normalized = normalize_input_schema(resolved_schema)
            cls._check_schema(name, normalized)
            resolved_description = description or (inspect.getdoc(func) or "")
            spec = ToolSpec(
                name=name,
                description=resolved_description,
                category=category,
                input_schema=normalized,
                permissions=permissions,
                timeout=timeout,
                max_output_bytes=max_output_bytes,
                handler=func,
            )
            cls._tools[name] = spec
            cls._validators.pop(name, None)
            return func

        return decorator

    @classmethod
    def _check_schema(cls, name: str, schema: Mapping[str, Any]) -> None:
        """注册期编译 schema（jsonschema 可用时），非法 schema 直接拒绝注册。"""
        if not _JSONSCHEMA_AVAILABLE or _Draft202012Validator is None:
            return
        try:
            _Draft202012Validator.check_schema(schema)
        except Exception as exc:  # noqa: BLE001
            raise ToolSchemaError(name, str(exc)) from exc

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------
    @classmethod
    def get(cls, name: str) -> Optional[ToolSpec]:
        """按名称获取工具（包含已禁用的）。"""
        return cls._tools.get(name)

    @classmethod
    def has(cls, name: str) -> bool:
        return name in cls._tools

    @classmethod
    def list(
        cls, category: Optional[str] = None, *, enabled_only: bool = True
    ) -> List[ToolSpec]:
        """列出工具；默认只返回已启用的，可按 category 过滤。"""
        tools = [
            tool
            for tool in cls._tools.values()
            if (not category or tool.category == category)
        ]
        if enabled_only:
            tools = [tool for tool in tools if tool.enabled]
        return tools

    @classmethod
    def schema_for(cls, name: str) -> Optional[Dict[str, Any]]:
        """返回工具 input_schema 的深拷贝；工具不存在时返回 None。"""
        tool = cls.get(name)
        if tool is None:
            return None
        return copy.deepcopy(tool.input_schema)

    @classmethod
    def openai_tools(cls, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """输出 OpenAI function calling 的 tools 结构（含完整 schema）。"""
        result: List[Dict[str, Any]] = []
        for tool in cls.list(category=category):
            result.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": copy.deepcopy(tool.input_schema),
                    },
                }
            )
        return result

    # ------------------------------------------------------------------
    # 启停
    # ------------------------------------------------------------------
    @classmethod
    def enable(cls, name: str) -> bool:
        tool = cls.get(name)
        if tool is None:
            return False
        tool.enabled = True
        return True

    @classmethod
    def disable(cls, name: str) -> bool:
        tool = cls.get(name)
        if tool is None:
            return False
        tool.enabled = False
        return True

    # ------------------------------------------------------------------
    # 校验 + 调用
    # ------------------------------------------------------------------
    @classmethod
    def validate(cls, name: str, args: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
        """校验参数并返回归一化后的参数（可直接 ``handler(**result)``）。

        校验失败抛 :class:`ToolValidationError`（含字段级错误列表）；
        工具不存在抛 :class:`ToolNotFoundError`。
        """
        tool = cls.get(name)
        if tool is None:
            raise ToolNotFoundError(name)
        if args is None:
            arguments: Any = {}
        elif isinstance(args, Mapping):
            arguments = dict(args)
        else:
            raise ToolValidationError(
                name,
                [
                    {
                        "field": "$",
                        "message": f"参数必须是对象，实际为 {type(args).__name__}",
                        "validator": "type",
                    }
                ],
                {},
            )

        prepared = cls._prepare_arguments(tool.input_schema, arguments)
        errors = cls._collect_validation_errors(tool, prepared)
        if errors:
            raise ToolValidationError(name, errors, prepared)
        return prepared

    @classmethod
    def call(cls, name: str, **kwargs: Any) -> Any:
        """校验后执行工具。非法参数不会进入 handler。"""
        tool = cls.get(name)
        if tool is None:
            raise ToolNotFoundError(name)
        if not tool.enabled:
            raise ToolDisabledError(name)
        if tool.handler is None:  # pragma: no cover - 理论上不会出现
            raise ToolError(f"工具 '{name}' 没有绑定 handler")
        arguments = cls.validate(name, kwargs)
        result = tool.handler(**arguments)
        return cls._truncate_result(tool, result)

    # ------------------------------------------------------------------
    # 内部实现
    # ------------------------------------------------------------------
    @staticmethod
    def _prepare_arguments(
        schema: Mapping[str, Any], arguments: Mapping[str, Any]
    ) -> Dict[str, Any]:
        """安全归一化：只接收 schema 声明的键；可选参数传 null 视作未传。"""
        properties = schema.get("properties")
        properties = properties if isinstance(properties, dict) else {}
        required = schema.get("required")
        required_names = set(required) if isinstance(required, list) else set()
        prepared: Dict[str, Any] = {}
        for key, value in arguments.items():
            prop = properties.get(key)
            if value is None and key not in required_names and isinstance(prop, Mapping):
                continue
            if isinstance(prop, Mapping):
                value = _coerce_value(prop, value)
            prepared[key] = value
        return prepared

    @classmethod
    def _collect_validation_errors(
        cls, tool: ToolSpec, arguments: Mapping[str, Any]
    ) -> List[Dict[str, Any]]:
        validator = cls._validator_for(tool)
        if validator is not None:
            try:
                raw_errors = list(validator.iter_errors(arguments))
            except Exception:  # noqa: BLE001 - schema 运行期异常时回退内置校验
                raw_errors = None
            if raw_errors is not None:
                return _json_schema_error_entries(raw_errors, arguments)
        return _builtin_errors(tool.input_schema, arguments)

    @classmethod
    def _validator_for(cls, tool: ToolSpec) -> Any:
        if not _JSONSCHEMA_AVAILABLE or _Draft202012Validator is None:
            return None
        cached = cls._validators.get(tool.name)
        if cached is not None:
            return cached if cached is not False else None
        try:
            validator = _Draft202012Validator(tool.input_schema)
        except Exception:  # noqa: BLE001 - 非法 schema 回退内置校验
            cls._validators[tool.name] = False
            return None
        cls._validators[tool.name] = validator
        return validator

    @classmethod
    def _truncate_result(cls, tool: ToolSpec, result: Any) -> Any:
        """按 ``max_output_bytes`` 截断过长的字符串/字节结果（仅展示层兜底）。"""
        try:
            limit = int(tool.max_output_bytes or 0)
        except (TypeError, ValueError):
            limit = 0
        if limit <= 0:
            return result
        if isinstance(result, str):
            data = result.encode("utf-8", "ignore")
                                          # 中文：忽略
            if len(data) <= limit:
                return result
            return (
                data[:limit].decode("utf-8", "ignore")
                                             # 中文：忽略
                + "\n…[结果已按 max_output_bytes 截断]"
            )
        if isinstance(result, (bytes, bytearray)):
            if len(result) <= limit:
                return result
            return bytes(result[:limit]) + "…[结果已按 max_output_bytes 截断]".encode()
        return result

    # ------------------------------------------------------------------
    # 测试/运维辅助
    # ------------------------------------------------------------------
    @classmethod
    def clear(cls) -> None:
        """清空注册表（测试用；生产代码不要调用）。"""
        cls._tools.clear()
        cls._validators.clear()

    @classmethod
    def snapshot(cls) -> Dict[str, Dict[str, Any]]:
        """返回所有工具的契约快照（用于设置页展示/审计）。"""
        return {name: tool.to_dict() for name, tool in cls._tools.items()}


__all__ = [
    "ToolRegistry",
    # 中文：ToolRegistry
    "ToolSpec",
    # 中文：ToolSpec
    "ToolError",
    "ToolNotFoundError",
    "ToolDisabledError",
    "ToolSchemaError",
    "ToolValidationError",
    "PERMISSION_VALUES",
    "normalize_input_schema",
    "schema_from_signature",
]

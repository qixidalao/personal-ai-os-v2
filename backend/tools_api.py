"""
Personal AI OS — Agent 工具调用 API

提供真实可用的工具列表与工具调用端点：
- GET  /api/v1/tools
- POST /api/v1/tools/call

工具注册来自项目根目录 tools.ToolRegistry；启用状态优先读取 storage/settings.json 的 agentTools。
"""
from __future__ import annotations

import asyncio
import inspect
import json
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger
import uuid

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from runtime.approvals import approval_timeout, decide, get_approval_store
from runtime.approvals.store import args_hash
from pydantic import BaseModel, Field
# 导入模块会触发 @ToolRegistry.register 装饰器注册
from tools import ToolRegistry, ToolSpec
import tools.filesystem  # noqa: F401
import tools.search  # noqa: F401
import tools.shell  # noqa: F401
import tools.browser  # noqa: F401
import tools.python  # noqa: F401
import tools.skills  # noqa: F401
import tools.media  # noqa: F401

router = APIRouter(prefix="/api/v1/tools", tags=["tools"])

SETTINGS_FILE = Path("storage/settings.json")
class ToolCallRequest(BaseModel):
    name: str = Field(..., description="工具名称")
    arguments: dict[str, Any] = Field(default_factory=dict, description="工具参数")


class ToolCallCompatRequest(BaseModel):
    tool: str | None = None
    name: str | None = None
    args: dict[str, Any] | None = None
    arguments: dict[str, Any] | None = None
    approval_id: str | None = Field(None, description="已批准的审批 id（批准后重试时携带）")
    session_id: str | None = Field(None, description="可选会话 id，用于会话级授权")


def _read_settings() -> dict[str, Any]:
    if not SETTINGS_FILE.exists():
        return {}
    try:
        return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _settings_tool_map() -> dict[str, dict[str, Any]]:
    settings = _read_settings()
    tools = settings.get("agentTools", [])
    if not isinstance(tools, list):
        return {}
    result: dict[str, dict[str, Any]] = {}
    for item in tools:
        if isinstance(item, dict) and isinstance(item.get("name"), str):
            result[item["name"]] = item
    return result


def _jsonable(value: Any) -> Any:
    """把工具返回转成 JSON 可序列化结构。"""
    try:
        json.dumps(value, ensure_ascii=False)
        return value
    except TypeError:
        if isinstance(value, Path):
            return str(value)
        if isinstance(value, (set, tuple)):
            return list(value)
        if hasattr(value, "dict"):
            return value.dict()
        if hasattr(value, "model_dump"):
            return value.model_dump()
        return str(value)


def _type_name(annotation: Any) -> str:
    if annotation is inspect.Parameter.empty:
        return "string"
    if annotation in (str, "str"):
        return "string"
    if annotation in (int, "int"):
        return "integer"
    if annotation in (float, "float"):
        return "number"
    if annotation in (bool, "bool"):
        return "boolean"
    if annotation in (dict, "dict"):
        return "object"
    if annotation in (list, "list"):
        return "array"
    return "string"

def _schema_from_handler(tool: ToolSpec) -> dict[str, Any]:
    sig = inspect.signature(tool.handler)
    properties: dict[str, Any] = {}
    required: list[str] = []
    for name, param in sig.parameters.items():
        if name == "self":
            continue
        properties[name] = {"type": _type_name(param.annotation)}
        if param.default is not inspect.Parameter.empty:
            properties[name]["default"] = param.default
        else:
            required.append(name)
    return {"type": "object", "properties": properties, "required": required}


def _tool_to_dict(tool: ToolSpec, configured: dict[str, Any] | None = None) -> dict[str, Any]:
    configured = configured or {}
    enabled = bool(configured.get("enabled", tool.enabled))
    description = configured.get("description") or tool.description
    # P0：显式 JSON Schema 是唯一契约来源；settings 里的旧 schema 只在工具没有显式契约时兜底
    explicit = getattr(tool, "input_schema", None)
    configured_schema = configured.get("schema")
    try:
        if explicit:
            schema_obj = explicit
        elif isinstance(configured_schema, str) and configured_schema.strip():
            schema_obj = json.loads(configured_schema)
        else:
            schema_obj = _schema_from_handler(tool)
    except Exception:
        schema_obj = explicit or _schema_from_handler(tool)
    return {
        "name": tool.name,
        "description": description,
        "category": tool.category,
        "enabled": enabled,
        "schema": schema_obj,
        "registered": True,
    }


def _normalise_tool_name(name: str) -> str:
    aliases = {
        "file_read": "file_read",
        "read_file": "file_read",
    }
    return aliases.get(name, name)


def _normalise_args(name: str, args: dict[str, Any]) -> dict[str, Any]:
    clean = dict(args or {})
    if name == "shell_exec" and "cmd" in clean and "command" not in clean:
        clean["command"] = clean.pop("cmd")
    return clean


def _ensure_enabled(name: str):
    configured = _settings_tool_map()
    if name in configured and configured[name].get("enabled") is False:
        raise HTTPException(status_code=403, detail=f"工具 '{name}' 已在设置中禁用")


@router.get("")
async def list_tools(category: str | None = None, enabled_only: bool = False):
    """列出真实已注册工具，并融合设置页启用状态。"""
    configured = _settings_tool_map()
    tools = []
    for tool in ToolRegistry.list(category=None):
        if category and tool.category != category:
            continue
        info = _tool_to_dict(tool, configured.get(tool.name))
        if enabled_only and not info["enabled"]:
            continue
        tools.append(info)

    # settings 里存在但没有真实注册的，也标出来，方便排错
    registered_names = {t["name"] for t in tools}
    for name, cfg in configured.items():
        normalised = _normalise_tool_name(name)
        if name in registered_names or normalised in registered_names:
            continue
        if enabled_only and not cfg.get("enabled", True):
            continue
        tools.append({
            "name": name,
            "description": cfg.get("description", ""),
            "category": "configured",
            "enabled": bool(cfg.get("enabled", True)),
            "schema": cfg.get("schema"),
            "registered": False,
        })

    logger.info(f"📋 工具列表查询: {len(tools)} 个 (enabled_only={enabled_only}, category={category})")
    return {"tools": tools, "count": len(tools), "time": datetime.now().isoformat()}


@router.get("/{name}")
async def get_tool(name: str):
    """查看单个工具详情。"""
    name = _normalise_tool_name(name)
    tool = ToolRegistry.get(name)
    if not tool:
        logger.warning(f"⚠️ GET /api/v1/tools/{name} → 未注册")
        raise HTTPException(status_code=404, detail=f"工具 '{name}' 未注册")
    result = {"tool": _tool_to_dict(tool, _settings_tool_map().get(name))}
    logger.info(f"🔍 GET /api/v1/tools/{name} → ok")
    return result


@router.post("/call")
async def call_tool(payload: ToolCallCompatRequest):
    """调用工具。兼容 name/arguments 与 tool/args 两种入参。"""
    raw_name = payload.name or payload.tool
    if not raw_name:
        raise HTTPException(status_code=400, detail="缺少工具名称 name/tool")
    name = _normalise_tool_name(raw_name)
    args = payload.arguments if payload.arguments is not None else payload.args
    args = _normalise_args(name, args or {})

    tool = ToolRegistry.get(name)
    if not tool:
        logger.warning(f"⚠️ POST /api/v1/tools/call → {raw_name} 未注册")
        raise HTTPException(status_code=404, detail=f"工具 '{raw_name}' 未注册")
    _ensure_enabled(name)

    # ── P3：工具中心手动执行同样走三档权限 / 审批 ─────────────────────
    decision = decide(name, args, session_id=payload.session_id)
    if decision.kind == "deny":
        logger.warning(f"⛔ 工具中心调用被策略拒绝: {name} ({decision.reason})")
        raise HTTPException(status_code=403, detail=f"策略拒绝：{decision.reason}")

    used_approval: str | None = None
    approval_store = get_approval_store()
    if decision.kind == "confirm":
        if payload.approval_id:
            record = approval_store.get(payload.approval_id)
            if (
                not record
                or record.get("status") != "approved"
                or record.get("tool") != name
                or record.get("args_hash") != args_hash(args)
            ):
                raise HTTPException(status_code=403, detail="审批无效、已过期或参数不匹配")
            used_approval = payload.approval_id
        else:
            record = approval_store.create(
                run_id=f"tools-{uuid.uuid4().hex[:8]}",
                tool_call_id=f"manual-{uuid.uuid4().hex[:8]}",
                tool=name,
                args=args,
                risk=decision.risk,
                timeout_s=approval_timeout(),
                session_id=payload.session_id,
            )
            logger.info(f"🔐 工具中心调用需要审批: {name} approval={record['id']}")
            return JSONResponse(
                status_code=202,
                content={
                    "ok": False,
                    "status": "approval_required",
                    "permission": "confirm",
                    "approval": record,
                },
            )

    logger.info(f"🛠️ POST /api/v1/tools/call → {name} args={json.dumps(args, ensure_ascii=False)}")
    try:
        result = await asyncio.to_thread(ToolRegistry.call, name, **args)
        if used_approval:
            approval_store.consume(used_approval)
        logger.info(f"✅ {name} 调用成功 result_len={len(str(result))}")
        return {
            "ok": True,
            "name": name,
            "arguments": args,
            "result": _jsonable(result),
            "permission": "approved" if used_approval else "allow",
            "time": datetime.now().isoformat(),
        }
    except TypeError as exc:
        logger.error(f"❌ {name} 参数错误: {exc}")
        raise HTTPException(status_code=400, detail=f"参数错误：{exc}") from exc
    except HTTPException:
        raise
    except Exception as exc:
        from tools import ToolValidationError

        if isinstance(exc, ToolValidationError):
            logger.warning(f"⛔ {name} 参数契约校验失败: {exc}")
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        try:
            from runtime.execution import WorkspaceViolation

            if isinstance(exc, WorkspaceViolation):
                logger.warning(f"⛔ {name} 工作区越界: {exc}")
                raise HTTPException(status_code=403, detail=str(exc)) from exc
        except ImportError:
            pass
        logger.error(f"❌ {name} 调用异常: {exc}")
        return {
            "ok": False,
            "name": name,
            "arguments": args,
            "error": str(exc),
            "traceback": traceback.format_exc(limit=8),
            "time": datetime.now().isoformat(),
        }

@router.get("/spills/{session_id}/{filename}")
async def read_spill(session_id: str, filename: str):
    """按定位符读取溢出存储的完整工具结果。

    locator 格式: spill://<session_id>/<filename>
    对应 URL:     /api/v1/tools/spills/<session_id>/<filename>
    """
    from runtime.memory.spill_store import SpillStore, LOCATOR_PREFIX

    store = SpillStore()
    locator = f"{LOCATOR_PREFIX}{session_id}/{filename}"
    content = store.resolve(locator)
    if content is None:
        raise HTTPException(status_code=404, detail=f"spill 内容不存在: {locator}")
    return {"locator": locator, "content": content}


@router.get("/spills")
async def list_spills(session_id: str = "default", limit: int = 20):
    """列出某会话的 spill 定位符（按时间倒序）。"""
    from runtime.memory.spill_store import SpillStore

    store = SpillStore()
    refs = store.list_refs(session_id=session_id, limit=limit)
    return {"session_id": session_id, "refs": refs}

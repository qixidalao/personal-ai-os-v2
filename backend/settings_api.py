"""
Personal AI OS — 设置页面配置落盘 API
所有前端设置数据持久化到 storage/settings.json

工具列表自动从 ToolRegistry 扫描，settings.json 只存启用/禁用状态。
"""
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin
import json

import httpx
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

# 导入 ToolRegistry 并触发所有工具模块注册，实现自动扫描
from tools import ToolRegistry
import tools.filesystem  # noqa: F401
import tools.search      # noqa: F401
import tools.shell       # noqa: F401
import tools.browser     # noqa: F401
import tools.python      # noqa: F401
import tools.skills       # noqa: F401

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])

STORAGE_DIR = Path("storage")
STORAGE_DIR.mkdir(parents=True, exist_ok=True)
SETTINGS_FILE = STORAGE_DIR / "settings.json"
USER_SETTINGS_DIR = STORAGE_DIR / "users"


class ProviderModelsRequest(BaseModel):
    baseUrl: str
    key: str = ""


def _default_settings() -> dict:
    """返回默认配置，agentTools 为空数组，由 _read_settings 自动扫描合并。"""
    return {
        "params": {"temperature": 0.7, "topP": 0.9, "maxTokens": 8192, "presencePenalty": 0},
        "streaming": True,
        "providers": [],
        "prompts": [
            {"name": "通用助手", "content": "你是 Personal AI OS 的 AI 助手。", "isDefault": True},
            {"name": "代码专家", "content": "你是资深全栈工程师。回答简洁，优先给代码。", "isDefault": False},
        ],
        "agentTools": [],  # 由 _read_settings 自动从 ToolRegistry 扫描合并
        "enabledSkills": ["web-research", "interest-scout", "frontend-craft"],
        "interestsEnabled": True,
        "userInterests": [],
        "agentParams": {"temperature": 0.3, "maxTokens": 4096, "topP": 0.9, "presencePenalty": 0, "maxToolRounds": 6, "agentPrompt": ""},
        "theme": "dark",
        "codeFont": "JetBrains Mono",
        "ligatures": True,
        "glass": False,
        "devMode": False,
        "autoTools": True,
        "thinking": False,
        "displayLimit": 30,  # 聊天消息默认显示条数，0 表示无限制
    }


def _merge_registered_tools(data: dict) -> dict:
    """
    将 ToolRegistry 中所有已注册的工具自动合并到 data['agentTools']。
    - 已有工具保留用户的 enabled/description/schema/showSchema 设置
    - 新工具默认启用
    - 已注销的工具标记禁用保留在末尾
    """
    existing: dict[str, dict] = {}
    for item in data.get("agentTools", []):
        if isinstance(item, dict) and item.get("name"):
            existing[item["name"]] = item

    merged: list[dict] = []
    seen: set[str] = set()
    for tool in ToolRegistry.list():
        name = tool.name
        seen.add(name)
        if name in existing:
            old = existing[name]
            merged.append({
                "name": name,
                "description": old.get("description", tool.description),
                "schema": old.get("schema", json.dumps(tool.parameters)),
                "enabled": bool(old.get("enabled", True)),
                "showSchema": bool(old.get("showSchema", False)),
            })
        else:
            merged.append({
                "name": name,
                "description": tool.description,
                "schema": json.dumps(tool.parameters),
                "enabled": True,
                "showSchema": False,
            })
    for name, old in existing.items():
        if name not in seen:
            merged.append({
                "name": name,
                "description": old.get("description", ""),
                "schema": old.get("schema", ""),
                "enabled": False,
                "showSchema": bool(old.get("showSchema", False)),
            })

    data["agentTools"] = merged
    return data


def _read_settings() -> dict:
    """读取设置，自动合并注册工具。"""
    if not SETTINGS_FILE.exists():
        return _merge_registered_tools(_default_settings())
    try:
        data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return _merge_registered_tools(_default_settings())

    # 补充默认值（新增字段）— 支持深合并 agentParams
    defaults = _default_settings()
    for key, value in defaults.items():
        if key not in data:
            data[key] = value
        elif isinstance(value, dict) and isinstance(data.get(key), dict):
            for sub_key, sub_value in value.items():
                if sub_key not in data[key]:
                    data[key][sub_key] = sub_value

    return _merge_registered_tools(data)


def _write_settings(data: dict):
    """写入设置，注意 agentTools 由自动扫描管理，写全量但读时仍会合并。"""
    data["_updatedAt"] = datetime.now().isoformat()
    SETTINGS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _models_url(base_url: str) -> str:
    normalized = base_url.strip().rstrip("/")
    if not normalized:
        raise HTTPException(status_code=400, detail="Base URL 不能为空")
    if normalized.endswith("/v1"):
        return f"{normalized}/models"
    return urljoin(f"{normalized}/", "v1/models")


def _extract_model_ids(payload) -> list[str]:
    data = payload.get("data") if isinstance(payload, dict) else payload
    if not isinstance(data, list):
        return []
    model_ids: list[str] = []
    for item in data:
        model_id = None
        if isinstance(item, dict):
            model_id = item.get("id") or item.get("name")
        elif isinstance(item, str):
            model_id = item
        if isinstance(model_id, str) and model_id and model_id not in model_ids:
            model_ids.append(model_id)
    return model_ids


def _is_owner_request(request: Request) -> bool:
    try:
        from backend.auth import _bearer_ok, is_local_access, session_from_scope

        if is_local_access(request.scope) or _bearer_ok(request.scope):
            return True
        session = session_from_scope(request.scope)
        return bool(session and session.get("role") == "owner")
    except Exception:
        return True  # 鉴权未启用时保持兼容


USER_SETTING_KEYS = {
    "params", "streaming", "providers", "prompts", "agentParams",
    "theme", "codeFont", "ligatures", "glass", "displayLimit",
    "thinking", "autoTools",
}


def _settings_identity(request: Request) -> tuple[str, str]:
    try:
        from backend.auth import is_local_access, session_from_scope, _bearer_ok, owner_user_id

        session = session_from_scope(request.scope)
        if session:
            return str(session.get("user_id") or ""), str(session.get("role") or "member")
        if is_local_access(request.scope) or _bearer_ok(request.scope):
            return owner_user_id(), "owner"
    except Exception:
        pass
    return "", ""


def _user_settings_file(user_id: str) -> Path:
    safe_id = "".join(c for c in user_id if c.isalnum() or c in "_.-")
    if not safe_id:
        raise HTTPException(status_code=401, detail="账号信息不可用")
    path = USER_SETTINGS_DIR / safe_id / "settings.json"
    return path


def _read_user_settings(user_id: str) -> dict:
    path = _user_settings_file(user_id)
    try:
        data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except (OSError, json.JSONDecodeError):
        data = {}
    defaults = _default_settings()
    # Only expose keys that are deliberately user-scoped. Never inherit admin keys.
    result = {k: defaults[k] for k in USER_SETTING_KEYS if k in defaults}
    result.update({k: v for k, v in data.items() if k in USER_SETTING_KEYS})
    result["agentTools"] = _merge_registered_tools({"agentTools": data.get("agentTools", [])})["agentTools"]
    return result


def _write_user_settings(user_id: str, data: dict) -> None:
    path = _user_settings_file(user_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    safe = {k: v for k, v in data.items() if k in USER_SETTING_KEYS}
    safe["_updatedAt"] = datetime.now().isoformat()
    path.write_text(json.dumps(safe, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        import os
        os.chmod(path, 0o600)
    except OSError:
        pass


@router.get("")
async def get_settings(request: Request):
    user_id, role = _settings_identity(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if role == "owner":
        return _read_settings()
    return _read_user_settings(user_id)


@router.put("")
async def update_settings(request: Request, data: dict):
    user_id, role = _settings_identity(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if role == "owner":
        current = _read_settings()
        current.update(data)
        _write_settings(current)
        return {"status": "ok", "updatedAt": datetime.now().isoformat(), "scope": "instance"}
    current = _read_user_settings(user_id)
    current.update({k: v for k, v in data.items() if k in USER_SETTING_KEYS})
    _write_user_settings(user_id, current)
    return {"status": "ok", "updatedAt": datetime.now().isoformat(), "scope": "user"}


@router.post("/reset")
async def reset_settings(request: Request):
    user_id, role = _settings_identity(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if role == "owner":
        defaults = _default_settings()
        _write_settings(defaults)
        return {"status": "ok", "settings": defaults, "scope": "instance"}
    defaults = {k: _default_settings()[k] for k in USER_SETTING_KEYS if k in _default_settings()}
    defaults["agentTools"] = _merge_registered_tools({"agentTools": []})["agentTools"]
    _write_user_settings(user_id, defaults)
    return {"status": "ok", "settings": defaults, "scope": "user"}


@router.post("/providers/models")
async def load_provider_models(request: ProviderModelsRequest, http_request: Request):
    user_id, role = _settings_identity(http_request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    url = _models_url(request.baseUrl)
    headers = {"Accept": "application/json"}
    if request.key and not request.key.startswith("sk-***"):
        headers["Authorization"] = f"Bearer {request.key}"
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(url, headers=headers)
        if response.status_code >= 400:
            raise HTTPException(status_code=response.status_code, detail=f"模型列表加载失败: HTTP {response.status_code}")
        payload = response.json()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"模型列表加载失败: {exc}")
    models = _extract_model_ids(payload)
    if not models:
        raise HTTPException(status_code=502, detail="模型接口返回为空或格式不兼容")
    return {"models": models, "url": url}

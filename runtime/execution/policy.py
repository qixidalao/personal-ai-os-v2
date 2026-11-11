"""Policy loading for the execution boundary."""
# 中文：执行边界的策略加载。
from __future__ import annotations

import json
from pathlib import Path

from .models import ExecutionPolicy

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SETTINGS_FILE = PROJECT_ROOT / "storage" / "settings.json"


def _default_roots() -> list[str]:
    roots = [str(PROJECT_ROOT)]
    workspace = PROJECT_ROOT / "storage" / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    roots.append(str(workspace))
    return roots


def load_policy(settings: dict | None = None) -> ExecutionPolicy:
    if settings is None:
        try:
            settings = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            settings = {}
    raw = settings.get("execution") if isinstance(settings, dict) else None
    raw = raw if isinstance(raw, dict) else {}
    roots = raw.get("allowedRoots")
    normalized: list[str] = []
    if isinstance(roots, list):
        for item in roots:
            if not isinstance(item, str) or not item.strip():
                continue
            p = Path(item.strip()).expanduser()
            if not p.is_absolute():
                p = PROJECT_ROOT / p
            normalized.append(str(p.resolve()))
    if not normalized:
        normalized = _default_roots()
    return ExecutionPolicy(
        enabled=bool(raw.get("enabled", True)),
        allowed_roots=normalized,
        allow_shell=bool(raw.get("allowShell", True)),
        allow_python=bool(raw.get("allowPython", True)),
        allow_network=bool(raw.get("allowNetwork", False)),
        default_timeout=int(raw.get("defaultTimeout", 30) or 30),
        max_timeout=int(raw.get("maxTimeout", 300) or 300),
        max_output_bytes=int(raw.get("maxOutputBytes", 64 * 1024) or 64 * 1024),
        max_concurrent=max(1, int(raw.get("maxConcurrent", 2) or 2)),
        sandbox=str(raw.get("sandbox", "auto") or "auto"),
    )

"""增强型健康检查与系统状态 API。"""
import time
from pathlib import Path

from fastapi import APIRouter
from loguru import logger

router = APIRouter(tags=["health"])

_startup_time = time.time()


@router.get("/health")
async def health_check():
    """基础健康检查。"""
    return {"status": "ok", "service": "personal-ai-os", "version": "2.1.0"}


@router.get("/api/v1/health")
async def detailed_health():
    """详细健康检查，包含存储、会话和运行时间状态。"""
    uptime_sec = int(time.time() - _startup_time)
    storage_dir = Path("storage")
    sessions_dir = storage_dir / "sessions"
    logs_dir = storage_dir / "logs"

    health = {
        "status": "ok",
        "service": "personal-ai-os",
        "version": "2.1.0",
        "uptime_seconds": uptime_sec,
        "uptime_human": _format_duration(uptime_sec),
        "storage": {
            "exists": storage_dir.exists(),
            "sessions_count": len(list(sessions_dir.glob("*.json"))) if sessions_dir.exists() else 0,
            "logs_exists": logs_dir.exists(),
        },
    }

    # 检查 skills 目录
    skills_dir = Path("skills")
                      # 中文：技能

    if skills_dir.exists():
        health["skills"] = {
               # 中文：技能

            "count": len(list(skills_dir.glob("*/SKILL.md"))),
            "enabled": [d.name for d in skills_dir.iterdir() if d.is_dir()],
        }

    return health


@router.get("/api/v1/status")
async def system_status():
    """系统运行状态概览。"""
    sessions_dir = Path("storage/sessions")
    session_count = len(list(sessions_dir.glob("*.json"))) if sessions_dir.exists() else 0

    return {
        "status": "running",
        "version": "2.1.0",
        "features": {
            "streaming": True,
            "tools": True,
            "skills": True,
            # 中文：技能

            "memory": True,
            "media": True,
            # 中文：媒体

        },
        "stats": {
            "sessions": session_count,
            "uptime_seconds": int(time.time() - _startup_time),
        },
    }


def _format_duration(seconds: int) -> str:
    """将秒数格式化为人类可读的持续时间。"""
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m {seconds % 60}s"
    if seconds < 86400:
        return f"{seconds // 3600}h {(seconds % 3600) // 60}m"
    return f"{seconds // 86400}d {(seconds % 86400) // 3600}h"

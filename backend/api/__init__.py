"""基础 API 路由。"""
from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check():
    """基础健康检查；详细运行状态由应用自身状态接口提供。"""
    return {"status": "ok", "service": "personal-ai-os"}

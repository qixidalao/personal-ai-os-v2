"""
Personal AI OS V2 — 后端入口
FastAPI + SSE + Event Bus 架构
"""
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.config.loader import ConfigLoader
from backend.logger import setup_logger
from backend.event import EventBus
from backend.api import router as api_router
from backend.gateway import router as gateway_router
from backend.stream import router as stream_router
from backend.websocket import router as ws_router
from backend.sessions import router as sessions_router
from backend.settings_api import router as settings_router
from backend.chat_api import router as chat_router
from backend.media_api import router as media_router
from backend.image_enhance_api import router as image_enhance_router
from backend.skills_api import router as skills_router
from backend.tools_api import router as tools_router
from backend.health_api import router as health_router
from backend.runs_api import router as runs_router
from backend.auth import AuthMiddleware, router as auth_router
from backend.approvals_api import router as approvals_router
from backend.executor_api import router as executor_router
from backend.tts_api import router as tts_router
from backend.middleware.logging import RequestLoggingMiddleware
from backend.onebot import router as onebot_router, register_event_handlers, OneBotChatWorker


@asynccontextmanager
async def lifespan(app: FastAPI):
    event_bus = app.state.event_bus
    logger = app.state.logger
    logger.info("🚀 Personal AI OS V2 启动中...")

    # ── P0：执行边界状态 + 上次未收尾的 Run 恢复 ──────────────────────────
    try:
        from runtime.execution import get_execution_manager
        _exec_status = get_execution_manager().status()
        logger.info(
            f"🛡️ 执行边界: sandbox={_exec_status.get('sandbox')} "
            f"python={_exec_status.get('allowPython')} shell={_exec_status.get('allowShell')} "
            f"network={_exec_status.get('allowNetwork')} roots={_exec_status.get('allowedRoots')}"
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"执行边界初始化失败（工具执行会被拒绝）: {exc}")
    try:
        from runtime.runs.store import get_run_store
        _run_store = get_run_store()
        app.state.run_store = _run_store
        _recovered = _run_store.mark_interrupted_runs()
        if _recovered:
            logger.warning(f"🔁 发现 {_recovered} 个上次未收尾的 Run，已标记为 unknown")
        try:
            from runtime.approvals import get_approval_store
            _approvals = get_approval_store()
            _expired = _approvals.expire_stale()
            if _expired:
                logger.warning(f"⏰ {_expired} 个待审批请求已过期")
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"审批存储初始化失败: {exc}")
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"Run 状态恢复失败: {exc}")

    register_event_handlers(event_bus)
    chat_worker = OneBotChatWorker(event_bus)
    await chat_worker.start()
    app.state.onebot_chat_worker = chat_worker
    logger.info("🤖 OneBot 适配器已加载")

    await event_bus.emit("system.start", {"version": app.version})
    yield

    logger.info("👋 Personal AI OS V2 关闭中...")
    await event_bus.emit("system.stop", {})


def create_app() -> FastAPI:
    config_loader = ConfigLoader(Path("config"))
    config = config_loader.load_all()
    logger = setup_logger(config)
    event_bus = EventBus()

    app = FastAPI(
        title="Personal AI OS V2",
        description="个人 AI 工作台与本地智能中枢",
        version="2.1.0",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    app.state.config = config
    app.state.config_loader = config_loader
    app.state.event_bus = event_bus
    app.state.logger = logger

    cors_config = config.get("app", {}).get("server", {})
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_config.get("cors_origins", ["*"]),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestLoggingMiddleware)

    @app.middleware("http")
    async def _static_cache_headers(request: Request, call_next):
        """静态资源缓存策略：index.html 永不缓存，hash 资源长缓存。

        否则手机浏览器可能缓存旧 index.html，重新部署后引用已不存在的
        hash 资源，表现为“打不开/白屏”，必须手动清缓存才能恢复。
        """
        response = await call_next(request)
        try:
            path = request.url.path
            if path.startswith("/assets/"):
                response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
            elif path in ("/", "/index.html") or path.endswith(".html"):
                response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
                response.headers["Pragma"] = "no-cache"
                response.headers["Expires"] = "0"
        except Exception:
            pass
        return response

    app.include_router(api_router, prefix="/api/v1")
    app.include_router(gateway_router, prefix="/api/v1/gateway")
    app.include_router(stream_router, prefix="/api/v1/stream")
    app.include_router(onebot_router)
    app.include_router(ws_router, prefix="/ws")
    app.include_router(sessions_router)
    app.include_router(settings_router)
    app.include_router(chat_router)
    app.include_router(media_router)
    app.include_router(image_enhance_router)
    app.include_router(skills_router)
    app.include_router(tools_router)
    app.include_router(health_router)
    app.include_router(runs_router)
    app.include_router(auth_router)
    app.include_router(approvals_router)
    app.include_router(executor_router)
    app.include_router(tts_router)

    static_dir = Path("frontend/dist")
    if static_dir.exists() and (static_dir / "index.html").exists():
        @app.get("/", include_in_schema=False)
        async def frontend_index():
            return FileResponse(static_dir / "index.html")

        app.mount("/", StaticFiles(directory=str(static_dir), html=False), name="frontend")
        logger.info(f"📂 前端 UI: {static_dir}")
    else:
        @app.get("/")
        async def api_welcome():
            return {"app": "Personal AI OS V2", "version": app.version, "status": "running"}
        logger.warning("⚠️  无前端 UI")

    # 访问鉴权：最后添加 -> 最先执行，覆盖所有 HTTP/WS
    app.add_middleware(AuthMiddleware)

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    server_config = app.state.config.get("app", {}).get("server", {})
    uvicorn.run(
        "backend.main:app",
        host=server_config.get("host", "0.0.0.0"),
        port=server_config.get("port", 8080),
        reload=server_config.get("dev_mode", False),
    )


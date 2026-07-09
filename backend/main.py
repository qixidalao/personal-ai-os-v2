"""
Personal AI OS V2 — 后端入口
FastAPI + SSE + Event Bus 架构
"""
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
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
from backend.tools_api import router as tools_router
# ─── OneBot QQ 机器人 ──────────────────────────────
from backend.onebot import router as onebot_router, register_event_handlers, OneBotChatWorker


@asynccontextmanager
async def lifespan(app: FastAPI):
    event_bus = app.state.event_bus
    logger = app.state.logger
    logger.info("🚀 Personal AI OS V2 启动中...")

    # ─── 注册 OneBot 事件处理器 ────────────────
    register_event_handlers(event_bus)
    chat_worker = OneBotChatWorker(event_bus)
    await chat_worker.start()
    app.state.onebot_chat_worker = chat_worker
    logger.info("🤖 QQ 机器人 (OneBot) 适配器已加载")

    await event_bus.emit("system.start", {"version": "2.0.0"})
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
        description="运行于 Android Termux 的个人 AI 操作系统",
        version="2.0.0",
        lifespan=lifespan,
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

    # API 路由
    app.include_router(api_router, prefix="/api/v1")
    app.include_router(gateway_router, prefix="/api/v1/gateway")
    app.include_router(stream_router, prefix="/api/v1/stream")
    # ─── OneBot WS 路由（NapCat 反向连接） ──
    app.include_router(onebot_router)
    # ─── 原有 WS 路由 ──────────────────────
    app.include_router(ws_router, prefix="/ws")
    app.include_router(sessions_router)
    app.include_router(settings_router)
    app.include_router(chat_router)
    app.include_router(tools_router)

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
            return {"app": "Personal AI OS V2", "version": "2.0.0", "status": "running"}
        logger.warning("⚠️  无前端 UI")

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

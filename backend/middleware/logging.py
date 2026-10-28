"""增强型请求日志与性能监控中间件。"""
import time
import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from loguru import logger


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """记录所有 HTTP 请求的处理时间和状态码，跳过静态文件和 health 检查。"""

    def __init__(self, app, skip_paths: set[str] | None = None):
        super().__init__(app)
        self.skip_paths = skip_paths or {"/health", "/api/v1/health", "/favicon.ico"}

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path
        if any(path.startswith(skip) for skip in self.skip_paths):
            return await call_next(request)

        request_id = request.headers.get("X-Request-Id", uuid.uuid4().hex[:12])
        request.state.request_id = request_id
        start = time.perf_counter()

        try:
            response = await call_next(request)
        except Exception as exc:
            duration_ms = (time.perf_counter() - start) * 1000
            logger.error(
                f"[{request_id}] {request.method} {path} → EXCEPTION ({duration_ms:.1f}ms): {exc}"
            )
            raise

        duration_ms = (time.perf_counter() - start) * 1000
        status = response.status_code
        level = "info" if status < 400 else "warning" if status < 500 else "error"
        getattr(logger, level)(
            f"[{request_id}] {request.method} {path} → {status} ({duration_ms:.1f}ms)"
        )
        response.headers["X-Request-Id"] = request_id
        response.headers["X-Response-Time-Ms"] = f"{duration_ms:.1f}"
        return response

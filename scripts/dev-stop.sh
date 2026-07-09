#!/bin/bash
# ============================================
# Personal AI OS — 停止开发服务
# ============================================

echo "🛑 停止 Personal AI OS 服务..."

# 查找并停止后端进程
BACKEND_PID=$(pgrep -f "uvicorn backend.main:app" 2>/dev/null)
if [ -n "$BACKEND_PID" ]; then
    kill $BACKEND_PID 2>/dev/null
    echo "   ✅ 后端服务已停止 (PID: $BACKEND_PID)"
fi

# 查找并停止前端进程
FRONTEND_PID=$(pgrep -f "vite" 2>/dev/null)
if [ -n "$FRONTEND_PID" ]; then
    kill $FRONTEND_PID 2>/dev/null
    echo "   ✅ 前端服务已停止 (PID: $FRONTEND_PID)"
fi

echo "✅ 所有服务已停止"

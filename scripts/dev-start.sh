#!/bin/bash
# ============================================
# Personal AI OS — 开发模式启动脚本
# ============================================

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "🚀 Personal AI OS V2 — 开发模式启动"
echo "===================================="

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo "❌ 未找到 python3，请先安装 Python 3.11+"
    exit 1
fi

# 检查 Node.js
if ! command -v node &> /dev/null; then
    echo "❌ 未找到 node，请先安装 Node.js 18+"
    exit 1
fi

# 创建虚拟环境
if [ ! -d "$PROJECT_DIR/.venv" ]; then
    echo "📦 创建 Python 虚拟环境..."
    python3 -m venv "$PROJECT_DIR/.venv"
fi

# 激活虚拟环境并安装依赖
source "$PROJECT_DIR/.venv/bin/activate"
echo "📦 安装 Python 依赖..."
pip install -r "$PROJECT_DIR/backend/requirements.txt" -q

# 安装前端依赖
echo "📦 安装前端依赖..."
cd "$PROJECT_DIR/frontend"
npm install --silent

# 启动后端（后台）
echo "🌐 启动后端服务 (port 8080)..."
cd "$PROJECT_DIR"
python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8080 --reload &
BACKEND_PID=$!
echo "   Backend PID: $BACKEND_PID"

# 启动前端（后台）
echo "🎨 启动前端开发服务器 (port 3000)..."
cd "$PROJECT_DIR/frontend"
npx vite --host 0.0.0.0 --port 3000 &
FRONTEND_PID=$!
echo "   Frontend PID: $FRONTEND_PID"

echo ""
echo "✅ Personal AI OS V2 启动完成！"
echo "   Frontend: http://localhost:3000"
echo "   Backend:  http://localhost:8080"
echo "   API Docs: http://localhost:8080/docs"
echo ""
echo "按 Ctrl+C 停止所有服务"

# 捕获中断信号
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" SIGINT SIGTERM

# 等待子进程
wait

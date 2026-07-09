#!/bin/bash
# ============================================
# Personal AI OS — 重启服务
# ============================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "🔄 重启 Personal AI OS..."

# 停止
bash "$SCRIPT_DIR/dev-stop.sh"

# 等待
sleep 2

# 启动
bash "$SCRIPT_DIR/dev-start.sh"

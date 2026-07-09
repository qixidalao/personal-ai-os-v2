#!/bin/bash
# ============================================
# Personal AI OS — 清理脚本
# ============================================

echo "🧹 Personal AI OS — 清理"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# 清理 Python 缓存
echo "  清理 __pycache__..."
find "$PROJECT_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

# 清理 .pyc
echo "  清理 .pyc..."
find "$PROJECT_DIR" -type f -name "*.pyc" -delete 2>/dev/null || true

# 清理前端构建
echo "  清理前端构建..."
rm -rf "$PROJECT_DIR/frontend/dist" 2>/dev/null || true
rm -rf "$PROJECT_DIR/frontend/node_modules/.vite" 2>/dev/null || true

# 清理日志
echo "  清理日志 (保留最近7天)..."
find "$PROJECT_DIR/storage/logs" -name "*.log" -mtime +7 -delete 2>/dev/null || true

# 清理临时文件
echo "  清理临时文件..."
rm -rf /tmp/personal-ai-os-* 2>/dev/null || true

echo "✅ 清理完成"

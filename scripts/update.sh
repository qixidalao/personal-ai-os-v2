#!/bin/bash
# ============================================
# Personal AI OS — 一键更新脚本
# ============================================

set -e

echo "🔄 Personal AI OS — 检查更新..."

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# 检查 Git
if [ ! -d "$PROJECT_DIR/.git" ]; then
    echo "❌ 不是 Git 仓库，无法自动更新"
    exit 1
fi

# 保存当前状态
echo "📦 备份当前配置..."
bash "$SCRIPT_DIR/backup.sh"

# 拉取更新
echo "📥 拉取最新代码..."
git -C "$PROJECT_DIR" pull

# 更新依赖
echo "📦 更新 Python 依赖..."
source "$PROJECT_DIR/.venv/bin/activate" 2>/dev/null || true
pip install -r "$PROJECT_DIR/backend/requirements.txt" -q

echo "📦 更新前端依赖..."
cd "$PROJECT_DIR/frontend"
npm install --silent
npm run build

echo "✅ 更新完成！请重启服务：bash scripts/restart.sh"

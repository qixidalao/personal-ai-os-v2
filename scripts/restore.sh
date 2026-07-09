#!/bin/bash
# ============================================
# Personal AI OS — 数据恢复脚本
# ============================================

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="$PROJECT_DIR/storage/backups"

echo "🔄 Personal AI OS 数据恢复"
echo "============================"

# 列出可用的备份
echo "可用的备份文件:"
ls -lh "$BACKUP_DIR"/*.tar.gz 2>/dev/null || echo "   没有找到备份文件"

# 选择备份
read -p "请输入要恢复的备份文件名 (留空取消): " BACKUP_FILE

if [ -z "$BACKUP_FILE" ]; then
    echo "已取消恢复"
    exit 0
fi

BACKUP_PATH="$BACKUP_DIR/$BACKUP_FILE"

if [ ! -f "$BACKUP_PATH" ]; then
    echo "❌ 备份文件不存在: $BACKUP_PATH"
    exit 1
fi

echo "⚠️  正在恢复数据，现有数据可能被覆盖..."
read -p "确认恢复? (y/N): " CONFIRM

if [ "$CONFIRM" != "y" ] && [ "$CONFIRM" != "Y" ]; then
    echo "已取消恢复"
    exit 0
fi

# 恢复
tar -xzf "$BACKUP_PATH" -C "$PROJECT_DIR"

echo "✅ 数据恢复完成: $BACKUP_FILE"

#!/bin/bash
# ============================================
# Personal AI OS — 数据备份脚本
# ============================================

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="$PROJECT_DIR/storage/backups"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_NAME="personal-ai-os-backup-$TIMESTAMP.tar.gz"

echo "📦 备份 Personal AI OS 数据..."

# 创建备份目录
mkdir -p "$BACKUP_DIR"

# 备份关键数据
tar -czf "$BACKUP_DIR/$BACKUP_NAME" \
    -C "$PROJECT_DIR" \
    config/ \
    storage/sqlite/ \
    storage/vector/ \
    storage/conversations/ \
    storage/files/ \
    storage/workspace/ \
    prompts/ \
    plugins/local/ \
    2>/dev/null || true

echo "✅ 备份完成: $BACKUP_DIR/$BACKUP_NAME"
echo "   大小: $(du -h "$BACKUP_DIR/$BACKUP_NAME" | cut -f1)"

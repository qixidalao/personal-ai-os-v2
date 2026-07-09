#!/bin/bash
# ============================================
# Personal AI OS — 环境检查脚本
# ============================================

echo "🔍 Personal AI OS — 环境诊断"
echo "=============================="

# Python
echo ""
echo "📋 Python:"
if command -v python3 &> /dev/null; then
    echo "   ✅ $(python3 --version)"
else
    echo "   ❌ 未安装"
fi

# Node.js
echo ""
echo "📋 Node.js:"
if command -v node &> /dev/null; then
    echo "   ✅ $(node --version)"
else
    echo "   ❌ 未安装"
fi

# npm
echo ""
echo "📋 npm:"
if command -v npm &> /dev/null; then
    echo "   ✅ $(npm --version)"
else
    echo "   ❌ 未安装"
fi

# 目录结构
echo ""
echo "📋 项目目录:"
DIRS=("config" "backend" "frontend" "runtime" "tools" "prompts" "plugins" "storage" "scripts" "tests")
for dir in "${DIRS[@]}"; do
    if [ -d "$(dirname "$0")/../$dir" ]; then
        echo "   ✅ $dir/"
    else
        echo "   ❌ $dir/ — 缺失"
    fi
done

# 配置文件
echo ""
echo "📋 配置文件:"
for file in "$(dirname "$0")/../config"/*.yaml; do
    if [ -f "$file" ]; then
        echo "   ✅ $(basename "$file")"
    fi
done

# 端口检查
echo ""
echo "📋 端口状态:"
for port in 8080 3000; do
    if ss -tlnp | grep -q ":$port "; then
        echo "   ⚠️  端口 $port 已被占用"
    else
        echo "   ✅ 端口 $port 可用"
    fi
done

echo ""
echo "=============================="
echo "✅ 诊断完成"

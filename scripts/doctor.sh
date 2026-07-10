#!/usr/bin/env bash
# Personal AI OS — environment diagnostics

set -u

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOCAL_BIN="${HOME}/.local/bin"

# Interactive shells may know the local Node installation while scripts do not.
if [[ -d "$LOCAL_BIN" ]]; then
    export PATH="$LOCAL_BIN:$PATH"
fi

ok()   { printf '   ✅ %s\n' "$*"; }
warn() { printf '   ⚠️  %s\n' "$*"; }
fail() { printf '   ❌ %s\n' "$*"; }
section() { printf '\n📋 %s:\n' "$1"; }

printf '🔍 Personal AI OS — 环境诊断\n'
printf '==============================\n'

section "Python"
if command -v python3 >/dev/null 2>&1; then
    ok "$(python3 --version 2>&1) ($(command -v python3))"
else
    fail "未安装"
fi

section "Node.js"
if command -v node >/dev/null 2>&1; then
    ok "$(node --version) ($(command -v node))"
else
    fail "未安装；已检查 PATH 和 $LOCAL_BIN"
fi

section "npm"
if command -v npm >/dev/null 2>&1; then
    ok "$(npm --version) ($(command -v npm))"
else
    fail "未安装；已检查 PATH 和 $LOCAL_BIN"
fi

section "项目目录"
DIRS=(config backend frontend runtime tools prompts plugins storage scripts tests)
for dir in "${DIRS[@]}"; do
    if [[ -d "$PROJECT_ROOT/$dir" ]]; then
        ok "$dir/"
    else
        fail "$dir/ — 缺失"
    fi
done

section "配置文件"
shopt -s nullglob
config_files=("$PROJECT_ROOT"/config/*.yaml)
if ((${#config_files[@]} == 0)); then
    fail "未找到 YAML 配置"
else
    for file in "${config_files[@]}"; do
        ok "$(basename "$file")"
    done
fi

section "端口状态"
for port in 8080 3000; do
    socket_info="$(ss -H -ltnp "sport = :$port" 2>/dev/null || true)"
    if [[ -n "$socket_info" ]]; then
        process_info="$(sed -n 's/.*users:(("\([^"]*\)",pid=\([0-9]*\).*/\1, PID \2/p' <<<"$socket_info" | head -n 1)"
        if [[ -n "$process_info" ]]; then
            warn "端口 $port 已被占用（$process_info）"
        else
            warn "端口 $port 已被占用"
        fi
    else
        ok "端口 $port 可用"
    fi
done

printf '\n==============================\n'
printf '✅ 诊断完成\n'

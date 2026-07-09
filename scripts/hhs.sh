#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════
# Personal AI OS (hhs) — 快捷启动/重启脚本
# 用法:
#   ./scripts/hhs.sh           启动服务
#   ./scripts/hhs.sh restart   重启服务（自动杀端口+重新构建+启动）
#   ./scripts/hhs.sh stop      停止服务
#   ./scripts/hhs.sh rebuild   只重新构建前端（不启停服务）
#   ./scripts/hhs.sh status    查看服务状态和日志尾巴
# ═══════════════════════════════════════════════════════════

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PORT="${HHS_PORT:-8080}"
LOG_FILE="/tmp/hhs.log"
PID_FILE="/tmp/hhs.pid"
NODE_BIN="/home/qixi/.local/bin/node"

cd "$SCRIPT_DIR"

# ── 颜色 ──────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

info()  { echo -e "${CYAN}[hhs]${NC} $1"; }
ok()    { echo -e "${GREEN}[✓]${NC} $1"; }
warn()  { echo -e "${YELLOW}[!]${NC} $1"; }
err()   { echo -e "${RED}[✗]${NC} $1"; }

# ── 工具函数 ──────────────────────────────────────────────

find_pid_on_port() {
  lsof -ti :"$PORT" 2>/dev/null || true
}

kill_port() {
  local pids
  pids="$(find_pid_on_port)"
  if [ -n "$pids" ]; then
    warn "端口 $PORT 被 PID $pids 占用，正在释放..."
    # 先温柔地 kill
    echo "$pids" | xargs -r kill 2>/dev/null || true
    sleep 1
    # 还没死透就强杀
    pids="$(find_pid_on_port)"
    if [ -n "$pids" ]; then
      echo "$pids" | xargs -r kill -9 2>/dev/null || true
      sleep 0.5
    fi
    ok "端口 $PORT 已释放"
  fi
}

build_frontend() {
  info "构建前端..."
  if [ ! -f "$NODE_BIN" ]; then
    warn "未找到 node ($NODE_BIN)，尝试 system node..."
    if command -v node &>/dev/null; then
      NODE_BIN="node"
    else
      err "找不到 node，跳过前端构建"
      return 1
    fi
  fi
  cd "$SCRIPT_DIR/frontend"
  if "$NODE_BIN" node_modules/.bin/vite build 2>&1 | tail -5; then
    ok "前端构建成功"
  else
    err "前端构建失败"
    return 1
  fi
  cd "$SCRIPT_DIR"
}

start_service() {
  if [ -n "$(find_pid_on_port)" ]; then
    err "端口 $PORT 已被占用！先执行 ./scripts/hhs.sh restart"
    return 1
  fi

  info "启动 hhs 服务 (端口 $PORT)..."

  # 后台启动，把 PID 记下来
  nohup python3 -m uvicorn backend.main:app \
    --host 0.0.0.0 \
    --port "$PORT" \
    > "$LOG_FILE" 2>&1 &
  local pid=$!
  echo "$pid" > "$PID_FILE"

  # 等几秒确认启动成功
  sleep 2
  if kill -0 "$pid" 2>/dev/null; then
    ok "服务已启动 (PID $pid) → http://localhost:$PORT"
    # 检查日志是否有错误
    if grep -i "error\|address already in use" "$LOG_FILE" 2>/dev/null | grep -v "closed" | head -3; then
      warn "日志中有错误，请检查: tail -20 $LOG_FILE"
    fi
  else
    err "服务启动失败！"
    tail -10 "$LOG_FILE"
    return 1
  fi
}

stop_service() {
  local pid=""
  # 先从 pid 文件读
  if [ -f "$PID_FILE" ]; then
    pid="$(cat "$PID_FILE")"
    if kill -0 "$pid" 2>/dev/null; then
      info "停止服务 (PID $pid)..."
      kill "$pid" 2>/dev/null || true
      sleep 1
      if kill -0 "$pid" 2>/dev/null; then
        kill -9 "$pid" 2>/dev/null || true
      fi
      ok "服务已停止"
    fi
    rm -f "$PID_FILE"
  fi

  # 再确保端口彻底释放
  kill_port
}

show_status() {
  local pid=""
  if [ -f "$PID_FILE" ]; then
    pid="$(cat "$PID_FILE")"
  fi
  if [ -z "$pid" ] || ! kill -0 "$pid" 2>/dev/null; then
    pid="$(find_pid_on_port)"
  fi

  if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
    ok "hhs 服务运行中 (PID $pid, 端口 $PORT)"
    echo ""
    echo "  📍  http://localhost:$PORT"
    echo "  🕒  启动时间: $(ps -o lstart= -p "$pid" 2>/dev/null || echo '未知')"
    echo ""
    echo "  ── 最近日志 ──"
    tail -8 "$LOG_FILE" 2>/dev/null | sed 's/^/    /' || echo "    (暂无日志)"
    echo ""
    echo "  查看全部日志: tail -f $LOG_FILE"
  else
    warn "hhs 服务未运行"
    # 检查日志是否有残影
    if [ -f "$LOG_FILE" ] && [ -s "$LOG_FILE" ]; then
      echo ""
      echo "  ── 上次运行日志最后几行 ──"
      tail -5 "$LOG_FILE" | sed 's/^/    /'
    fi
  fi
}

# ── 主命令分发 ────────────────────────────────────────────

case "${1:-start}" in
  start)
    kill_port
    build_frontend || warn "前端构建跳过（不影响后端启动）"
    start_service
    ;;
  restart)
    info "===== 重启 hhs 服务 ====="
    stop_service
    build_frontend || warn "前端构建跳过"
    start_service
    ok "重启完成 🚀"
    ;;
  stop)
    stop_service
    ok "服务已停止"
    ;;
  rebuild)
    build_frontend
    ;;
  status)
    show_status
    ;;
  *)
    echo "用法: $0 {start|restart|stop|rebuild|status}"
    echo ""
    echo "  start     启动服务（自动杀端口+构建+启动）"
    echo "  restart   重启服务"
    echo "  stop      停止服务"
    echo "  rebuild   只重新构建前端"
    echo "  status    查看服务状态"
    exit 1
    ;;
esac

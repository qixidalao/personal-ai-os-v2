#!/usr/bin/env bash
# AIOS remote runner bootstrap (BYO server)
# Usage (run as root on YOUR server):
#   bash aios-bootstrap.sh --public-key "ssh-ed25519 AAAA... aios-user" [--user aios] [--image aios-runner:latest]
#
# What it does:
#   1. install Docker (or use existing podman)
#   2. create dedicated non-root user `aios`
#   3. install the AIOS SSH public key
#   4. prepare workspace + pull runner image
#   5. print a health check command
set -euo pipefail

PUBLIC_KEY=""
RUNNER_USER="aios"
IMAGE="aios-runner:latest"
SSH_PORT="22"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --public-key) PUBLIC_KEY="${2:-}"; shift 2 ;;
    --user)       RUNNER_USER="${2:-aios}"; shift 2 ;;
    --image)      IMAGE="${2:-aios-runner:latest}"; shift 2 ;;
    --ssh-port)   SSH_PORT="${2:-22}"; shift 2 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

if [[ "$(id -u)" -ne 0 ]]; then
  echo "请用 root 运行（或在前面加 sudo）" >&2
  exit 1
fi
if [[ -z "$PUBLIC_KEY" ]]; then
  echo "缺少 --public-key（在 AIOS 设置页生成后复制公钥）" >&2
  exit 2
fi

echo "== 1/5 安装 Docker =="
if ! command -v docker >/dev/null 2>&1; then
  if command -v apt-get >/dev/null 2>&1; then
    apt-get update -y
    DEBIAN_FRONTEND=noninteractive apt-get install -y docker.io
  elif command -v dnf >/dev/null 2>&1; then
    dnf install -y docker
  else
    echo "无法自动安装 Docker，请手动安装后重试" >&2
    exit 1
  fi
fi
systemctl enable --now docker >/dev/null 2>&1 || true

echo "== 2/5 创建用户 ${RUNNER_USER} =="
if ! id "${RUNNER_USER}" >/dev/null 2>&1; then
  useradd -m -s /bin/bash "${RUNNER_USER}"
fi
usermod -aG docker "${RUNNER_USER}" || true

echo "== 3/5 安装 AIOS 公钥 =="
install -d -m 700 -o "${RUNNER_USER}" -g "${RUNNER_USER}" "/home/${RUNNER_USER}/.ssh"
touch "/home/${RUNNER_USER}/.ssh/authorized_keys"
chown "${RUNNER_USER}:${RUNNER_USER}" "/home/${RUNNER_USER}/.ssh/authorized_keys"
chmod 600 "/home/${RUNNER_USER}/.ssh/authorized_keys"
if ! grep -qF "$PUBLIC_KEY" "/home/${RUNNER_USER}/.ssh/authorized_keys"; then
  echo "$PUBLIC_KEY" >> "/home/${RUNNER_USER}/.ssh/authorized_keys"
fi

echo "== 4/5 准备 runner 镜像 =="
if docker image inspect "${IMAGE}" >/dev/null 2>&1; then
  echo "本机已有镜像 ${IMAGE}，跳过构建"
elif [[ -f "$(dirname "$0")/runner/Dockerfile" ]]; then
  docker build -t "${IMAGE}" "$(dirname "$0")/runner"
else
  echo "未找到 runner/Dockerfile；请将仓库中的 scripts/runner/Dockerfile 与此脚本放在同一 scripts 目录下" >&2
  exit 1
fi

echo "== 5/5 工作目录 =="
install -d -m 755 -o "${RUNNER_USER}" -g "${RUNNER_USER}" "/home/${RUNNER_USER}/workspace"

echo
echo "✅ 部署完成"
echo "在 AIOS 中填写："
echo "  主机: $(hostname -I 2>/dev/null | awk '{print $1}')"
echo "  端口: ${SSH_PORT}"
echo "  用户: ${RUNNER_USER}"
echo "  镜像: ${IMAGE}"
echo
echo "服务器自检："
echo "  docker run --rm ${IMAGE} sh -lc 'echo AIOS_OK'"

#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════
# Termux 一键部署 NapCat + hhs OneBot 适配器
# 让 Android 手机变成 QQ 机器人服务器！
# ═══════════════════════════════════════════════════════════
set -e

# ─── 颜色 ─────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}╔════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║   🤖 Termux QQ 机器人一键部署脚本    ║${NC}"
echo -e "${CYAN}║      NapCat + hhs OneBot 适配器      ║${NC}"
echo -e "${CYAN}╚════════════════════════════════════════╝${NC}"
echo ""

# ─── 检查 Termux ──────────────────────────────────────
if [ ! -d "/data/data/com.termux" ] && [ ! -f "/system/bin/sh" ]; then
    echo -e "${YELLOW}⚠️  看起来不是在 Termux 环境中运行${NC}"
    echo -e "${YELLOW}   脚本仍会继续，但某些步骤可能不适用${NC}"
fi

# ─── 1. 更新包管理器 ────────────────────────────────
echo -e "${GREEN}[1/6]📦 更新 Termux 包管理器...${NC}"
pkg update -y && pkg upgrade -y

# ─── 2. 安装必要依赖 ────────────────────────────────
echo -e "${GREEN}[2/6]🔧 安装依赖（proot-distro, git, nodejs, python）...${NC}"
pkg install -y proot-distro git nodejs python build-essential curl wget

# ─── 3. 创建 Ubuntu 容器 ────────────────────────────
echo -e "${GREEN}[3/6]📀 创建 Ubuntu 容器（用于运行 NapCat）...${NC}"
if ! proot-distro list | grep -q "ubuntu"; then
    proot-distro install ubuntu
else
    echo -e "${YELLOW}   Ubuntu 容器已存在，跳过安装${NC}"
fi

# ─── 4. 在 Ubuntu 容器中安装 NapCat ─────────────────
echo -e "${GREEN}[4/6]🎯 在 Ubuntu 容器中安装 NapCat...${NC}"

# 创建一个安装脚本放到容器中
cat > /tmp/install_napcat.sh << 'INSTALL_SCRIPT'
#!/bin/bash
set -e

echo "📦 更新 Ubuntu 包管理器..."
apt-get update -y
apt-get install -y curl wget nodejs npm ca-certificates

# 安装 NapCat（使用官方 Linux 安装器）
echo "📥 下载 NapCat Linux 安装器..."
# NapCat 官方 Linux 安装方式：一键脚本
# 参考：https://github.com/NapNeko/napcat-linux-installer
cd /root

# 创建 napcat 目录
mkdir -p /opt/napcat
cd /opt/napcat

# 使用 npm 安装 napcat（无头版）
echo "📥 安装 NapCat (npm)..."
npm install napcat --save

echo ""
echo "✅ NapCat 安装完成!"
echo "📌 NapCat 路径: /opt/napcat"
echo "📌 配置文件: /opt/napcat/config/onebot11.json"
echo ""
echo "⚠️  首次运行需要扫码登录 QQ 账号！"
echo "   运行命令: cd /opt/napcat && npx napcat"
echo ""

# 生成默认 OneBot 反向 WS 配置
mkdir -p /opt/napcat/config
cat > /opt/napcat/config/onebot11.json << 'CONFIG'
{
    "ws_reverse": {
        "enable": true,
        "url": "ws://10.123.9.78:8080/ws/onebot",
        "reconnect_interval": 3000
    },
    "http": {
        "enable": false
    },
    "ws": {
        "enable": false
    }
}
CONFIG

echo "📝 已生成默认反向 WS 配置 → ws://10.123.9.78:8080/ws/onebot"
echo "   请根据实际 hhs 服务地址修改 /opt/napcat/config/onebot11.json"
INSTALL_SCRIPT

# 复制安装脚本到容器并执行
proot-distro login ubuntu -- bash -c "$(cat /tmp/install_napcat.sh)"

# ─── 5. 检查 hhs 连接 ───────────────────────────────
echo -e "${GREEN}[5/6]🔗 检查 hhs 后端连接状态...${NC}"
HH_HOST="${1:-10.123.9.78}"
HH_PORT="${2:-8080}"

if curl -s "http://${HH_HOST}:${HH_PORT}/" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ hhs 后端可达: http://${HH_HOST}:${HH_PORT}${NC}"
else
    echo -e "${YELLOW}⚠️  无法连接 hhs 后端: http://${HH_HOST}:${HH_PORT}${NC}"
    echo -e "${YELLOW}   请在 NapCat 配置中手动设置正确的 WS 地址${NC}"
fi

# ─── 6. 完成 ─────────────────────────────────────────
echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║                     🎉 部署完成！                        ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${GREEN}📋 后续步骤：${NC}"
echo ""
echo -e "  ${YELLOW}1. 登录 Ubuntu 容器:${NC}"
echo -e "     proot-distro login ubuntu"
echo ""
echo -e "  ${YELLOW}2. 启动 NapCat 并扫码登录 QQ:${NC}"
echo -e "     cd /opt/napcat && npx napcat"
echo ""
echo -e "  ${YELLOW}3. 如果 NapCat 无法直接运行，尝试:${NC}"
echo -e "     # 安装 xvfb 虚拟显示"
echo -e "     apt-get install -y xvfb"
echo -e "     xvfb-run npx napcat"
echo ""
echo -e "  ${YELLOW}4. 检查反向 WS 连接状态:${NC}"
echo -e "     配置在 /opt/napcat/config/onebot11.json"
echo -e "     确认 url 指向你的 hhs 服务地址"
echo ""
echo -e "  ${YELLOW}5. 后台运行 NapCat（断开 SSH 不中断）:${NC}"
echo -e "     nohup xvfb-run npx napcat > napcat.log 2>&1 &"
echo ""
echo -e "${CYAN}💡 Tip: 如果你的 hhs 运行在其他地址，请在${NC}"
echo -e "${CYAN}   第1个参数传入 hhs 主机IP，第2个参数传入端口${NC}"
echo -e "${CYAN}   例如: bash termux-onebot.sh 192.168.1.100 8080${NC}"
echo ""

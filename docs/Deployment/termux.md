# Personal AI OS — Termux 部署指南

## 环境要求

- Android 11+
- Termux (F-Droid 版本)
- 至少 4GB 内存
- 至少 8GB 可用存储

## 安装步骤

### 1. 安装 Termux

从 F-Droid 安装 Termux，**不要从 Google Play 安装**（版本太旧）。

### 2. 安装依赖

```bash
pkg update && pkg upgrade
pkg install python nodejs git openssl
```

### 3. 克隆项目

```bash
cd ~
git clone https://github.com/username/personal-ai-os-v2.git
cd personal-ai-os-v2
```

### 4. 安装 Python 依赖

```bash
pip install -r backend/requirements.txt
```

### 5. 安装前端依赖

```bash
cd frontend
npm install
npm run build
cd ..
```

### 6. 启动

```bash
bash scripts/dev-start.sh
```

## 访问

在 Termux 中运行后，浏览器访问：
- `http://localhost:8080` — 后端 API
- `http://localhost:3000` — 前端界面

## 后台运行

```bash
nohup python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8080 &
```

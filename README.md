# Personal AI OS V2 / hhs

> 面向个人使用的 AI 工作台与本地智能中枢。
> 当前核心由 Vue 3 + TypeScript 前端、FastAPI 后端、SSE/WebSocket、EventBus、工具系统与 OneBot 适配组成。

![Vue](https://img.shields.io/badge/Vue-3.x-42b883)
![FastAPI](https://img.shields.io/badge/FastAPI-0.x-009688)
![TypeScript](https://img.shields.io/badge/TypeScript-5.x-3178c6)
![Python](https://img.shields.io/badge/Python-3.x-3776ab)

## 项目定位

Personal AI OS V2（内部称 **hhs**）是一个可长期演进的个人 AI 网关 / 工作台。

当前设计重点：

- Web UI 统一管理聊天、模型、提示词、工具、Agent 与工作区能力。
- FastAPI 统一承接 LLM 请求、流式输出、工具调用和事件分发。
- 配置采用 YAML 模板 + 本地运行时设置的方式管理。
- 聊天优先采用流式传输，并保留推理内容、工具调用等事件。
- 支持 OneBot 11 反向 WebSocket 作为外部入口。

## 当前架构

```text
personal-ai-os-v2/
├── backend/       # FastAPI 后端、API、SSE、WebSocket、EventBus、OneBot
├── frontend/      # Vue 3 + TypeScript + Vite
├── config/        # YAML 默认配置模板
├── runtime/       # 运行时能力
├── tools/         # 工具注册与实现
├── prompts/       # 提示词
├── scripts/       # 启停、构建、维护脚本
├── docs/          # API、架构、部署、协议等文档
├── tests/         # 测试
└── storage/       # 本地运行数据（不提交 Git）
```

### 后端

- FastAPI + Uvicorn
- SSE 流式聊天
- WebSocket
- EventBus / 事件流
- OpenAI-compatible LLM 请求适配
- Tool Registry / 工具调用
- OneBot 11 反向 WebSocket
- 本地设置与运行时数据

### 前端

- Vue 3
- TypeScript
- Vite
- Pinia
- Vue Router
- marked / highlight.js / KaTeX / Mermaid
- Monaco Editor
- 自绘 UI 组件

## 已具备能力

### 聊天与流式输出

- 会话管理
- OpenAI-compatible Chat API
- SSE 流式输出
- 推理内容展示
- 工具调用轨迹
- Markdown / 代码 / 数学公式 / Mermaid
- 消息重试、复制、历史加载

### 工具与 Agent

- 工具注册与调用 API
- 工具执行轨迹
- Agent 参数配置
- 文件、搜索、Shell、浏览器、Python 等工具入口

### OneBot

- `backend/onebot/`
- OneBot 11 反向 WebSocket
- `/ws/onebot`
- 支持与 NapCat 等 OneBot 实现对接

## 配置

默认配置位于 `config/`，由 `backend/config/loader.py` 自动加载 YAML。

常见配置包括：

- `app.yaml`：服务、端口、上传等基础配置
- `api.yaml`：Provider 与 API 参数模板
- `models.yaml`：模型配置模板
- `agents.yaml`：Agent 配置
- `memory.yaml` / `rag.yaml`：记忆与 RAG 配置
- `plugins.yaml`：插件配置
- `prompts.yaml`：提示词配置
- `profiles.yaml`：Profile 配置
- `shortcuts.yaml`：快捷操作
- `theme.yaml` / `ui.yaml`：界面配置
- `tools.yaml`：工具配置

敏感信息和个人运行数据应保存在 `storage/` 或本地环境变量中，不应提交到仓库。

## 启动

项目内置脚本负责构建前端并启动后端。具体脚本以 `scripts/` 当前内容为准，避免依赖机器相关的绝对路径。

后端也可以直接启动：

```bash
python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8080
```

前端开发：

```bash
cd frontend
npm install
npm run dev
```

构建与类型检查：

```bash
npm run build
npm run typecheck
```

默认服务端口为 `8080`，可通过配置调整。

## API

主要入口以当前代码为准，核心包括：

```text
GET  /
POST /api/v1/chat/...
GET  /api/v1/settings/...
PUT  /api/v1/settings/...
WS   /ws/...
WS   /ws/onebot
```

完整接口说明见 `docs/API/`。

## 隐私与仓库卫生

`.gitignore` 已忽略：

- 前端构建产物与 `node_modules/`
- `.env` 与本地虚拟环境
- Python 缓存与测试产物
- `storage/` 运行数据
- 数据库、日志、JSONL、临时文件
- 编辑器和系统临时文件

提交前建议检查：

```bash
git status
git ls-files | grep -Ei 'apikey|api_key|token|secret|password|\.env|storage/'
```

## 开发原则

- **配置与代码分离**：默认模板不保存个人密钥和运行数据。
- **事件驱动**：跨模块通信优先使用 EventBus。
- **流式优先**：LLM 与工具过程尽量保留实时事件。
- **以代码为准**：README、文档和 Roadmap 不应描述尚未实现的功能。
- **避免机器绑定**：文档和脚本不要依赖个人绝对路径、内网 IP 或临时环境。

## 当前维护状态

本仓库处于持续开发状态。项目功能会随着实际代码演进，README 只记录当前已经存在或明确稳定的能力，不再维护过时的里程碑清单或固定机器环境说明。

## License

GPL-3.0。详见 `LICENSE`。

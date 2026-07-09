# Personal AI OS V2 / hhs

> 一个面向个人使用的 AI 工作台与本地智能中枢。  
> 前端采用 Vue 3 + 自绘组件，后端采用 FastAPI + SSE/WebSocket/EventBus，目标是把聊天、工具调用、Agent、记忆、工作区、插件与自动化能力整合成一个可长期演进的个人 AI OS。

![Vue](https://img.shields.io/badge/Vue-3.x-42b883)
![FastAPI](https://img.shields.io/badge/FastAPI-0.x-009688)
![TypeScript](https://img.shields.io/badge/TypeScript-5.x-3178c6)
![Python](https://img.shields.io/badge/Python-3.x-3776ab)
![Status](https://img.shields.io/badge/status-personal_project-blue)

---

## 项目定位

Personal AI OS V2，内部常称为 **hhs 服务**，是一个个人 AI 网关/工作台项目。它不是单纯的聊天页面，而是围绕“个人 AI 操作系统”设计的一套可扩展框架：

- 用一个 Web UI 管理聊天、模型、提示词、工具、Agent、记忆、插件与工作区。
- 后端统一承接 LLM 请求、流式输出、工具调用、事件分发与第三方入口。
- 前端优先自绘组件，尽量保持界面和交互可控。
- 配置、工具、插件、提示词都尽量文件化/模块化，方便长期折腾和迭代。

核心理念：

1. **Everything is Config**：模型、工具、UI、工作区、提示词都尽量配置化。
2. **Everything is Event**：内部能力通过事件总线衔接。
3. **Everything is Plugin**：能力模块尽量插件化、可扩展。
4. **Everything is Stream**：聊天与工具执行结果优先支持流式反馈。

---

## 当前主要能力

### AI 聊天

- 支持前端聊天会话管理。
- 支持后端 OpenAI-compatible Chat API 转发。
- 支持 SSE 流式输出。
- 支持 Markdown 渲染、代码高亮、KaTeX、Mermaid 等富文本能力。
- 支持消息重试、复制、历史会话加载。
- 支持 AI 消息中的推理内容/思考流与工具流收纳展示。

### 设置中心

- 设置页面支持从后端加载与落盘。
- 支持模型、Provider、Agent 参数、主题、插件、提示词等配置入口。
- 全局设置保存在本地 `storage/settings.json`，默认不会提交到 Git。

### Agent 与工具系统

- 后端有工具 API 与工具注册入口。
- Agent 参数支持独立配置，例如 system prompt、temperature、top_p、presence penalty、最大工具调用轮数等。
- 工具调用轨迹可返回给前端展示。

### OneBot / QQ 机器人适配

项目中已包含 OneBot 11 反向 WebSocket 适配代码：

- 后端路由：`/ws/onebot`
- 适配目录：`backend/onebot/`
- Termux/NapCat 部署脚本：`scripts/termux-onebot.sh`

当前属于“代码已就绪，按需部署”的状态。

### 本地 Web 服务

- 后端：FastAPI + Uvicorn
- 前端：Vue 3 + Vite 构建后由后端静态托管
- 默认端口：`8080`
- 默认监听：`0.0.0.0`

---

## 技术栈

### 前端

- Vue 3
- TypeScript
- Vite
- Pinia
- Vue Router
- 自绘 UI 组件库：`frontend/components/ui/`
- Markdown：`marked`
- 代码高亮：`highlight.js`
- 公式：`katex`
- 图表：`mermaid`
- 图标：`lucide-vue-next`

### 后端

- Python 3
- FastAPI
- Uvicorn
- SSE / WebSocket
- 内部 EventBus
- OpenAI-compatible LLM 请求适配

---

## 目录结构

```text
personal-ai-os-v2/
├── backend/                 # FastAPI 后端服务
│   ├── main.py              # 后端入口，注册 API/WS/静态前端
│   ├── chat_api.py          # 聊天与 LLM 调用接口
│   ├── sessions.py          # 会话 API
│   ├── settings_api.py      # 设置读取/保存 API
│   ├── tools_api.py         # 工具 API
│   ├── event/               # 事件总线相关
│   ├── onebot/              # OneBot/QQ 机器人适配
│   └── ...
├── frontend/                # Vue 3 前端
│   ├── pages/               # 页面
│   ├── components/          # 组件
│   │   └── ui/              # 自绘 UI 组件库
│   ├── stores/              # Pinia 状态
│   ├── services/            # 前端 API 调用
│   └── assets/styles/       # 全局样式
├── config/                  # 默认配置模板
├── prompts/                 # 提示词模板
├── runtime/                 # LLM / Agent / Memory / RAG 运行时目录
├── tools/                   # 工具能力目录
├── scripts/                 # 启停、构建、维护脚本
├── docs/                    # 项目文档
├── tests/                   # 测试
└── storage/                 # 本地数据目录，默认不提交 Git
```

---

## 快速启动

> 推荐使用项目内置的 `hhs.sh` 脚本，它会自动构建前端、释放端口、启动后端。

```bash
cd /home/qixi/mcp_agent/workspace/personal-ai-os-v2
./scripts/hhs.sh start
```

启动后访问：

```text
http://localhost:8080
```

在 WSL2/局域网环境下，也可以通过机器内网 IP 访问，例如：

```text
http://10.123.9.78:8080
```

---

## 常用管理命令

```bash
# 启动服务：自动释放端口、构建前端、启动后端
./scripts/hhs.sh start

# 重启服务：推荐日常使用
./scripts/hhs.sh restart

# 停止服务
./scripts/hhs.sh stop

# 只重新构建前端
./scripts/hhs.sh rebuild

# 查看服务状态与日志尾部
./scripts/hhs.sh status
```

日志位置：

```bash
/tmp/hhs.log
```

PID 文件：

```bash
/tmp/hhs.pid
```

默认端口：

```bash
8080
```

可通过环境变量修改端口：

```bash
HHS_PORT=8090 ./scripts/hhs.sh restart
```

---

## 手动开发命令

### 后端

```bash
cd /home/qixi/mcp_agent/workspace/personal-ai-os-v2
python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8080
```

### 前端

```bash
cd frontend
npm install
npm run dev
npm run build
npm run typecheck
```

前端构建产物会输出到：

```text
frontend/dist/
```

后端检测到 `frontend/dist/index.html` 存在时，会自动托管前端页面。

---

## 配置说明

### 默认配置目录

```text
config/
```

其中包含：

- `config/app.yaml`：应用与服务配置
- `config/api.yaml`：API Provider 默认模板
- `config/models.yaml`：模型配置
- `config/agents.yaml`：Agent 配置
- `config/prompts.yaml`：提示词配置
- `config/plugins.yaml`：插件配置
- `config/theme.yaml`：主题配置
- `config/tools.yaml`：工具配置
- `config/workspace.yaml`：工作区配置

### 本地运行时数据

```text
storage/
```

这里保存运行时产生的数据，例如：

- 会话记录
- 用户设置
- 上传文件
- 工作区缓存
- 导出/备份

`storage/` 属于个人数据目录，默认不应该上传公开仓库。

---

## 隐私与敏感信息

项目已经在 `.gitignore` 中忽略常见敏感/运行时目录：

```gitignore
node_modules/
dist/
.env
*.pyc
__pycache__/
.venv/
venv/
*.db
*.sqlite3
storage/conversations/*
storage/files/*
storage/workspace/*
storage/cache/*
storage/exports/*
storage/backups/*
*.log
```

注意：

- `config/api.yaml` 中只保留空的 `api_key: ""` 模板。
- 真正的 API Key 和个人设置通常保存在本地 `storage/settings.json`。
- 聊天记录、历史会话、上传文件等不应提交到 GitHub。
- 提交前可执行下面的命令检查是否误提交敏感文件：

```bash
git ls-files | grep -Ei 'apikey|api_key|token|secret|password|\.env|storage/'
```

---

## API 与入口

常用入口：

```text
GET  /                         前端页面或服务状态
POST /api/v1/chat              聊天请求
GET  /api/v1/settings          读取设置
PUT  /api/v1/settings          保存设置
POST /api/v1/settings/reset    重置设置
WS   /ws/onebot                OneBot 反向 WebSocket
```

更多 API 可参考：

```text
docs/API/endpoints.md
```

---

## Git 使用

当前远程仓库：

```text
git@github.com:qixidalao/personal-ai-os-v2.git
```

日常提交：

```bash
git status
git add README.md
git commit -m "docs: update README"
git push
```

查看最近提交：

```bash
git log --oneline -5
```

---

## 当前状态

已完成/已具备：

- Vue 3 前端框架
- FastAPI 后端框架
- hhs 快捷启停脚本
- 基础聊天 UI
- 会话 API
- 设置 API 与本地落盘
- SSE/WS 基础设施
- EventBus
- 工具 API
- Agent 参数配置
- LLM 思考流/工具流展示
- OneBot 适配代码
- GitHub 远程仓库同步

仍在演进：

- 更丝滑的前端流式输出/打字机体验
- Agent 工作流体验
- 多模态能力
- RAG/记忆系统深度整合
- 插件市场/插件加载机制
- QQ 机器人实际部署流程

---

## Roadmap

- **M1 基础框架**：FastAPI + Vue3 + SSE + 聊天 + 会话
- **M2 事件系统**：统一 EventBus 与事件协议
- **M3 工具系统**：工具注册、调用、轨迹展示
- **M4 配置中心**：设置页面、配置落盘、热更新方向
- **M5 Workspace**：本地工作区与文件能力
- **M6 Memory / RAG**：长期记忆与检索增强
- **M7 Plugin**：插件生态与扩展协议
- **M8 Agent OS**：多 Agent、多入口、多设备协同

---

## License

个人项目，当前未指定开源协议。  
如需正式公开协作，建议后续补充 `LICENSE` 文件。

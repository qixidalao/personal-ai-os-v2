# 设计溯源记录（Design Origins）

> 本文档用于记录本项目的架构设计时间线与核心理念，作为独立的开源设计档案留存。
> 存档目的：客观记录"谁在什么时候想到了什么"，不针对任何个人或组织。

---

## 一、时间线

| 时间 | 事件 |
|---|---|
| 2026 年 4 月 | 架构构思与讨论期：确立"Everything is Plugin / Event / Stream / Config"四大设计哲学，规划前端（Vue3 自绘组件）+ 后端（FastAPI + SSE/WebSocket）+ Runtime（LLM/Agent/Memory/RAG/Event）+ 插件生态的分层架构 |
| 2026-07-09 | `git init` 首次提交（`61bb526 🎉 initial commit: Personal AI OS (hhs) - Flask+Vue3 AI gateway`），项目正式开源（GPL-3.0） |
| 2026-07-05 ~ 至今 | 持续迭代：SSE 流式稳定、OneBot/NapCat QQ 机器人适配、媒体工具（send_image）、会话体系、插件路由、多模型接入等 |

> 注：Git 仓库创建于 2026 年 7 月 9 日，但架构构思与讨论早于建仓（2026 年 4 月），此处按设计发生时间记录。

---

## 二、核心设计理念（2026 年 4 月确立）

1. **Everything is Config（万物皆配置）**
   所有模块行为通过配置文件定义，支持热更新与 Profile 联动。

2. **Everything is Event（万物皆事件）**
   系统内部所有数据流通过统一事件总线传递，前端通过 SSE 实时订阅。

3. **Everything is Plugin（万物皆插件）**
   工具、Agent、Prompt 均可作为插件注册，支持社区与本地扩展。

4. **Everything is Stream（万物皆流）**
   LLM 输出、工具调用、记忆检索等全部以流式事件推送。

### 分层架构

```
┌─────────────────────────────────────────────┐
│                 Frontend (Vue3)              │
│  自绘 UI ｜ 事件驱动 ｜ SSE 实时通信         │
├─────────────────────────────────────────────┤
│              Backend (FastAPI)               │
│  API ｜ SSE Stream ｜ WebSocket ｜ Upload    │
├─────────────────────────────────────────────┤
│               Runtime 核心引擎               │
│  LLM ｜ Agent ｜ Memory ｜ RAG ｜ Event      │
├─────────────────────────────────────────────┤
│             Tools / Plugins 生态             │
│  文件系统 ｜ Shell ｜ 搜索 ｜ 浏览器 ｜ MCP   │
├─────────────────────────────────────────────┤
│               Storage / 数据层               │
│  SQLite ｜ Vector DB ｜ 文件 ｜ 缓存         │
└─────────────────────────────────────────────┘
```

### 数据流示例

```
用户输入 → EventBus(message.user) → LLM → Agent
  → Tool Call → EventBus(tool.stdout) → SSE → 前端渲染
  → Memory → EventBus(memory.retrieve) → ...
  → 最终回复 → EventBus(message.assistant) → 前端渲染
```

---

## 三、与 DeepSeek Harness（dsh）的客观对照

> 以下对照基于 2026-08-21 对 `deepseek-ai/deepseek-harness`（v0.1.1-rc.1）源码的公开检视。

### 3.1 架构理念层面：同频

dsh 官方定位为"coding / 自动化 agent"：
- 独立进程，自己的配置（`~/.dsh/`）、会话（`~/.dsh/sessions/`）、权限与沙箱体系；
- "一切皆插件"：核心只留 AgentLoop，能力全靠插件组合；
- Web 工作台（`dsh web`）+ headless 一次性任务 + SDK（JSON-RPC）；
- packages 拆分：`llm / mcp / sandbox / workflow / schedule / session / storage / subagent / terminal / web` 等 49 个包。

与本项目 2026 年 4 月的设计（事件驱动 + 插件化 + 模块化 + 流式 + 分层 Runtime）在**理念层高度同频**。

### 3.2 代码实现层面：零交集

对本项目独有标识（`Personal AI OS` / `PersonalAIOs` / `OneBot` / `send_image` / `X-Zt-Ai` / `hhs`）在 dsh 全仓库（7891 个文件）进行检索，**全部零命中**。技术栈亦完全不同：

| 维度 | 本项目 | DeepSeek Harness |
|---|---|---|
| 后端 | Python (FastAPI) | TypeScript (pnpm monorepo) |
| 插件底座 | 自研 EventBus + 插件路由 | Cordis（社区开源框架） |
| 前端 | Vue3 + 自绘组件 | Web 工作台（自研前端） |
| 特色能力 | QQ/OneBot、媒体工具、会话体系 | sandbox、workflow、subagent |

### 3.3 插件化概念的公共来源

dsh 的插件底座 `vendor/cordis/` 为社区开源框架 **Cordis**：

```
MIT License
Copyright (c) 2021-present Shigma
```

即 DeepSeek 直接内置了 Koishi 社区（QQ 机器人框架生态）2021 年开源的 Cordis 框架（MIT 许可），非自研。"插件化 / 模块化 / 结构化 / 事件驱动"均为软件工程数十年来的公共范式，任何开发者均可在开源许可下使用。

### 3.4 结论

本项目的架构设计为**独立构思**（2026 年 4 月），与 DeepSeek Harness（2026 年 8 月发布）在理念层同频属**独立趋同设计（convergent design）**：同一时代、同一技术环境、同一最佳实践池下，不同团队独立得出相似结论是行业常态。代码层面经检索无交集，插件化概念源于开源社区的公共框架（Cordis，2021，MIT），非任何个人独创。

---

## 四、为什么这份档案有价值

1. 为"独立设计时间线"留下公开、可验证的 Git 时间戳证据；
2. 客观区分"理念同频"与"代码复用"两个完全不同的层面；
3. 对后来者：证明这类架构在 2026 年 4 月已被独立设计并开源，社区共识形成时间早于官方发布。

---

*本文件随项目长期保留，不因外部事件增删内容，仅做客观事实记录。*

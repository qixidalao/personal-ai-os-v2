# Personal AI OS V2 — 架构概览

## 核心理念

### Everything is Config（万物皆配置）
所有模块行为通过 YAML 配置文件定义，支持热更新和 Profile 联动。

### Everything is Event（万物皆事件）
系统内部所有数据流通过统一事件总线传递，前端通过 SSE 实时订阅。

### Everything is Plugin（万物皆插件）
工具、Agent、Prompt 均可作为插件注册，支持社区和本地扩展。

### Everything is Stream（万物皆流）
LLM 输出、工具调用、记忆检索等全部以流式事件推送。

## 分层架构

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

## 数据流示例

```
用户输入 → EventBus(message.user) → LLM → Agent
  → Tool Call → EventBus(tool.stdout) → SSE → 前端渲染
  → Memory → EventBus(memory.retrieve) → ...
  → 最终回复 → EventBus(message.assistant) → 前端渲染
```

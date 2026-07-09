# Personal AI OS V2

> 运行于 Android Termux 的个人 AI 操作系统

**四个核心原则：**
- Everything is Config（万物皆配置）
- Everything is Event（万物皆事件）
- Everything is Plugin（万物皆插件）
- Everything is Stream（万物皆流）

## 架构概览

```
Personal AI OS
├── frontend/     Vue3 自绘组件前端
├── backend/      FastAPI 后端服务
├── runtime/      LLM / Agent / Memory / RAG 运行时
├── tools/        工具注册中心
├── config/       配置中心（热更新）
├── prompts/      提示词仓库
├── plugins/      插件生态
├── storage/      数据存储
├── scripts/      运维脚本
└── tests/        测试套件
```

## 快速启动

```bash
# 开发模式
bash scripts/dev-start.sh

# 生产模式
bash scripts/restart.sh
```

## Milestone

- M1：基础框架（FastAPI + Vue3 + SSE + 聊天 + SQLite）
- M2：统一事件系统
- M3：工具系统
- M4：配置中心
- M5：Workspace
- M6：记忆与 RAG
- M7：插件生态
- M8：完善体验

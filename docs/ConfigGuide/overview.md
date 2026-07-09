# Personal AI OS — 配置指南

## 配置中心结构

所有配置位于 `config/` 目录，采用 YAML 格式。

### 配置文件列表

| 文件 | 说明 | 热更新 |
|------|------|--------|
| `app.yaml` | 应用主配置 | ✅ |
| `ui.yaml` | 界面配置 | ✅ |
| `theme.yaml` | 主题配色 | ❌ (需刷新) |
| `api.yaml` | API / Provider 配置 | ✅ |
| `models.yaml` | 模型定义 | ✅ |
| `prompts.yaml` | Prompt 配置 | ✅ |
| `agents.yaml` | Agent 配置 | ✅ |
| `tools.yaml` | 工具配置 | ✅ |
| `workspace.yaml` | 工作区配置 | ✅ |
| `memory.yaml` | 记忆配置 | ✅ |
| `rag.yaml` | RAG 配置 | ✅ |
| `plugins.yaml` | 插件配置 | ✅ |
| `shortcuts.yaml` | 快捷键配置 | ✅ |
| `profiles.yaml` | Profile 配置 | ✅ |
| `about.yaml` | 关于信息 | ❌ |
| `dev.yaml` | 开发模式 | ✅ |

## Profile 联动

Profile 可以绑定：
- 使用的模型
- 使用的 Prompt
- 使用的 Agent
- 主题配色
- API Provider

切换 Profile 即可一键切换整套配置。

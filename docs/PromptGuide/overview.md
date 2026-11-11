# Personal AI OS — Prompt 指南

> **历史/参考文档**：本文可能描述早期版本或研究记录，不是当前安装与使用说明。当前版本请先看 [README](../../README.md)、[用户手册](../AIOS-使用手册.md) 和 [执行器接入指南](../AIOS-执行器接入指南.md)。


## Prompt 结构

Prompt 文件存储在 `prompts/` 目录，按分类组织：

```
prompts/
├── system/         # 系统级 System Prompt
│   ├── default.md
│   └── developer.md
├── developer/      # 开发相关 Prompt
├── assistant/      # 助手人格 Prompt
├── coding/         # 编程 Prompt
├── writing/        # 写作 Prompt
├── translate/      # 翻译 Prompt
├── planner/        # 规划 Prompt
├── browser/        # 浏览器 Prompt
├── rag/            # RAG Prompt
├── memory/         # 记忆 Prompt
├── summary/        # 摘要 Prompt
├── vision/         # 视觉 Prompt
└── custom/         # 自定义 Prompt
```

## Prompt 变量

支持以下变量替换：

- `{{model}}` — 当前模型名称
- `{{date}}` — 当前日期
- `{{time}}` — 当前时间
- `{{tools}}` — 可用工具列表
- `{{memory}}` — 记忆摘要
- `{{profile}}` — 当前 Profile 名称

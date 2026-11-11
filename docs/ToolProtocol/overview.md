# Personal AI OS — 工具协议

> **历史/参考文档**：本文可能描述早期版本或研究记录，不是当前安装与使用说明。当前版本请先看 [README](../../README.md)、[用户手册](../AIOS-使用手册.md) 和 [执行器接入指南](../AIOS-执行器接入指南.md)。


## 工具规范

每个工具需要定义：

```yaml
name: "工具名称"
description: "工具描述"
parameters:
  type: object
  properties:
    param1:
      type: string
      description: "参数说明"
      required: true
category: "filesystem"  # 分类
timeout: 30  # 超时（秒）
```

## 内置工具分类

| 分类 | 工具 | 说明 |
|------|------|------|
| filesystem | read_file, write_file, list_dir, delete_file, file_info | 文件操作 |
| shell | shell_exec | 命令执行 |
| python | python_exec | Python 执行 |
| search | web_search | 网络搜索 |
| browser | browser_open | 网页浏览 |
| sqlite | sqlite_query | 数据库查询 |
| git | git_status, git_commit, git_push | Git 操作 |
| termux | notification, tts, clipboard | Termux 特有 |
| mcp | mcp_call | MCP 协议调用 |

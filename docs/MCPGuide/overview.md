# Personal AI OS — MCP 指南

## 什么是 MCP？

MCP (Model Context Protocol) 是一个开放协议，定义了 AI 模型与外部工具/数据源之间的通信标准。

## MCP Client

Personal AI OS 内置 MCP Client，可以连接任意 MCP Server：

- 文件系统 MCP
- 数据库 MCP
- API 网关 MCP
- 自定义 MCP Server

## MCP Server

也可以作为 MCP Server 对外提供服务：

- 通过 MCP 协议暴露系统工具
- 允许外部 AI 客户端调用

## 配置

在 `config/tools.yaml` 中配置 MCP 连接：

```yaml
mcp:
  enabled: true
  servers:
    - name: "filesystem"
      transport: "stdio"
      command: "npx"
      args: ["@modelcontextprotocol/server-filesystem", "/path"]
```

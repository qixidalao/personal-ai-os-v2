# Personal AI OS — 事件协议

## 事件列表

### 系统事件
| 事件类型 | 说明 | 数据 |
|---------|------|------|
| `system.start` | 系统启动 | `{ version }` |
| `system.ready` | 系统就绪 | `{}` |
| `system.stop` | 系统关闭 | `{}` |

### 消息事件
| 事件类型 | 说明 | 数据 |
|---------|------|------|
| `message.user` | 用户消息 | `{ content, session_id }` |
| `message.assistant` | AI 回复 | `{ content, done }` |

### Thinking 事件
| 事件类型 | 说明 | 数据 |
|---------|------|------|
| `thinking.start` | 开始思考 | `{ model }` |
| `thinking.delta` | 思考增量 | `{ content }` |
| `thinking.stop` | 思考结束 | `{ duration }` |

### 工具事件
| 事件类型 | 说明 | 数据 |
|---------|------|------|
| `tool.start` | 工具开始执行 | `{ name, args }` |
| `tool.stdout` | 工具标准输出 | `{ content }` |
| `tool.stderr` | 工具错误输出 | `{ content }` |
| `tool.finish` | 工具执行完成 | `{ name, result, duration }` |

### 观察事件
| 事件类型 | 说明 | 数据 |
|---------|------|------|
| `observation` | 观察结果 | `{ content }` |

### 记忆事件
| 事件类型 | 说明 | 数据 |
|---------|------|------|
| `memory.retrieve` | 检索记忆 | `{ items }` |
| `memory.update` | 更新记忆 | `{ item }` |

### 通知事件
| 事件类型 | 说明 | 数据 |
|---------|------|------|
| `error` | 错误 | `{ message, code }` |
| `warning` | 警告 | `{ message }` |
| `info` | 信息 | `{ message }` |

## SSE 格式

```
event: message.assistant
data: {"content": "你好！", "done": false}

event: message.assistant
data: {"content": "我是 AI 助手", "done": true}
```

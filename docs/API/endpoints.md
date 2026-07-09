# Personal AI OS — API 文档

## 基础路径

```
/api/v1
```

## 端点列表

### 健康检查
```
GET /api/v1/health
→ { status: "ok", version: "2.0.0" }
```

### 流式对话
```
GET /api/v1/stream/chat?session_id=<id>
→ SSE 事件流
```

### 事件流
```
GET /api/v1/stream/events
→ 全部事件 SSE 流
```

### Thinking 流
```
GET /api/v1/stream/thinking
→ Thinking 事件 SSE 流
```

### 配置管理
```
GET    /api/v1/config          → 列出所有配置
GET    /api/v1/config/:name    → 获取单个配置
PUT    /api/v1/config/:name    → 更新配置
POST   /api/v1/config/:name/reload → 热重载
```

### 工具调用
```
GET    /api/v1/tools           → 列出可用工具
POST   /api/v1/tools/call      → 调用工具
```

### 文件上传
```
POST   /api/v1/upload          → 上传文件
GET    /api/v1/files           → 列出文件
```

### 会话管理
```
GET    /api/v1/sessions        → 列出会话
GET    /api/v1/sessions/:id    → 获取会话
DELETE /api/v1/sessions/:id    → 删除会话
```

## WebSocket

```
/ws/chat?session_id=<id>
```

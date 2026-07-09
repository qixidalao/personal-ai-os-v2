# Personal AI OS V2 — 开发路线图

## M1：基础框架 ✅
- [x] FastAPI 后端脚手架
- [x] Vue3 前端脚手架
- [x] SSE 实时通信
- [x] 基础聊天对话
- [x] Markdown 渲染
- [x] SQLite 存储

## M2：统一事件系统
- [ ] EventBus 事件总线
- [x] Stream 编解码器
- [ ] 五流消息（System / Thinking / Tool / Observation / Answer）
- [ ] SSE 前端订阅

## M3：工具系统
- [x] ToolRegistry 工具注册中心
- [x] Filesystem / Shell / Python 工具
- [ ] Browser / Search / SQLite 工具
- [ ] Termux 深度工具
- [ ] MCP 客户端

## M4：配置中心
- [x] YAML 热加载
- [x] 多 Provider 配置
- [x] 多 API Key 支持
- [x] 多模型管理
- [x] 多 Prompt 管理
- [x] 多 Agent 管理
- [x] 多 Profile 管理

## M5：Workspace（Canvas）
- [ ] Monaco 编辑器集成
- [ ] Markdown 实时预览
- [ ] Notebook 交互式环境
- [ ] Terminal 终端
- [ ] Mermaid 图表
- [ ] PDF 预览

## M6：记忆与 RAG
- [ ] SessionMemory 会话记忆
- [ ] ConversationSummary 摘要
- [ ] LongMemory 长期记忆
- [ ] VectorMemory 向量检索
- [ ] FactMemory 事实提取
- [ ] 文档导入与分块

## M7：插件生态
- [ ] MCP Client
- [ ] MCP Server 端
- [ ] 本地插件系统
- [ ] 社区插件市场（预留）

## M8：完善体验
- [ ] 全部自绘 UI 组件
- [ ] 动画与过渡
- [ ] 导入导出
- [ ] 数据备份
- [ ] 一键更新
- [ ] 性能优化
- [ ] Android / Termux 深度适配

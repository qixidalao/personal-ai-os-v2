# Agent Skills、工具与兴趣上下文

HHS 的 Skills 采用可审查的 Markdown 指南。实现参考 Open WebUI 的按需技能读取模型：系统提示只包含启用技能的 id 与简介，模型在任务相关时调用 `read_skill(skill_id)` 读取全文。技能不会每轮都把全部说明塞进上下文，也不会执行技能文件里的代码。

## 添加本地 Skill

在 `skills/<skill-id>/SKILL.md` 新建文件，id 使用小写字母、数字和连字符。文件开头写 YAML front matter：

```markdown
---
name: 网络研究
description: 对时效性话题做有来源、可核验的网络研究
category: research
---

用简洁、可验证的步骤描述任务策略。
```

目录扫描只接受 `SKILL.md`，单文件限制 32 KB。技能通过“能力中心”启用；关闭后模型看不到简介，工具也拒绝读取正文。只放入可信且经过人工审阅的指令，因为模型会把技能内容当作行为指南。

## 用户兴趣

“兴趣与记忆”页面仅保存用户明确输入的兴趣标签，最多 30 项、每项最多 80 字。关闭“允许用于个性化”后，下一条对话不再收到该上下文。HHS 不从普通聊天自动猜测兴趣，也不会因此自动联网；搜索仍由对话中的任务触发。

## 工具开关与执行

Agent 使用 `GET /api/v1/tools` 返回的真实工具注册表。能力中心保存 `agentTools` 启用状态；聊天 API 构造函数定义时会过滤已关闭的工具。关闭的工具仍不能通过工具调用 API 绕过设置。

仓库内同步工具由线程池执行，避免网络 I/O 或较慢的本地操作阻塞 ASGI 事件循环。添加新的工具时应明确副作用、输入范围、超时和错误返回，并为危险操作增加审批边界。

## 参考

- Open WebUI 将 Skills 作为独立的 Agent 能力，并提供按需读取工具；工具与插件的代码在服务端执行，需要把来源和权限视为安全边界：[Skills and Tools](https://docs.openwebui.com/features/extensibility/plugin/tools/)、[Plugin Security](https://docs.openwebui.com/features/extensibility/plugin/)。
- LangGraph 的长期记忆示例将跨会话用户偏好放入独立 Store；HHS 当前先使用本地设置文件保存显式兴趣，后续可迁移到具备命名空间和检索能力的持久化 Profile Store：[Long-term memory](https://docs.langchain.com/oss/python/langgraph/add-memory)。

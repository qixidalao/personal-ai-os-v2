# DeepSeek Harness 借鉴记录

> 日期：2026-08-21
> 项目：DeepSeek 官方开源的 Agent Harness（`npx @deepseek-ai/dsh web`，MIT）
> 核心理念：**一切皆插件**（含 agent loop 本身、模型适配器、工具注册表、会话日志），Cordis 驱动

## 一、Harness 架构精髓

```
一切皆插件（含 agent loop 本身、模型适配器、工具注册表、会话日志）
    ├─ Profiles/Bundles 分层配置，每层可 patch 覆盖
    ├─ 事件三分类：session(持久化事实) / agent(实时) / capability(策略seam)
    ├─ 工具流水线：canonical output schema + UI presenter 分离
    ├─ Spill 溢出存储：超大工具输出落盘，只给模型定位符
    ├─ Approval 审批：ask/never 策略 + 瀑布应答者 + 失败闭合
    ├─ Sandbox 沙箱 + Subprocess + Code runtime
    ├─ SystemPrompt 分节组装（order 约定 + 动态 provider）
    └─ Compaction 上下文压缩 + Token meter + 会话回放重建
```

## 二、对比分析

| 维度 | 我们 personal-ai-os | DeepSeek Harness | 借鉴优先级 |
|------|---------------------|-----------------|-----------|
| 事件引擎 | ✅ EventBus 万物皆事件 | 事件三类 + append-only 持久化 + 回放 | ⭐⭐⭐ |
| 插件化 | ⚠️ plugins 目录 | 所有组件都是插件，卸载可逆撤销 effect | ⭐⭐⭐ |
| 上下文溢出 | ⚠️ pruner/summary 压缩 | **Spill 存储**：超长输出落盘+定位符 | ⭐⭐⭐ ✅已落地 |
| 工具注册 | ⚠️ tools 目录 | ToolDefinition 输出 schema + presenter 分离 | ⭐⭐ |
| 审批 | ❌ 无 | Approval ask/never + fail-closed | ⭐⭐ |
| 系统提示词 | ✅ prompts + PromptGuide | 分节组装 order 约定 | ⭐⭐ |
| 消息结构 | ✅ SSE 流式 | ContentBlock 类型化 + provenance 回放 | ⭐⭐ |
| 会话持久化 | ✅ storage/sessions | session log append-only + 回放 | ⭐⭐ |
| 沙箱 | ✅ tools/python | landlock 沙箱 + 子进程 | ⭐ |
| 前后端契约 | ⚠️ FastAPI+TS 手写 | typert 共享类型 + type-equiv | ⭐⭐⭐ |
| 工程质量 | ⚠️ pytest 基础 | verify-* 脚本矩阵 | ⭐ |

## 三、已落地：Spill 溢出存储

### 背景
现有 `ToolResultPruner` 裁剪超长工具结果时，中间段**直接丢弃**（`[... middle pruned ...]`），数据不可恢复。Harness 的 spill 思路：超长输出**落盘保存**，只给模型 head+定位符，需要时恢复。

### 落地内容

**新增 `runtime/memory/spill.py`**
- `SpillStore`：落盘 `storage/spill/`，返回 `spill://<uuid>` 定位符
- 支持恢复读取 `read(ref)`、删除、TTL 清理、容量统计
- 单文件上限 8MB、默认保留 7 天、最多 500 文件
- 安全：UUID 白名单校验防路径穿越

**升级 `runtime/memory/pruner.py`**
- 新增 `spill_enabled` 开关（默认 True，完全向后兼容）
- 超长时中间段落盘，返回 head + `[...middle spilled to spill://<id>...]` + tail
- `read_spilled(text)`：把定位符还原为完整内容（精确无损）
- 关闭 spill 时行为与原来完全一致

### 效果
- 超长工具输出不再丢数据，模型需要时可恢复完整内容
- 上下文只占 head+tail+定位符，token 占用大幅降低
- 与现有记忆体系无缝集成

### 测试
- 短文本不裁剪 ✅
- 超长文本 spill 落盘 + 定位符 ✅
- 精确恢复 9000 字符无损 ✅
- spill 关闭时退回纯裁剪 ✅
- 模块全部可导入 ✅

## 四、待落地清单（按性价比排序）

1. **事件持久化 + 回放** — 现在 EventBus `_history` 仅内存 1000 条；借鉴 Harness session log append-only 落库（已有 sqlite），重启回放重建状态，解决 OneBot 断线重连丢上下文
2. **可逆插件效果** — 插件卸载自动撤销其注册（事件订阅/工具/定时任务），用 EventBus source 字段做归属追踪
3. **工具输出契约** — 工具声明 canonical output schema，前端 presenter 按 schema 渲染（解决表格/卡片渲染靠猜的问题）
4. **SystemPrompt 分节** — prompts 目录加 order 约定（-100 身份/0 人设/100-199 工具），各节可独立开关
5. **typert 前后端共享类型** — host/client 共享 TS/Python 类型，编译期验证
6. **Approval 审批** — 高危操作 ask/never + fail-closed

## 五、一句话总结

> 我们的项目"万物皆事件"理念已踩对路（Harness 也是这个哲学），差距在工程纵深：持久化回放、溢出管理、可逆插件、契约化工具输出。逐层加固即可，无需重写。

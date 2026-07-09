# Personal AI OS — 插件 SDK 概述

## 插件类型

### 1. Tool 插件
注册新的工具到 ToolRegistry：

```python
from tools import ToolRegistry

@ToolRegistry.register("my_tool", "工具说明", "custom")
def my_tool(param1: str, param2: int) -> dict:
    """工具实现"""
    return {"result": param1 * param2}
```

### 2. Agent 插件
自定义 Agent 行为：

```python
from runtime.agent import BaseAgent, AgentContext

class MyAgent(BaseAgent):
    async def run(self, context: AgentContext) -> dict:
        # 自定义 Agent 逻辑
        pass
```

### 3. LLM Provider 插件
接入新的 LLM 提供者：

```python
from runtime.llm import BaseLLMProvider, LLMConfig

class MyProvider(BaseLLMProvider):
    async def chat(self, messages, **kwargs):
        # 实现聊天接口
        pass
```

### 4. UI 组件插件
注册前端自定义组件（预留）。

"""
Agent 运行时 — Planner / Executor / Observer / Reflector / Retry / Workflow
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class AgentContext:
    """Agent 执行上下文"""
    session_id: str
    messages: List[Dict] = field(default_factory=list)
    tools: List[Dict] = field(default_factory=list)
    config: Dict = field(default_factory=dict)
    state: Dict = field(default_factory=dict)
    max_iterations: int = 25
    max_tool_calls: int = 50
    current_iteration: int = 0
    tool_call_count: int = 0


class BaseAgent:
    """Agent 基类"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.name = config.get("name", "Agent")
        self.model = config.get("model", "gpt-4o")
        self.prompt = config.get("prompt", "default")
        self.tools = config.get("tools", [])
    
    async def run(self, context: AgentContext) -> Dict[str, Any]:
        raise NotImplementedError
    
    async def plan(self, context: AgentContext) -> List[Dict]:
        """规划执行步骤"""
        raise NotImplementedError
    
    async def execute(self, context: AgentContext, step: Dict) -> Dict:
        """执行单个步骤"""
        raise NotImplementedError
    
    async def observe(self, context: AgentContext, result: Dict) -> str:
        """观察执行结果"""
        raise NotImplementedError
    
    async def reflect(self, context: AgentContext) -> str:
        """反思当前状态"""
        raise NotImplementedError

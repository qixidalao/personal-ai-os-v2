"""
LLM 运行时 — 统一模型调用接口
支持 OpenAI / Claude / Gemini / DeepSeek / Qwen / Ollama / 自定义
"""
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Dict, List, Optional
import json


@dataclass
class LLMMessage:
    role: str  # system / user / assistant / tool
    content: str
    tool_calls: Optional[list] = None
    tool_call_id: Optional[str] = None
    name: Optional[str] = None


@dataclass
class LLMConfig:
    provider: str = "openai"
    model: str = "gpt-4o"
    api_key: str = ""
    base_url: str = ""
    temperature: float = 0.7
    max_tokens: int = 4096
    top_p: float = 1.0
    streaming: bool = True


class BaseLLMProvider:
    """LLM 提供者基类"""
    
    def __init__(self, config: LLMConfig):
        self.config = config
    
    async def chat(self, messages: List[LLMMessage], **kwargs) -> Dict[str, Any]:
        raise NotImplementedError
    
    async def chat_stream(self, messages: List[LLMMessage], **kwargs) -> AsyncGenerator[str, None]:
        raise NotImplementedError
    
    async def embed(self, texts: List[str]) -> List[List[float]]:
        raise NotImplementedError


class OpenAIProvider(BaseLLMProvider):
    """OpenAI 兼容接口提供者"""
    
    def __init__(self, config: LLMConfig):
        super().__init__(config)
        from openai import AsyncOpenAI
        self.client = AsyncOpenAI(
            api_key=config.api_key or "sk-placeholder",
            base_url=config.base_url or "https://api.openai.com/v1",
        )
    
    async def chat(self, messages: List[LLMMessage], **kwargs) -> Dict[str, Any]:
        response = await self.client.chat.completions.create(
            model=kwargs.get("model", self.config.model),
            messages=[{"role": m.role, "content": m.content} for m in messages],
            temperature=kwargs.get("temperature", self.config.temperature),
            max_tokens=kwargs.get("max_tokens", self.config.max_tokens),
        )
        return {
            "content": response.choices[0].message.content,
            "role": "assistant",
            "model": response.model,
            "usage": response.usage.model_dump() if response.usage else {},
        }
    
    async def chat_stream(self, messages: List[LLMMessage], **kwargs) -> AsyncGenerator[str, None]:
        stream = await self.client.chat.completions.create(
            model=kwargs.get("model", self.config.model),
            messages=[{"role": m.role, "content": m.content} for m in messages],
            temperature=kwargs.get("temperature", self.config.temperature),
            max_tokens=kwargs.get("max_tokens", self.config.max_tokens),
            stream=True,
        )
        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

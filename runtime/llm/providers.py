"""
LLM Provider 工厂
"""
from typing import Dict, Optional
from runtime.llm import BaseLLMProvider, LLMConfig, OpenAIProvider


class ProviderFactory:
    """Provider 工厂 — 根据配置创建对应的 LLM 提供者"""

    _providers: Dict[str, type] = {
        "openai": OpenAIProvider,
        "claude": OpenAIProvider,  # Claude 兼容 OpenAI 接口
        "gemini": OpenAIProvider,  # Gemini 兼容 OpenAI 接口
        "deepseek": OpenAIProvider,
        "qwen": OpenAIProvider,
        "ollama": OpenAIProvider,
        "lm_studio": OpenAIProvider,
        "openrouter": OpenAIProvider,
        "siliconflow": OpenAIProvider,
        "custom": OpenAIProvider,
    }

    _instances: Dict[str, BaseLLMProvider] = {}

    @classmethod
    def create(cls, config: Dict) -> BaseLLMProvider:
        """创建 Provider 实例"""
        provider_name = config.get("provider", "openai")
        provider_class = cls._providers.get(provider_name, OpenAIProvider)

        llm_config = LLMConfig(
            provider=provider_name,
            model=config.get("model", "gpt-4o"),
            api_key=config.get("api_key", ""),
            base_url=config.get("base_url", ""),
            temperature=config.get("temperature", 0.7),
            max_tokens=config.get("max_tokens", 4096),
            streaming=config.get("streaming", True),
        )

        return provider_class(llm_config)

    @classmethod
    def get(cls, provider_name: str, config: Dict) -> BaseLLMProvider:
        """获取或创建 Provider 实例（缓存）"""
        key = f"{provider_name}:{config.get('model', 'default')}"
        if key not in cls._instances:
            cls._instances[key] = cls.create({**config, "provider": provider_name})
        return cls._instances[key]

    @classmethod
    def clear_cache(cls):
        """清空 Provider 缓存"""
        cls._instances.clear()

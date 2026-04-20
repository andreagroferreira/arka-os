"""Runtime adapters for multi-framework support."""

from core.runtime.base import RuntimeAdapter, RuntimeConfig
from core.runtime.registry import get_adapter, detect_runtime
from core.runtime.llm_provider import (
    AnthropicDirectProvider,
    LLMProvider,
    LLMResponse,
    LLMUnavailable,
    StubProvider,
    SubagentProvider,
    get_llm_provider,
)

__all__ = [
    "AnthropicDirectProvider",
    "LLMProvider",
    "LLMResponse",
    "LLMUnavailable",
    "RuntimeAdapter",
    "RuntimeConfig",
    "StubProvider",
    "SubagentProvider",
    "detect_runtime",
    "get_adapter",
    "get_llm_provider",
]

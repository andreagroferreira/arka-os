"""Runtime adapters for multi-framework support."""

from core.runtime.base import RuntimeAdapter, RuntimeConfig
from core.runtime.registry import get_adapter, detect_runtime

__all__ = ["RuntimeAdapter", "RuntimeConfig", "get_adapter", "detect_runtime"]

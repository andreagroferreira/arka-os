"""Runtime registry — maps runtime IDs to adapter instances."""

from core.runtime.base import RuntimeAdapter
from core.runtime.claude_code import ClaudeCodeAdapter
from core.runtime.codex_cli import CodexCliAdapter
from core.runtime.gemini_cli import GeminiCliAdapter
from core.runtime.cursor import CursorAdapter

_ADAPTERS: dict[str, type[RuntimeAdapter]] = {
    "claude-code": ClaudeCodeAdapter,
    "codex": CodexCliAdapter,
    "gemini": GeminiCliAdapter,
    "cursor": CursorAdapter,
}


def get_adapter(runtime_id: str) -> RuntimeAdapter:
    """Get an adapter instance for the given runtime ID.

    Args:
        runtime_id: One of 'claude-code', 'codex', 'gemini', 'cursor'

    Returns:
        Instantiated RuntimeAdapter for the runtime.

    Raises:
        ValueError: If runtime_id is not recognized.
    """
    adapter_cls = _ADAPTERS.get(runtime_id)
    if adapter_cls is None:
        supported = ", ".join(_ADAPTERS.keys())
        raise ValueError(f"Unknown runtime: {runtime_id}. Supported: {supported}")
    return adapter_cls()


def detect_runtime() -> str:
    """Detect which runtime is currently active.

    Checks environment variables and process context to determine
    which AI runtime is executing this code.

    Returns:
        Runtime ID string.
    """
    import os

    # Check environment variables set by each runtime
    if os.environ.get("CLAUDE_CODE"):
        return "claude-code"
    if os.environ.get("CODEX_CLI"):
        return "codex"
    if os.environ.get("GEMINI_CLI"):
        return "gemini"
    if os.environ.get("CURSOR_SESSION"):
        return "cursor"

    # Check for runtime-specific config directories
    from pathlib import Path

    home = Path.home()
    if (home / ".claude" / "settings.json").exists():
        return "claude-code"
    if (home / ".codex").exists():
        return "codex"
    if (home / ".gemini").exists():
        return "gemini"
    if (home / ".cursor").exists():
        return "cursor"

    # Default to claude-code as primary runtime
    return "claude-code"


def list_runtimes() -> list[dict[str, str]]:
    """List all supported runtimes with their status."""
    results = []
    for runtime_id, adapter_cls in _ADAPTERS.items():
        adapter = adapter_cls()
        config = adapter.get_config()
        results.append({
            "id": runtime_id,
            "name": config.name,
            "config_dir": str(config.config_dir),
            "installed": config.config_dir.exists(),
        })
    return results

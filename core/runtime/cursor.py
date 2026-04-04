"""Cursor runtime adapter.

Cursor AI IDE. Uses .cursorrules for project instructions and .cursor/rules for global rules.
Supports agent mode with tool execution.
"""

from pathlib import Path
from os.path import expanduser

from core.runtime.base import RuntimeAdapter, RuntimeConfig, AgentContext, AgentResult


class CursorAdapter(RuntimeAdapter):
    """Adapter for Cursor AI IDE."""

    def get_config(self) -> RuntimeConfig:
        home = Path(expanduser("~"))
        return RuntimeConfig(
            id="cursor",
            name="Cursor",
            config_dir=home / ".cursor",
            skills_dir=home / ".cursor" / "skills",
            settings_file=home / ".cursor" / "settings.json",
            supports_hooks=False,
            supports_subagents=False,
            supports_mcp=True,
            max_context_tokens=200_000,
        )

    def inject_context(self, layers: dict[str, str]) -> str:
        """Cursor receives context via .cursorrules files."""
        parts = []
        for name, content in layers.items():
            parts.append(f"## {name}\n{content}")
        return "\n\n".join(parts)

    def dispatch_agent(self, context: AgentContext) -> AgentResult:
        """Cursor agent mode handles dispatch internally."""
        return AgentResult(
            agent_id=context.agent_id,
            status="dispatched",
            output=f"Agent {context.agent_id} dispatched via Cursor",
            metadata={"runtime": "cursor"},
        )

    def spawn_subagent(self, context: AgentContext) -> AgentResult:
        """Cursor does not support native subagents."""
        return AgentResult(
            agent_id=context.agent_id,
            status="unsupported",
            output="Cursor does not support subagent spawning. Using single-agent mode.",
            metadata={"runtime": "cursor", "fallback": "single-agent"},
        )

    def read_file(self, path: str) -> str:
        raise NotImplementedError("Use Cursor's native file read")

    def write_file(self, path: str, content: str) -> None:
        raise NotImplementedError("Use Cursor's native file write")

    def edit_file(self, path: str, old: str, new: str) -> None:
        raise NotImplementedError("Use Cursor's native file edit")

    def execute_command(self, command: str, timeout: int = 120) -> tuple[str, int]:
        raise NotImplementedError("Use Cursor's native terminal")

    def search_files(self, pattern: str, path: str = ".") -> list[str]:
        raise NotImplementedError("Use Cursor's native file search")

    def search_content(self, pattern: str, path: str = ".") -> list[str]:
        raise NotImplementedError("Use Cursor's native content search")

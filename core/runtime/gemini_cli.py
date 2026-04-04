"""Gemini CLI runtime adapter.

Google's Gemini CLI. Uses GEMINI.md for instructions and activate_skill for skills.
"""

from pathlib import Path
from os.path import expanduser

from core.runtime.base import RuntimeAdapter, RuntimeConfig, AgentContext, AgentResult


class GeminiCliAdapter(RuntimeAdapter):
    """Adapter for Google's Gemini CLI."""

    def get_config(self) -> RuntimeConfig:
        home = Path(expanduser("~"))
        return RuntimeConfig(
            id="gemini",
            name="Gemini CLI",
            config_dir=home / ".gemini",
            skills_dir=home / ".gemini" / "skills",
            settings_file=home / ".gemini" / "settings.json",
            supports_hooks=False,
            supports_subagents=True,
            supports_mcp=True,
            max_context_tokens=1_000_000,
        )

    def inject_context(self, layers: dict[str, str]) -> str:
        """Gemini receives context via GEMINI.md instruction file."""
        parts = []
        for name, content in layers.items():
            parts.append(f"## {name}\n{content}")
        return "\n\n".join(parts)

    def dispatch_agent(self, context: AgentContext) -> AgentResult:
        return AgentResult(
            agent_id=context.agent_id,
            status="dispatched",
            output=f"Agent {context.agent_id} dispatched via Gemini CLI",
            metadata={"runtime": "gemini"},
        )

    def spawn_subagent(self, context: AgentContext) -> AgentResult:
        return AgentResult(
            agent_id=context.agent_id,
            status="dispatched",
            output=f"Subagent {context.agent_id} spawned via Gemini CLI",
            metadata={"runtime": "gemini", "pattern": "subagent"},
        )

    def read_file(self, path: str) -> str:
        raise NotImplementedError("Use Gemini CLI's native file read")

    def write_file(self, path: str, content: str) -> None:
        raise NotImplementedError("Use Gemini CLI's native file write")

    def edit_file(self, path: str, old: str, new: str) -> None:
        raise NotImplementedError("Use Gemini CLI's native file edit")

    def execute_command(self, command: str, timeout: int = 120) -> tuple[str, int]:
        raise NotImplementedError("Use Gemini CLI's native shell execution")

    def search_files(self, pattern: str, path: str = ".") -> list[str]:
        raise NotImplementedError("Use Gemini CLI's native file search")

    def search_content(self, pattern: str, path: str = ".") -> list[str]:
        raise NotImplementedError("Use Gemini CLI's native content search")

"""OpenCode runtime adapter (Foundation PR-6).

OpenCode (opencode.ai) — open-source terminal AI coding agent with
native agents (markdown, ``~/.config/opencode/agents/``), custom
commands (``commands/``), MCP servers (``opencode.json``), and AGENTS.md
instructions. The installer adapter (installer/adapters/opencode.js)
deploys the generated harness bundle onto those surfaces.

Honesty note: OpenCode ships a headless ``opencode run`` mode, but the
invocation/event shape has NOT been live-verified against a real binary
the way codex_cli.py documents — until that verification lands,
``headless_supported`` stays False (base-adapter conservatism; the
capabilities matrix must never overclaim). Registered follow-up.
"""

from pathlib import Path
from os.path import expanduser
from typing import TYPE_CHECKING

from core.runtime.base import RuntimeAdapter, RuntimeConfig, AgentContext, AgentResult

if TYPE_CHECKING:
    from core.runtime.llm_provider import LLMResponse


class OpenCodeAdapter(RuntimeAdapter):
    """Adapter for OpenCode (terminal AI coding agent)."""

    def get_config(self) -> RuntimeConfig:
        home = Path(expanduser("~"))
        config_dir = home / ".config" / "opencode"
        return RuntimeConfig(
            id="opencode",
            name="OpenCode",
            config_dir=config_dir,
            skills_dir=config_dir / "commands",
            settings_file=config_dir / "opencode.json",
            supports_hooks=False,
            supports_subagents=True,
            supports_mcp=True,
            max_context_tokens=200_000,
        )

    def capabilities(self) -> dict[str, bool]:
        return {
            "agent_dispatch": False,  # native agents exist; no ArkaOS wiring yet
            "headless": False,        # `opencode run` not live-verified yet
            "file_ops": True,         # terminal agent edits files natively
            "hooks": False,           # plugins exist; no PreToolUse/Stop parity
        }

    def inject_context(self, layers: dict[str, str]) -> str:
        """OpenCode reads AGENTS.md and `instructions` config entries."""
        parts = []
        for name, content in layers.items():
            parts.append(f"## {name}\n{content}")
        return "\n\n".join(parts)

    def dispatch_agent(self, context: AgentContext) -> AgentResult:
        """OpenCode selects its own (deployed arka-*) agents internally."""
        return AgentResult(
            agent_id=context.agent_id,
            status="dispatched",
            output=f"Agent {context.agent_id} dispatched via OpenCode",
            metadata={"runtime": "opencode"},
        )

    def spawn_subagent(self, context: AgentContext) -> AgentResult:
        """Native subagents exist (mode: subagent) but ArkaOS cannot
        target them programmatically yet — honest unsupported."""
        return AgentResult(
            agent_id=context.agent_id,
            status="unsupported",
            output=(
                "OpenCode subagents are selected by OpenCode itself; "
                "programmatic ArkaOS dispatch is not wired yet."
            ),
            metadata={"runtime": "opencode", "fallback": "single-agent"},
        )

    def read_file(self, path: str) -> str:
        raise NotImplementedError("Use OpenCode's native file read")

    def write_file(self, path: str, content: str) -> None:
        raise NotImplementedError("Use OpenCode's native file write")

    def edit_file(self, path: str, old: str, new: str) -> None:
        raise NotImplementedError("Use OpenCode's native file edit")

    def execute_command(self, command: str, timeout: int = 120) -> tuple[str, int]:
        raise NotImplementedError("Use OpenCode's native shell tool")

    def search_files(self, pattern: str, path: str = ".") -> list[str]:
        raise NotImplementedError("Use OpenCode's native file search")

    def search_content(self, pattern: str, path: str = ".") -> list[str]:
        raise NotImplementedError("Use OpenCode's native content search")

    def headless_supported(self) -> bool:
        return False

    def headless_complete(
        self,
        prompt: str,
        *,
        max_tokens: int = 2000,
        system: str = "",
    ) -> "LLMResponse":
        raise NotImplementedError(
            "OpenCode `opencode run` exists but its invocation/output "
            "shape is not live-verified yet (codex_cli.py precedent). "
            "Fall back to AnthropicDirectProvider or StubProvider."
        )

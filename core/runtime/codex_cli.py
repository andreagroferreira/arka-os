"""Codex CLI runtime adapter.

OpenAI's Codex CLI. Supports sandboxed execution and file operations.
More limited than Claude Code: no native hooks, no MCP servers.
"""

import shutil
from pathlib import Path
from os.path import expanduser
from typing import TYPE_CHECKING

from core.runtime.base import RuntimeAdapter, RuntimeConfig, AgentContext, AgentResult

if TYPE_CHECKING:
    from core.runtime.llm_provider import LLMResponse


class CodexCliAdapter(RuntimeAdapter):
    """Adapter for OpenAI's Codex CLI."""

    def get_config(self) -> RuntimeConfig:
        home = Path(expanduser("~"))
        return RuntimeConfig(
            id="codex",
            name="Codex CLI",
            config_dir=home / ".codex",
            skills_dir=home / ".codex" / "skills",
            settings_file=home / ".codex" / "settings.json",
            supports_hooks=False,
            supports_subagents=True,
            supports_mcp=False,
            max_context_tokens=200_000,
        )

    def inject_context(self, layers: dict[str, str]) -> str:
        """Codex receives context via AGENTS.md instruction file."""
        parts = []
        for name, content in layers.items():
            parts.append(f"## {name}\n{content}")
        return "\n\n".join(parts)

    def dispatch_agent(self, context: AgentContext) -> AgentResult:
        """Codex dispatches agents via its native agent system."""
        return AgentResult(
            agent_id=context.agent_id,
            status="dispatched",
            output=f"Agent {context.agent_id} dispatched via Codex",
            metadata={"runtime": "codex"},
        )

    def spawn_subagent(self, context: AgentContext) -> AgentResult:
        """Codex supports subagents with fresh context."""
        return AgentResult(
            agent_id=context.agent_id,
            status="dispatched",
            output=f"Subagent {context.agent_id} spawned via Codex",
            metadata={"runtime": "codex", "pattern": "subagent"},
        )

    def read_file(self, path: str) -> str:
        raise NotImplementedError("Use Codex CLI's native file read")

    def write_file(self, path: str, content: str) -> None:
        raise NotImplementedError("Use Codex CLI's native file write")

    def edit_file(self, path: str, old: str, new: str) -> None:
        raise NotImplementedError("Use Codex CLI's native file edit")

    def execute_command(self, command: str, timeout: int = 120) -> tuple[str, int]:
        raise NotImplementedError("Use Codex CLI's native shell execution")

    def search_files(self, pattern: str, path: str = ".") -> list[str]:
        raise NotImplementedError("Use Codex CLI's native file search")

    def search_content(self, pattern: str, path: str = ".") -> list[str]:
        raise NotImplementedError("Use Codex CLI's native content search")

    def headless_supported(self) -> bool:
        # Codex CLI headless invocation syntax is not stable as of
        # 2026-04-20. Until verified, we surface unsupported and let
        # SubagentProvider fall back to AnthropicDirect or stub.
        return False

    def headless_complete(
        self,
        prompt: str,
        *,
        max_tokens: int = 2000,
        system: str = "",
    ) -> "LLMResponse":
        binary = shutil.which("codex")
        if binary is None:
            raise NotImplementedError(
                "codex CLI not found on PATH — install Codex CLI to "
                "enable headless completion."
            )
        # TODO(llm-agnostic): Verify Codex CLI headless invocation
        # syntax (`codex exec "<prompt>"` was the working hypothesis
        # but has not been confirmed for the current release). Until
        # then, refuse rather than guess. Tracked in Task #12 report.
        raise NotImplementedError(
            "Codex CLI headless completion not yet wired — verify CLI "
            "syntax before enabling. See core/runtime/codex_cli.py TODO."
        )

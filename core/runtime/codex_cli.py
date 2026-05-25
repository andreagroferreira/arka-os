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
        # Auto-detect: headless is supported iff the `codex` binary is
        # on PATH. When the operator installs Codex CLI later, this
        # lights up without any code change (the headless_complete()
        # method below already gates on shutil.which() too, so a missing
        # binary will raise cleanly).
        #
        # Note: even when the binary is present, headless_complete()
        # still raises until the invocation syntax is verified locally.
        # See TODO(llm-agnostic) below for the verification checklist.
        return shutil.which("codex") is not None

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
        # TODO(llm-agnostic): Implement real headless completion.
        #
        # Status as of 2026-05-25 (PR60): Codex CLI still not verified
        # in any ArkaOS dev environment. headless_supported() now
        # auto-detects the binary on PATH so this lights up the moment
        # someone installs it — but the actual subprocess call below
        # still needs syntax verification before we can stop refusing.
        #
        # Verification checklist for whoever picks this up:
        #   1. Install:   npm install -g @openai/codex-cli
        #   2. Discover:  codex --help    (confirm non-interactive flag)
        #   3. Pattern:   likely `codex exec "<prompt>"` or
        #                 `codex --prompt "<prompt>" --format json`
        #   4. Wire the subprocess call (mirror the Gemini adapter —
        #      list-form args, 60s timeout, stderr clipped, JSON parse
        #      with plain-text fallback, token estimate on miss).
        #
        # SubagentProvider cleanly falls back to anthropic-direct or
        # stub when this raises, so the chain keeps working.
        raise NotImplementedError(
            "Codex CLI headless mode requires verified invocation syntax. "
            "The `codex` binary is on PATH but ArkaOS has not validated "
            "the non-interactive call shape locally. "
            "Verification steps: `codex --help`, then update "
            "core/runtime/codex_cli.py::headless_complete to call the "
            "discovered subprocess shape. "
            "SubagentProvider will cleanly fall back to anthropic-direct or stub."
        )

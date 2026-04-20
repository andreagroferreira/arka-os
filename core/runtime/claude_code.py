"""Claude Code runtime adapter.

Claude Code is the primary and most capable runtime for ArkaOS.
It supports hooks, subagents (Agent tool), MCP servers, and worktrees.
"""

import json
import shutil
import subprocess
from pathlib import Path
from os.path import expanduser
from typing import TYPE_CHECKING

from core.runtime.base import RuntimeAdapter, RuntimeConfig, AgentContext, AgentResult

if TYPE_CHECKING:
    from core.runtime.llm_provider import LLMResponse


class ClaudeCodeAdapter(RuntimeAdapter):
    """Adapter for Anthropic's Claude Code CLI."""

    def get_config(self) -> RuntimeConfig:
        home = Path(expanduser("~"))
        return RuntimeConfig(
            id="claude-code",
            name="Claude Code",
            config_dir=home / ".claude",
            skills_dir=home / ".claude" / "skills",
            settings_file=home / ".claude" / "settings.json",
            supports_hooks=True,
            supports_subagents=True,
            supports_mcp=True,
            max_context_tokens=1_000_000,
        )

    def inject_context(self, layers: dict[str, str]) -> str:
        """Claude Code receives context via UserPromptSubmit hook.

        The hook script concatenates all layers into a single
        additionalContext string that Claude sees in system-reminder tags.
        """
        parts = []
        for name, content in layers.items():
            parts.append(f"[{name}] {content}")
        return " ".join(parts)

    def dispatch_agent(self, context: AgentContext) -> AgentResult:
        """In Claude Code, agents are dispatched via the Agent tool.

        The orchestrator provides the agent type via subagent_type parameter.
        Claude Code handles the actual execution.
        """
        # This is a specification of intent — actual execution happens
        # through Claude Code's native Agent tool
        return AgentResult(
            agent_id=context.agent_id,
            status="dispatched",
            output=f"Agent {context.agent_id} dispatched for: {context.task}",
            metadata={
                "runtime": "claude-code",
                "subagent_type": context.agent_id,
                "department": context.department,
            },
        )

    def spawn_subagent(self, context: AgentContext) -> AgentResult:
        """Spawn a fresh Claude Code subagent.

        Uses the Agent tool with a complete task description.
        Each subagent gets a fresh 1M token context window.
        """
        return AgentResult(
            agent_id=context.agent_id,
            status="dispatched",
            output=f"Subagent {context.agent_id} spawned for: {context.task}",
            metadata={
                "runtime": "claude-code",
                "pattern": "subagent",
                "fresh_context": True,
            },
        )

    def read_file(self, path: str) -> str:
        """Claude Code uses the Read tool natively."""
        # This maps to the Read tool in Claude Code
        raise NotImplementedError("Use Claude Code's native Read tool")

    def write_file(self, path: str, content: str) -> None:
        """Claude Code uses the Write tool natively."""
        raise NotImplementedError("Use Claude Code's native Write tool")

    def edit_file(self, path: str, old: str, new: str) -> None:
        """Claude Code uses the Edit tool natively."""
        raise NotImplementedError("Use Claude Code's native Edit tool")

    def execute_command(self, command: str, timeout: int = 120) -> tuple[str, int]:
        """Claude Code uses the Bash tool natively."""
        raise NotImplementedError("Use Claude Code's native Bash tool")

    def search_files(self, pattern: str, path: str = ".") -> list[str]:
        """Claude Code uses the Glob tool natively."""
        raise NotImplementedError("Use Claude Code's native Glob tool")

    def search_content(self, pattern: str, path: str = ".") -> list[str]:
        """Claude Code uses the Grep tool natively."""
        raise NotImplementedError("Use Claude Code's native Grep tool")

    def supports_feature(self, feature: str) -> bool:
        """Claude Code supports all features."""
        return True

    def headless_supported(self) -> bool:
        return shutil.which("claude") is not None

    def headless_complete(
        self,
        prompt: str,
        *,
        max_tokens: int = 2000,
        system: str = "",
    ) -> "LLMResponse":
        from core.runtime.llm_provider import LLMUnavailable

        binary = shutil.which("claude")
        if binary is None:
            raise NotImplementedError(
                "claude CLI not found on PATH — install Claude Code to enable "
                "headless completion via this adapter."
            )
        cmd = [binary, "-p", prompt, "--output-format", "json"]
        if system:
            cmd.extend(["--append-system-prompt", system])
        proc = _run_claude_cli(cmd)
        if proc.returncode != 0:
            raise LLMUnavailable(
                f"claude CLI exited {proc.returncode}: {proc.stderr.strip()[:200]}"
            )
        return _parse_claude_cli_output(proc.stdout)


def _run_claude_cli(cmd: list[str]) -> subprocess.CompletedProcess:
    from core.runtime.llm_provider import LLMUnavailable

    try:
        return subprocess.run(
            cmd, capture_output=True, text=True, timeout=60, check=False
        )
    except subprocess.TimeoutExpired as exc:
        raise LLMUnavailable("claude CLI timed out after 60s") from exc
    except OSError as exc:
        raise LLMUnavailable(f"claude CLI subprocess failed: {exc}") from exc


def _parse_claude_cli_output(stdout: str) -> "LLMResponse":
    from core.runtime.llm_provider import LLMResponse

    payload = json.loads(stdout) if stdout.strip() else {}
    text = str(payload.get("result") or payload.get("response") or "")
    usage = payload.get("usage") or {}
    tokens_in = int(usage.get("input_tokens") or 0)
    tokens_out = int(usage.get("output_tokens") or 0)
    cache_read = int(usage.get("cache_read_input_tokens") or 0)
    cache_write = int(usage.get("cache_creation_input_tokens") or 0)
    total_input = tokens_in + cache_read + cache_write
    model = str(payload.get("model") or "")
    return LLMResponse(
        text=text,
        tokens_in=total_input,
        tokens_out=tokens_out,
        cached_tokens=cache_read,
        model=model,
    )


# Backward compatibility alias — tests and external importers that used
# the old helper name continue to work without modification.
_parse_claude_json = _parse_claude_cli_output

"""Claude Code runtime adapter.

Claude Code is the primary and most capable runtime for ArkaOS.
It supports hooks, subagents (Agent tool), MCP servers, and worktrees.
"""

from pathlib import Path
from os.path import expanduser

from core.runtime.base import RuntimeAdapter, RuntimeConfig, AgentContext, AgentResult


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

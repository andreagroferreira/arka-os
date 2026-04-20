"""Abstract runtime adapter interface.

Every AI runtime (Claude Code, Codex CLI, Gemini CLI, Cursor) must implement
this interface. The adapter translates ArkaOS operations into runtime-specific
commands and configurations.

Design: Strategy pattern. The orchestrator calls adapter methods without
knowing which runtime is active. Each adapter handles the translation.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from core.runtime.llm_provider import LLMResponse


@dataclass
class RuntimeConfig:
    """Configuration for a specific runtime environment."""

    id: str
    name: str
    config_dir: Path
    skills_dir: Path
    settings_file: Path
    supports_hooks: bool = True
    supports_subagents: bool = True
    supports_mcp: bool = False
    max_context_tokens: int = 200_000


@dataclass
class AgentContext:
    """Context passed to an agent for execution."""

    agent_id: str
    task: str
    department: str
    tier: int
    tools: list[str] = field(default_factory=list)
    files: list[str] = field(default_factory=list)
    context_layers: dict[str, str] = field(default_factory=dict)


@dataclass
class AgentResult:
    """Result returned by an agent after execution."""

    agent_id: str
    status: str  # "completed", "failed", "needs_review"
    output: str
    files_modified: list[str] = field(default_factory=list)
    tokens_used: int = 0
    duration_ms: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


class RuntimeAdapter(ABC):
    """Abstract base class for runtime adapters.

    Each supported AI runtime implements this interface to translate
    ArkaOS operations into runtime-specific actions.
    """

    @abstractmethod
    def get_config(self) -> RuntimeConfig:
        """Return runtime configuration."""

    @abstractmethod
    def inject_context(self, layers: dict[str, str]) -> str:
        """Inject context layers into the runtime.

        Args:
            layers: Dict of layer_name -> context_string

        Returns:
            The formatted context string for this runtime.
        """

    @abstractmethod
    def dispatch_agent(self, context: AgentContext) -> AgentResult:
        """Dispatch a task to an agent.

        Args:
            context: The agent context with task, tools, and files.

        Returns:
            AgentResult with output and metadata.
        """

    @abstractmethod
    def spawn_subagent(self, context: AgentContext) -> AgentResult:
        """Spawn a fresh subagent for isolated task execution.

        Each subagent gets a fresh context window (the subagent pattern).

        Args:
            context: The agent context for the subagent.

        Returns:
            AgentResult from the subagent.
        """

    @abstractmethod
    def read_file(self, path: str) -> str:
        """Read a file through the runtime."""

    @abstractmethod
    def write_file(self, path: str, content: str) -> None:
        """Write a file through the runtime."""

    @abstractmethod
    def edit_file(self, path: str, old: str, new: str) -> None:
        """Edit a file through the runtime (find and replace)."""

    @abstractmethod
    def execute_command(self, command: str, timeout: int = 120) -> tuple[str, int]:
        """Execute a shell command through the runtime.

        Returns:
            Tuple of (output, exit_code).
        """

    @abstractmethod
    def search_files(self, pattern: str, path: str = ".") -> list[str]:
        """Search for files matching a glob pattern."""

    @abstractmethod
    def search_content(self, pattern: str, path: str = ".") -> list[str]:
        """Search file contents for a regex pattern."""

    def supports_feature(self, feature: str) -> bool:
        """Check if the runtime supports a specific feature.

        Features: hooks, subagents, mcp, parallel_agents, worktrees
        """
        config = self.get_config()
        feature_map = {
            "hooks": config.supports_hooks,
            "subagents": config.supports_subagents,
            "mcp": config.supports_mcp,
        }
        return feature_map.get(feature, False)

    def headless_supported(self) -> bool:
        """Whether this adapter can perform a headless CLI completion.

        Default: False. Override in adapters that implement
        `headless_complete`. `SubagentProvider` consults this before
        attempting a call so the factory can fall back cleanly.
        """
        return False

    def headless_complete(
        self,
        prompt: str,
        *,
        max_tokens: int = 2000,
        system: str = "",
    ) -> "LLMResponse":
        """Run a one-shot headless completion via this runtime's CLI.

        Default implementation raises NotImplementedError — adapters
        that do not have a headless CLI mode (e.g. Cursor) inherit this
        behaviour. Never hardcodes a model.
        """
        raise NotImplementedError(
            f"{self.get_config().name} does not support headless LLM completion"
        )

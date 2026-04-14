"""Subagent Pattern — fresh agent instances per task.

Each subagent gets a fresh context window, preventing context pollution
between tasks. The orchestrator uses only 10-15% of its context to
dispatch and collect results.

Pattern: Orchestrator compacts task description + relevant context into
a brief, dispatches to a subagent, and receives a structured result.

Context budget:
- Orchestrator: 10-15% of context window for dispatch + collection
- Subagent: Full context window for task execution
- Handoff artifact: ~379 tokens per agent switch (compacted persona + task)
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Any

from core.agents.schema import Agent


class SubagentStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


@dataclass
class HandoffArtifact:
    """Compacted context passed from orchestrator to subagent.

    This is the ~379-token artifact that carries everything
    the subagent needs to start working without full history.
    """
    task_id: str
    task_description: str
    agent_id: str
    agent_role: str
    agent_disc: str                  # Compact DISC label
    department: str
    relevant_files: list[str] = field(default_factory=list)
    context_summary: str = ""        # Compacted prior context
    constraints: list[str] = field(default_factory=list)
    expected_output: str = ""
    quality_criteria: list[str] = field(default_factory=list)

    def to_prompt(self) -> str:
        """Convert to a prompt string for the subagent."""
        parts = [
            f"# Task: {self.task_description}",
            f"Agent: {self.agent_id} ({self.agent_role}, {self.agent_disc})",
            f"Department: {self.department}",
        ]
        if self.context_summary:
            parts.append(f"\n## Context\n{self.context_summary}")
        if self.relevant_files:
            parts.append(f"\n## Relevant Files\n" + "\n".join(f"- {f}" for f in self.relevant_files))
        if self.constraints:
            parts.append(f"\n## Constraints\n" + "\n".join(f"- {c}" for c in self.constraints))
        if self.expected_output:
            parts.append(f"\n## Expected Output\n{self.expected_output}")
        if self.quality_criteria:
            parts.append(f"\n## Quality Criteria\n" + "\n".join(f"- {q}" for q in self.quality_criteria))
        return "\n".join(parts)

    @property
    def estimated_tokens(self) -> int:
        """Estimate token count of this artifact."""
        return len(self.to_prompt().split())


@dataclass
class SubagentResult:
    """Result returned by a subagent."""
    task_id: str
    agent_id: str
    status: SubagentStatus
    output: str = ""
    files_modified: list[str] = field(default_factory=list)
    tokens_used: int = 0
    duration_ms: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_summary(self, max_tokens: int = 200) -> str:
        """Compact the result for the orchestrator's context.

        The orchestrator doesn't need the full output, just a summary
        to decide next steps.
        """
        words = self.output.split()
        if len(words) <= max_tokens:
            return self.output
        return " ".join(words[:max_tokens]) + "..."


class SubagentDispatcher:
    """Dispatches tasks to fresh subagent instances.

    The dispatcher creates HandoffArtifacts from agent definitions
    and task descriptions, then delegates to the runtime adapter
    for actual execution.

    Nesting policy: Maximum 1 level of nesting (agent -> subagent).
    Sub-subagent dispatch is not recommended -- creates context fragmentation
    and debugging complexity. If a subagent needs help, it should escalate
    to its squad lead rather than spawning another subagent.
    """

    def __init__(self) -> None:
        self._pending: dict[str, HandoffArtifact] = {}
        self._results: dict[str, SubagentResult] = {}
        self._task_counter: int = 0

    def create_handoff(
        self,
        agent: Agent,
        task_description: str,
        relevant_files: list[str] | None = None,
        context_summary: str = "",
        constraints: list[str] | None = None,
        expected_output: str = "",
    ) -> HandoffArtifact:
        """Create a handoff artifact for a subagent dispatch.

        Args:
            agent: The agent to dispatch to.
            task_description: What the subagent should do.
            relevant_files: File paths the subagent should read.
            context_summary: Compacted context from prior work.
                Required when ARKAOS_STRICT_HANDOFF=1; otherwise emits a
                warning. Use ContextCompactor.build() to construct.
            constraints: Boundaries for the subagent.
            expected_output: What format/content is expected back.

        Returns:
            HandoffArtifact ready for dispatch.
        """
        import os, warnings
        if not context_summary or not context_summary.strip():
            msg = (
                "create_handoff called without context_summary — subagent will "
                "lack prior conversation context. Use ContextCompactor.build() "
                "to construct one. Set ARKAOS_STRICT_HANDOFF=1 to enforce."
            )
            if os.environ.get("ARKAOS_STRICT_HANDOFF") == "1":
                raise ValueError(msg)
            warnings.warn(msg, DeprecationWarning, stacklevel=2)

        self._task_counter += 1
        task_id = f"task-{self._task_counter}"

        disc_label = agent.behavioral_dna.disc.label
        quality = []
        if agent.tier <= 1:
            quality.append("Enterprise-grade quality expected")
        quality.append("Follow SOLID principles")
        quality.append("Human-readable output, no AI patterns")

        artifact = HandoffArtifact(
            task_id=task_id,
            task_description=task_description,
            agent_id=agent.id,
            agent_role=agent.role,
            agent_disc=disc_label,
            department=agent.department,
            relevant_files=relevant_files or [],
            context_summary=context_summary,
            constraints=constraints or [],
            expected_output=expected_output,
            quality_criteria=quality,
        )

        self._pending[task_id] = artifact
        return artifact

    def record_result(self, result: SubagentResult) -> None:
        """Record a subagent's result."""
        self._results[result.task_id] = result
        self._pending.pop(result.task_id, None)

    def get_result(self, task_id: str) -> Optional[SubagentResult]:
        """Get a subagent's result by task ID."""
        return self._results.get(task_id)

    def get_pending(self) -> list[HandoffArtifact]:
        """Get all pending (undispatched) handoffs."""
        return list(self._pending.values())

    def get_all_results(self) -> list[SubagentResult]:
        """Get all collected results."""
        return list(self._results.values())

    @property
    def pending_count(self) -> int:
        return len(self._pending)

    @property
    def completed_count(self) -> int:
        return len(self._results)

    def orchestrator_context_usage(self) -> dict:
        """Estimate how much context the orchestrator is using.

        Target: 10-15% of context window for dispatch + collection.
        """
        dispatch_tokens = sum(a.estimated_tokens for a in self._pending.values())
        result_tokens = sum(
            len(r.to_summary().split()) for r in self._results.values()
        )
        total = dispatch_tokens + result_tokens
        return {
            "dispatch_tokens": dispatch_tokens,
            "result_summary_tokens": result_tokens,
            "total_orchestrator_tokens": total,
            "tasks_dispatched": self._task_counter,
        }

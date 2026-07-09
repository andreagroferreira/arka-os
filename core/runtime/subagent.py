"""Subagent handoff artifact — compacted context per dispatch.

Each subagent gets a fresh context window, preventing context pollution
between tasks. The orchestrator compacts task description + relevant
context into a brief (~379-token) artifact and dispatches via the
runtime's Task tool.

Dispatch itself is orchestrated by the runtime (hooks + skills + Task
tool); the former Python SubagentDispatcher had no production callers
and was removed (see docs/adr/2026-07-09-remove-dead-orchestration.md).
`HandoffArtifact` stays as the measured handoff contract — consumed by
`scripts/bench/harness.py::bench_subagent_handoff` and
`core/runtime/context_compactor.py` builds its `context_summary`.
"""

from dataclasses import dataclass, field


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

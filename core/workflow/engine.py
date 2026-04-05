"""Workflow execution engine.

Executes workflows phase by phase, respecting gates, conditions,
and agent assignments. Enforces the Constitution's sequential validation
and full visibility rules.
"""

from dataclasses import dataclass, field
from typing import Optional, Callable, Any

from core.workflow.schema import (
    Workflow, Phase, PhaseStatus, GateType, Gate,
)


@dataclass
class PhaseResult:
    """Result of executing a single phase."""
    phase_id: str
    status: PhaseStatus
    output: str = ""
    agent_outputs: dict[str, str] = field(default_factory=dict)
    duration_ms: int = 0


@dataclass
class GateResult:
    """Result of evaluating a gate."""
    passed: bool
    gate_type: GateType
    message: str = ""
    verdict: str = ""


class WorkflowEngine:
    """Executes YAML-defined workflows with phase gates and visibility.

    The engine enforces:
    1. Sequential validation — Phase N+1 only starts after N completes
    2. Full visibility — Every phase announces what's starting and what resulted
    3. Quality Gate — Mandatory review before delivery
    4. Gate evaluation — User approval, quality checks, or conditions
    """

    def __init__(
        self,
        on_phase_start: Optional[Callable[[Phase], None]] = None,
        on_phase_complete: Optional[Callable[[Phase, PhaseResult], None]] = None,
        on_gate_check: Optional[Callable[[Gate], GateResult]] = None,
        on_visibility: Optional[Callable[[str], None]] = None,
    ):
        """Initialize the workflow engine.

        Args:
            on_phase_start: Called when a phase begins execution.
            on_phase_complete: Called when a phase finishes.
            on_gate_check: Called to evaluate a gate. Must return GateResult.
            on_visibility: Called to announce status to the user.
        """
        self._on_phase_start = on_phase_start
        self._on_phase_complete = on_phase_complete
        self._on_gate_check = on_gate_check
        self._on_visibility = on_visibility
        self._history: list[PhaseResult] = []

    def announce(self, message: str) -> None:
        """Announce a status message (full visibility rule)."""
        if self._on_visibility:
            self._on_visibility(message)

    def execute(self, workflow: Workflow) -> list[PhaseResult]:
        """Execute a workflow from start to finish.

        Phases run sequentially. Each phase must complete and pass
        its gate before the next phase starts.

        Args:
            workflow: The workflow definition to execute.

        Returns:
            List of PhaseResults for each executed phase.
        """
        workflow.status = PhaseStatus.IN_PROGRESS
        results: list[PhaseResult] = []

        self.announce(
            f"Starting workflow: {workflow.name} "
            f"({len(workflow.phases)} phases, tier: {workflow.tier.value})"
        )

        for i, phase in enumerate(workflow.phases):
            # Check skip condition
            if phase.skip_if and self._evaluate_condition(phase.skip_if):
                phase.status = PhaseStatus.SKIPPED
                self.announce(f"Phase {i}: {phase.name} — SKIPPED (condition met)")
                results.append(PhaseResult(
                    phase_id=phase.id,
                    status=PhaseStatus.SKIPPED,
                    output="Skipped: condition evaluated to true",
                ))
                continue

            # Check dependencies
            if phase.depends_on:
                unmet = [
                    dep for dep in phase.depends_on
                    if not self._is_phase_complete(workflow, dep)
                ]
                if unmet:
                    phase.status = PhaseStatus.BLOCKED
                    self.announce(
                        f"Phase {i}: {phase.name} — BLOCKED "
                        f"(waiting for: {', '.join(unmet)})"
                    )
                    results.append(PhaseResult(
                        phase_id=phase.id,
                        status=PhaseStatus.BLOCKED,
                        output=f"Blocked by: {', '.join(unmet)}",
                    ))
                    continue

            # Execute phase
            self.announce(
                f"Phase {i}: {phase.name} — STARTING "
                f"(agents: {', '.join(a.agent_id for a in phase.agents)})"
            )
            phase.status = PhaseStatus.IN_PROGRESS

            if self._on_phase_start:
                self._on_phase_start(phase)

            result = self._execute_phase(phase)
            results.append(result)

            if result.status == PhaseStatus.FAILED:
                phase.status = PhaseStatus.FAILED
                workflow.status = PhaseStatus.FAILED
                self.announce(f"Phase {i}: {phase.name} — FAILED: {result.output}")
                break

            phase.status = PhaseStatus.COMPLETED
            phase.result = result.output

            if self._on_phase_complete:
                self._on_phase_complete(phase, result)

            self.announce(f"Phase {i}: {phase.name} — COMPLETED")

            # Evaluate gate
            gate_result = self._evaluate_gate(phase.gate)
            if not gate_result.passed:
                self.announce(
                    f"Gate after Phase {i} — REJECTED: {gate_result.message}"
                )
                # Loop back: reset phase to pending for retry
                phase.status = PhaseStatus.PENDING
                results.append(PhaseResult(
                    phase_id=f"{phase.id}_gate",
                    status=PhaseStatus.FAILED,
                    output=f"Gate rejected: {gate_result.message}",
                ))
                workflow.status = PhaseStatus.FAILED
                break

        if workflow.all_phases_complete():
            workflow.status = PhaseStatus.COMPLETED
            self.announce(f"Workflow {workflow.name} — COMPLETED")

        self._history.extend(results)
        return results

    def _execute_phase(self, phase: Phase) -> PhaseResult:
        """Execute a single phase.

        In the real implementation, this dispatches to agents via
        the runtime adapter. Here we return a placeholder result
        that the calling code fills in.
        """
        agent_ids = [a.agent_id for a in phase.agents]
        return PhaseResult(
            phase_id=phase.id,
            status=PhaseStatus.COMPLETED,
            output=f"Phase {phase.name} executed by {', '.join(agent_ids)}",
            agent_outputs={a.agent_id: "completed" for a in phase.agents},
        )

    def _evaluate_gate(self, gate: Gate) -> GateResult:
        """Evaluate a phase gate."""
        if gate.type == GateType.AUTO:
            return GateResult(passed=True, gate_type=GateType.AUTO, message="Auto-pass")

        if self._on_gate_check:
            return self._on_gate_check(gate)

        # Default: pass
        return GateResult(passed=True, gate_type=gate.type, message="Default pass")

    def _evaluate_condition(self, condition: str) -> bool:
        """Evaluate a skip/branch condition.

        For safety, only evaluates simple boolean expressions.
        """
        # In production, this would evaluate against workflow context
        return False

    def _is_phase_complete(self, workflow: Workflow, phase_id: str) -> bool:
        """Check if a specific phase is complete."""
        phase = workflow.get_phase_by_id(phase_id)
        if phase is None:
            return False
        return phase.status in (PhaseStatus.COMPLETED, PhaseStatus.SKIPPED)

    @property
    def history(self) -> list[PhaseResult]:
        """Get the execution history."""
        return self._history

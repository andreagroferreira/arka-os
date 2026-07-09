"""YAML workflow definitions for ArkaOS v2.

Declarative workflows with phases, conditions, gates, and parallelization.
The schema/loader pair is the contract for departments/*/workflows/*.yaml;
execution is orchestrated by the runtime (hooks + skills + Task tool), not
by a Python executor (see docs/adr/2026-07-09-remove-dead-orchestration.md).
"""

from core.workflow.schema import Workflow, Phase, Gate, PhaseStatus
from core.workflow.loader import load_workflow
from core.workflow.state import (
    init_workflow as init_workflow_state,
    get_state as get_workflow_state,
    update_phase,
    set_branch,
    add_violation,
    is_phase_completed,
    clear_workflow,
)

__all__ = [
    "Workflow", "Phase", "Gate", "PhaseStatus", "load_workflow",
    "init_workflow_state", "get_workflow_state", "update_phase", "set_branch",
    "add_violation", "is_phase_completed", "clear_workflow",
]

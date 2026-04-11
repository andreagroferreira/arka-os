"""YAML-based workflow engine for ArkaOS v2.

Declarative workflows with phases, conditions, gates, and parallelization.
"""

from core.workflow.schema import Workflow, Phase, Gate, PhaseStatus
from core.workflow.engine import WorkflowEngine
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
    "Workflow", "Phase", "Gate", "PhaseStatus", "WorkflowEngine", "load_workflow",
    "init_workflow_state", "get_workflow_state", "update_phase", "set_branch",
    "add_violation", "is_phase_completed", "clear_workflow",
]

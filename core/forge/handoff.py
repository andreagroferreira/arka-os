"""Forge handoff — execution path routing and workflow generation."""

import subprocess
import yaml
from core.forge.schema import ExecutionPath, ExecutionPathType, ForgePlan, PlanPhase


def select_execution_path(phases: list[PlanPhase]) -> ExecutionPath:
    """Select the execution path based on phase count and departments.

    Rules: 1 phase, 1 dept → skill | 2-3 phases, 1 dept → workflow | 4+ phases or 2+ depts → enterprise
    """
    departments = list({p.department for p in phases})
    n_phases = len(phases)
    n_depts = len(departments)

    if n_depts >= 2:
        path_type = ExecutionPathType.ENTERPRISE_WORKFLOW
    elif n_phases >= 4:
        path_type = ExecutionPathType.ENTERPRISE_WORKFLOW
    elif n_phases >= 2:
        path_type = ExecutionPathType.WORKFLOW
    else:
        path_type = ExecutionPathType.SKILL

    target = ""
    if path_type == ExecutionPathType.SKILL and departments:
        target = f"arka-{departments[0]}"
    elif path_type in (ExecutionPathType.WORKFLOW, ExecutionPathType.ENTERPRISE_WORKFLOW):
        target = "generated-workflow.yaml"

    return ExecutionPath(
        type=path_type,
        target=target,
        departments=departments,
        estimated_commits=max(1, n_phases * 2),
    )


def generate_workflow_yaml(plan: ForgePlan) -> str:
    """Generate a complete workflow YAML from a forge plan."""
    phases_data = []
    for phase in plan.plan_phases:
        d: dict = {"name": phase.name, "department": phase.department}
        if phase.agents:
            d["agents"] = [{"role": a} for a in phase.agents]
        if phase.deliverables:
            d["deliverables"] = phase.deliverables
        if phase.acceptance_criteria:
            d["acceptance_criteria"] = phase.acceptance_criteria
        if phase.depends_on:
            d["depends_on"] = phase.depends_on
        if phase.context_from_forge:
            d["context_from_forge"] = phase.context_from_forge
        phases_data.append(d)

    workflow = {
        "name": plan.id,
        "type": "enterprise" if len(plan.plan_phases) >= 4 else "focused",
        "generated_by": "forge",
        "forge_plan_id": plan.id,
        "phases": phases_data,
        "quality_gate_required": plan.governance.quality_gate_required,
        "branch": plan.governance.branch_strategy,
    }
    return yaml.dump(workflow, default_flow_style=False, allow_unicode=True)


def _git_changed_files(base: str, current: str) -> list[str]:
    """Return list of files changed between two commits, or [] on error."""
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", base, current],
            capture_output=True, text=True, check=True,
        )
        return [f for f in result.stdout.strip().split("\n") if f]
    except subprocess.CalledProcessError:
        return []


def check_repo_drift(commit_at_forge: str) -> dict:
    """Check if the repo has changed since the forge snapshot."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True,
        )
        current = result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return {"changed": False, "files": [], "message": "Could not read git state"}

    if current == commit_at_forge:
        return {"changed": False, "files": [], "message": "Repo unchanged"}

    files = _git_changed_files(commit_at_forge, current)
    return {
        "changed": True,
        "files": files,
        "message": f"Repo changed: {len(files)} files modified since forge",
    }

"""Forge persistence — YAML plans, Obsidian export, pattern extraction."""

import os
import re as _re
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Optional
import yaml
from core.forge.schema import ForgePlan, ForgeStatus


def _plans_dir() -> Path:
    return Path.home() / ".arkaos" / "plans"


def _active_link() -> Path:
    return _plans_dir() / "active.yaml"


def save_plan(plan: ForgePlan) -> Path:
    """Save a forge plan as YAML. Atomic write."""
    plans = _plans_dir()
    plans.mkdir(parents=True, exist_ok=True)
    target = plans / f"{plan.id}.yaml"
    data = plan.model_dump(mode="json")
    fd = NamedTemporaryFile(mode="w", dir=str(plans), suffix=".tmp", delete=False, encoding="utf-8")
    try:
        yaml.dump(data, fd, default_flow_style=False, allow_unicode=True)
        fd.close()
        os.replace(fd.name, str(target))
    except BaseException:
        fd.close()
        os.unlink(fd.name)
        raise
    return target


def load_plan(plan_id: str) -> Optional[ForgePlan]:
    """Load a forge plan by ID. Returns None if not found."""
    path = _plans_dir() / f"{plan_id}.yaml"
    if not path.exists():
        return None
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return ForgePlan(**data)


def list_plans() -> list[dict]:
    """List all saved plans as summary dicts."""
    plans = _plans_dir()
    if not plans.exists():
        return []
    results = []
    for path in sorted(plans.glob("*.yaml")):
        if path.name == "active.yaml":
            continue
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        results.append({
            "id": data.get("id", path.stem),
            "name": data.get("name", ""),
            "status": data.get("status", "draft"),
            "tier": data.get("complexity", {}).get("tier", "shallow"),
            "confidence": data.get("critic", {}).get("confidence", 0.0),
            "created_at": data.get("created_at", ""),
        })
    return results


def set_active_plan(plan_id: str) -> None:
    """Set a plan as the active forge plan."""
    link = _active_link()
    link.parent.mkdir(parents=True, exist_ok=True)
    link.write_text(plan_id, encoding="utf-8")


def get_active_plan() -> Optional[ForgePlan]:
    """Get the currently active forge plan."""
    link = _active_link()
    if not link.exists():
        return None
    plan_id = link.read_text(encoding="utf-8").strip()
    return load_plan(plan_id)


def clear_active_plan() -> None:
    """Clear the active forge plan."""
    link = _active_link()
    if link.exists():
        link.unlink()


# ---------------------------------------------------------------------------
# Obsidian Export (Task 6)
# ---------------------------------------------------------------------------

def _obsidian_forge_dir() -> Path:
    """Obsidian vault path for Forge documents."""
    return Path.home() / "Documents" / "Personal" / "Projects" / "WizardingCode Internal" / "ArkaOS" / "Forge"


def export_to_obsidian(plan: ForgePlan) -> Path:
    """Export a forge plan as structured Obsidian markdown."""
    forge_dir = _obsidian_forge_dir()
    plans_dir = forge_dir / "Plans"
    plans_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{plan.id.replace('forge-', '')}.md"
    target = plans_dir / filename
    content = _render_obsidian_plan(plan)
    target.write_text(content, encoding="utf-8")
    return target


def _render_obsidian_frontmatter(plan: ForgePlan) -> list[str]:
    """Render YAML frontmatter block for an Obsidian plan note."""
    tags = ["forge", "plan", plan.complexity.tier.value]
    for phase in plan.plan_phases:
        if phase.department not in tags:
            tags.append(phase.department)
    lines = [
        "---",
        f"tags: [{', '.join(tags)}]",
        f"status: {plan.status.value}",
        f"confidence: {plan.critic.confidence}",
        f"complexity: {plan.complexity.score}",
        f"created: {plan.created_at or ''}",
    ]
    if plan.executed_at:
        lines.append(f"executed: {plan.executed_at}")
    lines += ["---", "", f"# {plan.name}", ""]
    return lines


def _render_obsidian_context(plan: ForgePlan) -> list[str]:
    """Render the Context and Prompt sections."""
    ctx = plan.context
    return [
        "## Context",
        f"Repo: {ctx.repo} | Branch: {ctx.branch} | Commit: {ctx.commit_at_forge} | ArkaOS: {ctx.arkaos_version}",
        "",
        "## Prompt",
        f"> {ctx.prompt}",
        "",
    ]


def _render_obsidian_approaches(plan: ForgePlan) -> list[str]:
    """Render the Approaches Explored section."""
    if not plan.approaches:
        return []
    lines = ["## Approaches Explored"]
    for approach in plan.approaches:
        label = approach.explorer.value.title()
        lines.append(f"### {label} Explorer")
        lines.append(approach.summary)
        if approach.key_decisions:
            lines.append("")
            for kd in approach.key_decisions:
                lines.append(f"- **{kd.decision}**: {kd.rationale}")
        lines.append("")
    return lines


def _render_obsidian_critic(plan: ForgePlan) -> list[str]:
    """Render the Critic Synthesis section."""
    critic = plan.critic
    if critic.confidence <= 0:
        return []
    lines = ["## Critic Synthesis", f"**Confidence:** {critic.confidence}", ""]
    if critic.synthesis:
        lines.append("### Adopted Elements")
        for source, elements in critic.synthesis.items():
            for elem in elements:
                lines.append(f"- [{source}] {elem}")
        lines.append("")
    if critic.rejected_elements:
        lines.append("### Rejected Elements")
        for rej in critic.rejected_elements:
            lines.append(f"- **{rej.element}**: {rej.reason}")
        lines.append("")
    if critic.risks:
        lines.append("### Risks")
        for risk in critic.risks:
            lines.append(f"- **{risk.risk}** ({risk.severity.value}) — Mitigation: {risk.mitigation}")
        lines.append("")
    return lines


def _render_obsidian_phases(plan: ForgePlan) -> list[str]:
    """Render the Plan Phases section."""
    if not plan.plan_phases:
        return []
    lines = ["## Plan"]
    for i, phase in enumerate(plan.plan_phases):
        lines.append(f"### Phase {i + 1}: {phase.name}")
        lines.append(f"- **Department:** {phase.department}")
        if phase.agents:
            lines.append(f"- **Agents:** {', '.join(phase.agents)}")
        if phase.deliverables:
            lines.append(f"- **Deliverables:** {', '.join(phase.deliverables)}")
        if phase.acceptance_criteria:
            lines.append("- **Acceptance Criteria:**")
            for ac in phase.acceptance_criteria:
                lines.append(f"  - {ac}")
        lines.append("")
    return lines


def _render_obsidian_execution(plan: ForgePlan) -> list[str]:
    """Render the Execution section."""
    if not plan.execution_path.target:
        return []
    lines = [
        "## Execution",
        f"- **Path:** {plan.execution_path.type.value}",
        f"- **Target:** {plan.execution_path.target}",
    ]
    if plan.governance.branch_strategy:
        lines.append(f"- **Branch:** {plan.governance.branch_strategy}")
    lines.append("")
    return lines


def _render_obsidian_plan(plan: ForgePlan) -> str:
    """Render a ForgePlan as Obsidian markdown with frontmatter."""
    sections = (
        _render_obsidian_frontmatter(plan)
        + _render_obsidian_context(plan)
        + _render_obsidian_approaches(plan)
        + _render_obsidian_critic(plan)
        + _render_obsidian_phases(plan)
        + _render_obsidian_execution(plan)
    )
    return "\n".join(sections)


# ---------------------------------------------------------------------------
# Pattern Extraction (Task 7)
# ---------------------------------------------------------------------------

def extract_patterns(plan: ForgePlan) -> list[dict]:
    """Extract reusable patterns from a completed plan."""
    if plan.status not in (ForgeStatus.COMPLETED, ForgeStatus.ARCHIVED):
        return []
    patterns: list[dict] = []
    if len(plan.plan_phases) >= 2:
        depts = list({p.department for p in plan.plan_phases})
        pattern = {
            "name": _slugify(f"{plan.context.repo}-{'-'.join(depts)}-pattern"),
            "source_plan": plan.id,
            "departments": depts,
            "phase_count": len(plan.plan_phases),
            "phase_names": [p.name for p in plan.plan_phases],
            "tier": plan.complexity.tier.value,
            "reuse_count": 0,
        }
        patterns.append(pattern)
    if patterns:
        _save_patterns_to_obsidian(patterns)
    return patterns


def load_patterns() -> list[dict]:
    """Load all saved patterns from Obsidian."""
    patterns_dir = _obsidian_forge_dir() / "Patterns"
    if not patterns_dir.exists():
        return []
    results = []
    for path in patterns_dir.glob("*.md"):
        content = path.read_text(encoding="utf-8")
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                data = yaml.safe_load(parts[1])
                if data:
                    results.append(data)
    return results


def _save_patterns_to_obsidian(patterns: list[dict]) -> None:
    patterns_dir = _obsidian_forge_dir() / "Patterns"
    patterns_dir.mkdir(parents=True, exist_ok=True)
    for pattern in patterns:
        name = pattern["name"]
        target = patterns_dir / f"{name}.md"
        lines = [
            "---",
            f"name: {name}",
            f"source_plan: {pattern['source_plan']}",
            f"departments: [{', '.join(pattern['departments'])}]",
            f"phase_count: {pattern['phase_count']}",
            f"tier: {pattern['tier']}",
            f"reuse_count: {pattern['reuse_count']}",
            "---",
            "",
            f"# Pattern: {name}",
            "",
            f"Extracted from plan `{pattern['source_plan']}`.",
            "",
            "## Phases",
        ]
        for phase_name in pattern["phase_names"]:
            lines.append(f"- {phase_name}")
        lines.append("")
        target.write_text("\n".join(lines), encoding="utf-8")


def _slugify(text: str) -> str:
    slug = _re.sub(r"[^\w\s-]", "", text.lower())
    return _re.sub(r"[\s_]+", "-", slug).strip("-")

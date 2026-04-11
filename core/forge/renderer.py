"""Forge renderer — terminal ANSI output and HTML companion generator."""

from core.forge.schema import ComplexityScore, CriticVerdict, ExecutionPath, ForgePlan, ForgeTier, PlanPhase


def render_complexity(complexity: ComplexityScore) -> str:
    """Render complexity analysis as terminal output."""
    dims = complexity.dimensions
    tier_label = complexity.tier.value.title()
    explorers = {ForgeTier.SHALLOW: 1, ForgeTier.STANDARD: 2, ForgeTier.DEEP: 3}
    n_exp = explorers[complexity.tier]
    critic = "inline" if complexity.tier == ForgeTier.SHALLOW else "1 Plan Critic"
    lines = [
        f"  Score: {complexity.score}/100 ({tier_label})",
        _render_dimension_table(dims),
        f"  Tier: {tier_label} → {n_exp} explorer(s) + {critic}",
    ]
    if complexity.similar_plans:
        lines.append(f"  Similar plans: {', '.join(complexity.similar_plans)}")
    else:
        lines.append("  Similar plans in Obsidian: none found")
    if complexity.reused_patterns:
        lines.append(f"  Reusing patterns: {', '.join(complexity.reused_patterns)}")
    return "\n".join(lines)


def render_critic_summary(verdict: CriticVerdict) -> str:
    """Render critic verdict summary for terminal."""
    adopted = sum(len(v) for v in verdict.synthesis.values())
    rejected = len(verdict.rejected_elements)
    risks = len(verdict.risks)
    risk_detail = ", ".join(
        f"{sum(1 for r in verdict.risks if r.severity.value == s)} {s}"
        for s in ("high", "medium", "low")
        if any(r.severity.value == s for r in verdict.risks)
    )
    return "\n".join([
        f"  Confidence: {verdict.confidence}",
        f"  ✓ {adopted} elements adopted",
        f"  ✗ {rejected} elements rejected",
        f"  ⚠ {risks} risks identified ({risk_detail})",
    ])


def render_plan_overview(phases: list[PlanPhase], execution_path: ExecutionPath) -> str:
    """Render plan phase summary for terminal."""
    depts = list({p.department for p in phases})
    lines = []
    for i, phase in enumerate(phases):
        bar = "░" * 8
        dep = f"[{phase.department}]"
        deps_str = f" ← {', '.join(phase.depends_on)}" if phase.depends_on else ""
        lines.append(f"  Phase {i + 1}: {phase.name:<35} {dep:<10} {bar}{deps_str}")
    lines.append("")
    lines.append(f"  Execution: {execution_path.type.value} → {execution_path.target}")
    lines.append(f"  Departments: {', '.join(depts)}")
    lines.append(f"  QG required: yes")
    return "\n".join(lines)


def render_terminal(plan: ForgePlan) -> str:
    """Render a complete forge plan for terminal display."""
    lines = [
        f"⚒ FORGE — {plan.name}", "",
        "▸ Context Snapshot",
        f"  Repo: {plan.context.repo} @ {plan.context.commit_at_forge}",
        f"  ArkaOS: {plan.context.arkaos_version} | Branch: {plan.context.branch}", "",
        "▸ Complexity Analysis",
        render_complexity(plan.complexity), "",
    ]
    if plan.critic.confidence > 0:
        lines.extend(["▸ Critic Verdict", render_critic_summary(plan.critic), ""])
    if plan.plan_phases:
        n_depts = len({p.department for p in plan.plan_phases})
        lines.append(f"▸ Plan: {len(plan.plan_phases)} phases across {n_depts} department(s)")
        lines.extend([render_plan_overview(plan.plan_phases, plan.execution_path), ""])
    lines.append("  [A]pprove  [R]evise  [C]ompanion  [D]etail phase  [Q]uit")
    return "\n".join(lines)


def _render_dimension_table(dims) -> str:
    entries = [
        ("Scope", dims.scope),
        ("Deps", dims.dependencies),
        ("Ambig.", dims.ambiguity),
        ("Risk", dims.risk),
        ("Novelty", dims.novelty),
    ]
    lines = []
    for name, value in entries:
        filled = value // 10
        empty = 10 - filled
        bar = "█" * filled + "░" * empty
        lines.append(f"  │ {name:<8}│ {value:>3} │ {bar}")
    return "\n".join(lines)

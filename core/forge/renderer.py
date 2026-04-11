"""Forge renderer — terminal ANSI output and HTML companion generator."""

import math

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


_COMPANION_CSS = """\
:root { --bg: #0d1117; --fg: #c9d1d9; --accent: #58a6ff; --border: #30363d; --green: #3fb950; --red: #f85149; --yellow: #d29922; }
* { margin: 0; padding: 0; box-sizing: border-box; }
body { background: var(--bg); color: var(--fg); font-family: -apple-system, sans-serif; padding: 2rem; max-width: 1200px; margin: 0 auto; }
h1 { color: var(--accent); margin-bottom: 0.5rem; }
h2 { color: var(--fg); margin: 1.5rem 0 0.5rem; border-bottom: 1px solid var(--border); padding-bottom: 0.25rem; }
h3 { color: var(--accent); margin: 1rem 0 0.5rem; }
.meta { color: #8b949e; font-size: 0.9rem; margin-bottom: 1rem; }
.grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; }
.card { background: #161b22; border: 1px solid var(--border); border-radius: 8px; padding: 1rem; }
.badge { display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 0.8rem; margin: 2px; }
.badge-green { background: rgba(63,185,80,0.2); color: var(--green); }
.badge-red { background: rgba(248,81,73,0.2); color: var(--red); }
.badge-yellow { background: rgba(210,153,34,0.2); color: var(--yellow); }
.phase { padding: 0.5rem; border-left: 3px solid var(--accent); margin-bottom: 0.5rem; padding-left: 0.75rem; }
.phase-dept { color: #8b949e; font-size: 0.85rem; }
svg { display: block; margin: 0 auto; }
.approaches { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 1rem; }"""


def should_suggest_companion(tier: ForgeTier) -> str:
    """Determine companion suggestion level. Returns 'none', 'available', or 'suggested'."""
    if tier == ForgeTier.SHALLOW:
        return "none"
    if tier == ForgeTier.STANDARD:
        return "available"
    return "suggested"


def render_html(plan: ForgePlan) -> str:
    """Render a standalone HTML companion for a forge plan."""
    radar_svg = _render_radar_svg(plan.complexity.dimensions)
    phases_html = _render_phases_html(plan.plan_phases)
    critic_html = _render_critic_html(plan.critic)
    approaches_html = _render_approaches_html(plan.approaches)
    ctx = plan.context
    meta = (
        f"{_esc(ctx.repo)} @ {_esc(ctx.commit_at_forge)} | Branch: {_esc(ctx.branch)} "
        f"| ArkaOS {_esc(ctx.arkaos_version)} | Score: {plan.complexity.score}/100 "
        f"({plan.complexity.tier.value.title()})"
    )
    return (
        f'<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
        f'<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>Forge: {_esc(plan.name)}</title>"
        f"<style>\n{_COMPANION_CSS}\n</style></head><body>"
        f"<h1>\u2692 {_esc(plan.name)}</h1>"
        f'<div class="meta">{meta}</div>'
        f'<div class="grid">'
        f'<div class="card"><h2>Complexity Radar</h2>{radar_svg}</div>'
        f'<div class="card"><h2>Critic Verdict</h2>{critic_html}</div>'
        f"</div>"
        f"{approaches_html}"
        f"<h2>Plan Phases</h2>{phases_html}"
        f'<div class="meta" style="margin-top:2rem;text-align:center;">'
        f"Generated by The Forge \u2014 ArkaOS | Read-only companion</div>"
        f"</body></html>"
    )


def _radar_grid_and_axes(cx: int, cy: int, r: int, angles: list[float]) -> str:
    """Render radar background rings and spoke axes."""
    grid = "".join(
        f'<circle cx="{cx}" cy="{cy}" r="{r * pct}" fill="none" stroke="#30363d" stroke-width="0.5"/>'
        for pct in (0.25, 0.5, 0.75, 1.0)
    )
    axes = "".join(
        f'<line x1="{cx}" y1="{cy}" x2="{cx + r * math.cos(a):.1f}" y2="{cy + r * math.sin(a):.1f}" stroke="#30363d" stroke-width="0.5"/>'
        for a in angles
    )
    return grid + axes


def _radar_polygon_and_labels(cx: int, cy: int, r: int, angles: list[float], labels: list[tuple]) -> str:
    """Render radar data polygon and dimension labels."""
    points = " ".join(
        f"{cx + (v / 100) * r * math.cos(angles[i]):.1f},{cy + (v / 100) * r * math.sin(angles[i]):.1f}"
        for i, (_, v) in enumerate(labels)
    )
    polygon = f'<polygon points="{points}" fill="rgba(88,166,255,0.2)" stroke="#58a6ff" stroke-width="2"/>'
    label_elems = ""
    for i, (name, val) in enumerate(labels):
        x = cx + (r + 20) * math.cos(angles[i])
        y = cy + (r + 20) * math.sin(angles[i])
        anchor = "end" if x < cx - 10 else "start" if x > cx + 10 else "middle"
        label_elems += (
            f'<text x="{x:.1f}" y="{y:.1f}" fill="#c9d1d9" font-size="12" '
            f'text-anchor="{anchor}" dominant-baseline="middle">{name} ({val})</text>'
        )
    return polygon + label_elems


def _render_radar_svg(dims) -> str:
    """Render a radar/spider chart SVG for complexity dimensions."""
    cx, cy, r = 150, 150, 120
    labels = [
        ("Scope", dims.scope),
        ("Deps", dims.dependencies),
        ("Ambig.", dims.ambiguity),
        ("Risk", dims.risk),
        ("Novelty", dims.novelty),
    ]
    angles = [i * 2 * math.pi / len(labels) - math.pi / 2 for i in range(len(labels))]
    inner = _radar_grid_and_axes(cx, cy, r, angles) + _radar_polygon_and_labels(cx, cy, r, angles, labels)
    return f'<svg viewBox="0 0 300 300" width="280" height="280">{inner}</svg>'


def _render_phases_html(phases) -> str:
    if not phases:
        return "<p>No phases defined.</p>"
    html = ""
    for i, phase in enumerate(phases):
        deps = f' ← {", ".join(phase.depends_on)}' if phase.depends_on else ""
        html += (
            f'<div class="phase"><strong>Phase {i+1}: {_esc(phase.name)}</strong>{deps}'
            f'<br><span class="phase-dept">{_esc(phase.department)}</span></div>'
        )
    return html


def _render_critic_html(verdict) -> str:
    if verdict.confidence == 0:
        return "<p>No critic analysis.</p>"
    adopted = sum(len(v) for v in verdict.synthesis.values())
    lines = [
        f"<p><strong>Confidence:</strong> {verdict.confidence}</p>",
        f'<p><span class="badge badge-green">✓ {adopted} adopted</span> ',
        f'<span class="badge badge-red">✗ {len(verdict.rejected_elements)} rejected</span> ',
        f'<span class="badge badge-yellow">⚠ {len(verdict.risks)} risks</span></p>',
    ]
    if verdict.rejected_elements:
        lines.append("<h3>Rejected</h3><ul>")
        for rej in verdict.rejected_elements:
            lines.append(f"<li><strong>{_esc(rej.element)}</strong>: {_esc(rej.reason)}</li>")
        lines.append("</ul>")
    if verdict.risks:
        lines.append("<h3>Risks</h3><ul>")
        for risk in verdict.risks:
            lines.append(
                f"<li><strong>{_esc(risk.risk)}</strong> ({risk.severity.value}) — {_esc(risk.mitigation)}</li>"
            )
        lines.append("</ul>")
    return "\n".join(lines)


def _render_approaches_html(approaches) -> str:
    if not approaches:
        return ""
    html = '<h2>Approaches Explored</h2><div class="approaches">'
    for a in approaches:
        html += f'<div class="card"><h3>{a.explorer.value.title()} Explorer</h3><p>{_esc(a.summary)}</p></div>'
    html += "</div>"
    return html


def _esc(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


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

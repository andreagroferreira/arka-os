"""Model Fabric → orchestrator bridge (the consumption layer).

The dashboard and ``npx arkaos models`` write ``~/.arkaos/models.yaml``.
Until now nothing fed that config back to the Claude Code orchestrator,
so changing a role's model changed nothing at dispatch time. This module
turns the config into a compact directive the SessionStart hook injects,
so the orchestrator resolves an agent's model from the user's config
instead of only the agent YAML default.

It is context injection — the same control surface ArkaOS uses for the
constitution, routing, and evidence flow — not a hard rewrite of the Task
`model` param (Claude Code exposes no hook for that). The PostToolUse
telemetry already records the model actually requested per dispatch, so
mismatches are observable (see model_routing_check).
"""

from __future__ import annotations

# Which Model Fabric role governs each kind of agent work. Agents are a
# different taxonomy from roles, so we map by what the agent DOES. The
# orchestrator uses this to pick the role, then resolves the model.
AGENT_ROLE_HINTS: dict[str, str] = {
    # quality-critical
    "architect": "architecture",
    "cto": "architecture",
    "strategist": "strategy",
    "brand-strategist": "strategy",
    "creative-director": "design",
    "visual-designer": "design",
    "frontend-dev": "design",
    "marta-cqo": "quality_gate",
    "eduardo-copy": "quality_gate",
    "francisca-tech": "quality_gate",
    "code-reviewer": "review",
    "security": "review",
    "qa": "review",
    # execution
    "senior-dev": "execution",
    "paulo-tech-lead": "execution",
    "devops": "execution",
    # mechanical
    "analyst": "mechanical",
}


def routing_summary() -> str:
    """One-line role→provider/model@effort summary, or '' if unavailable."""
    try:
        from core.runtime.model_router import resolve_all
        items = resolve_all()
    except Exception:
        return ""
    parts = [
        f"{i.role}={i.provider}/{i.model or '?'}@{i.effort}" for i in items
    ]
    return " ".join(parts)


def routing_directive() -> str:
    """Full SessionStart block: the config plus how to honor it.

    Returns '' when the config cannot be read, so the hook can skip the
    block entirely rather than inject an empty directive.
    """
    summary = routing_summary()
    if not summary:
        return ""

    # When the LiteLLM gateway is live, the alias a subagent is dispatched
    # with is what physically selects the upstream (opus→Anthropic,
    # haiku→Ollama for execution), so the directive names the concrete
    # alias per role. Off, it stays advisory context injection.
    gateway_line = ""
    try:
        from core.runtime.model_routing_check import gateway_healthy

        if gateway_healthy():
            gateway_line = (
                "\nGateway LIVE: the Task model param physically routes the "
                "upstream. Dispatch execution with model=haiku (→ Ollama), "
                "mechanical with model=sonnet, and design/review/architecture/"
                "quality_gate with model=opus (→ Anthropic). strategy is the "
                "main loop model."
            )
    except Exception:
        gateway_line = ""

    # No backticks: this string is embedded in session-start.sh which
    # passes it through $(echo -e "$MSG") — backticks would trigger shell
    # command substitution. Use plain quotes.
    return (
        "[ARKA:MODEL-FABRIC] The operator's model routing (from "
        "~/.arkaos/models.yaml — dashboard / npx arkaos models):\n"
        f"  {summary}\n"
        "When dispatching a subagent via the Task tool, set its model "
        "param from this table by the KIND of work it does (design, "
        "review, architecture, strategy, quality_gate, execution, "
        "mechanical) — this is the user's explicit choice and OVERRIDES "
        "the agent YAML default. Quality roles never downgrade below the "
        "configured model (excellence-mandate). Genuinely mechanical "
        "dispatches (commit messages, formatting) use the mechanical role."
        f"{gateway_line}"
    )

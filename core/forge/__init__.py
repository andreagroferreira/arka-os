"""The Forge — ArkaOS Intelligent Planning Engine."""

from core.forge.schema import (
    ForgeTier,
    ForgeStatus,
    ExplorerLens,
    RiskSeverity,
    ExecutionPathType,
    ComplexityDimensions,
    ComplexityScore,
    KeyDecision,
    PhaseDeliverable,
    ExplorerApproach,
    RejectedElement,
    IdentifiedRisk,
    CriticVerdict,
    ForgeContext,
    PlanPhase,
    ExecutionPath,
    ForgeGovernance,
    ForgePlan,
)

from core.forge.complexity import (
    score_dimensions,
    calculate_weighted_score,
    determine_tier,
    analyze_complexity,
)

from core.forge.persistence import (
    save_plan,
    load_plan,
    list_plans,
    get_active_plan,
    set_active_plan,
    clear_active_plan,
    export_to_obsidian,
    extract_patterns,
    load_patterns,
)

from core.forge.renderer import (
    render_complexity,
    render_critic_summary,
    render_plan_overview,
    render_terminal,
    render_html,
    should_suggest_companion,
)

from core.forge.handoff import (
    select_execution_path,
    generate_workflow_yaml,
    check_repo_drift,
)

__all__ = [
    # schema
    "ForgeTier",
    "ForgeStatus",
    "ExplorerLens",
    "RiskSeverity",
    "ExecutionPathType",
    "ComplexityDimensions",
    "ComplexityScore",
    "KeyDecision",
    "PhaseDeliverable",
    "ExplorerApproach",
    "RejectedElement",
    "IdentifiedRisk",
    "CriticVerdict",
    "ForgeContext",
    "PlanPhase",
    "ExecutionPath",
    "ForgeGovernance",
    "ForgePlan",
    # complexity
    "score_dimensions",
    "calculate_weighted_score",
    "determine_tier",
    "analyze_complexity",
    # persistence
    "save_plan",
    "load_plan",
    "list_plans",
    "get_active_plan",
    "set_active_plan",
    "clear_active_plan",
    "export_to_obsidian",
    "extract_patterns",
    "load_patterns",
    # renderer
    "render_complexity",
    "render_critic_summary",
    "render_plan_overview",
    "render_terminal",
    "render_html",
    "should_suggest_companion",
    # handoff
    "select_execution_path",
    "generate_workflow_yaml",
    "check_repo_drift",
]

"""Built-in orchestration patterns.

Four patterns adapted from claude-skills orchestration protocol,
mapped to ArkaOS department/agent/skill system.
"""

from core.orchestration.protocol import OrchestrationPattern, PatternType


SOLO_SPRINT = OrchestrationPattern(
    type=PatternType.SOLO_SPRINT,
    name="Solo Sprint",
    description="One department lead drives a multi-phase sprint, pulling skills from their squad. Fast, focused execution.",
    when_to_use=[
        "Single-domain task with clear scope",
        "Time-constrained delivery (< 1 week)",
        "One department has all required expertise",
    ],
    structure="Lead → Phase 1 (skills A,B) → Phase 2 (skills C,D) → Quality Gate → Deliver",
    example=(
        "Objective: Launch MVP landing page\n"
        "Lead: Ines (Landing)\n"
        "Phase 1: /landing copy-framework + /landing funnel-design\n"
        "Phase 2: /landing page-build + /landing seo-optimize\n"
        "Phase 3: Quality Gate → Ship"
    ),
    anti_patterns=[
        "Using for cross-department work (use Multi-Agent Handoff instead)",
        "Skipping Quality Gate because 'it's just one department'",
    ],
)

DOMAIN_DEEP_DIVE = OrchestrationPattern(
    type=PatternType.DOMAIN_DEEP_DIVE,
    name="Domain Deep-Dive",
    description="One agent, multiple stacked skills for thorough analysis. Deep expertise over breadth.",
    when_to_use=[
        "Complex technical audit or review",
        "Due diligence or compliance assessment",
        "Research requiring depth in one area",
    ],
    structure="Agent → Skill 1 (foundation) → Skill 2 (analysis) → Skill 3 (recommendations) → Report",
    example=(
        "Objective: Full security assessment\n"
        "Agent: Bruno (Security Engineer)\n"
        "Skills stacked:\n"
        "  1. /dev security-audit (OWASP scan)\n"
        "  2. /dev dependency-audit (CVE check)\n"
        "  3. /dev red-team (attack simulation)\n"
        "  4. /dev ai-security (LLM-specific risks)\n"
        "Output: Consolidated security report with severity rankings"
    ),
    anti_patterns=[
        "Stacking unrelated skills (each skill should build on previous)",
        "Skipping the foundational skill and going straight to advanced",
        "No consolidated output (each skill reports independently)",
    ],
)

MULTI_AGENT_HANDOFF = OrchestrationPattern(
    type=PatternType.MULTI_AGENT_HANDOFF,
    name="Multi-Agent Handoff",
    description="Work flows between departments with structured handoffs. Each department adds its expertise.",
    when_to_use=[
        "Cross-department projects (product launch, brand + marketing)",
        "Sequential expertise needed (strategy → dev → marketing)",
        "Each phase requires different domain knowledge",
    ],
    structure="Dept A → Handoff → Dept B → Handoff → Dept C → Quality Gate → Deliver",
    example=(
        "Objective: Launch new SaaS product\n"
        "Phase 1: Tomas (Strategy) → /strat bmc + /strat five-forces\n"
        "  Handoff: Market validation, pricing strategy, competitive position\n"
        "Phase 2: Paulo (Dev) → /dev spec + /dev feature\n"
        "  Handoff: MVP built, deployed to staging\n"
        "Phase 3: Luna (Marketing) → /mkt growth-plan + /mkt email-sequence\n"
        "  Handoff: Landing page, email funnel, launch plan\n"
        "Phase 4: Quality Gate → Launch"
    ),
    anti_patterns=[
        "No handoff context (next department starts from zero)",
        "Too many departments (>4 phases becomes unwieldy)",
        "Skipping departments that should review (e.g., security for a public launch)",
    ],
)

SKILL_CHAIN = OrchestrationPattern(
    type=PatternType.SKILL_CHAIN,
    name="Skill Chain",
    description="Sequential procedural skills with no specific agent identity. Pure execution pipeline.",
    when_to_use=[
        "Procedural work with well-defined inputs/outputs",
        "Automated pipelines (generate → validate → publish)",
        "No judgment calls needed, just execution",
    ],
    structure="Skill A (input) → Skill B (transform) → Skill C (output) → Done",
    example=(
        "Objective: Content production pipeline\n"
        "Chain:\n"
        "  1. /content hook-write → 10 headline options\n"
        "  2. python scripts/tools/headline_scorer.py → scored + ranked\n"
        "  3. /content viral-design → full post with winning hook\n"
        "  4. /mkt social-strategy → distribution plan\n"
        "No persona needed — pure skill execution"
    ),
    anti_patterns=[
        "Using for work that needs judgment (use Solo Sprint or Handoff)",
        "Long chains with no validation checkpoints",
        "Mixing judgment skills with procedural skills",
    ],
)


PATTERNS = {
    PatternType.SOLO_SPRINT: SOLO_SPRINT,
    PatternType.DOMAIN_DEEP_DIVE: DOMAIN_DEEP_DIVE,
    PatternType.MULTI_AGENT_HANDOFF: MULTI_AGENT_HANDOFF,
    PatternType.SKILL_CHAIN: SKILL_CHAIN,
}


def select_pattern(
    departments_involved: int,
    needs_judgment: bool,
    is_sequential: bool,
) -> PatternType:
    """Recommend an orchestration pattern based on task characteristics."""
    if departments_involved == 1 and needs_judgment:
        return PatternType.SOLO_SPRINT
    if departments_involved == 1 and not needs_judgment:
        return PatternType.SKILL_CHAIN
    if departments_involved > 1 and is_sequential:
        return PatternType.MULTI_AGENT_HANDOFF
    if departments_involved == 1:
        return PatternType.DOMAIN_DEEP_DIVE
    return PatternType.MULTI_AGENT_HANDOFF

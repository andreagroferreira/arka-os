"""Cross-framework consistency validation for agent behavioral DNA.

Not all combinations make sense. A DISC "S" (calm, steady) with Enneagram 8
(challenger, aggressive) would be incoherent. This module validates that
the 4 frameworks form a consistent personality.
"""

from dataclasses import dataclass, field
from core.agents.schema import Agent, DISCType


@dataclass
class ValidationResult:
    """Result of agent consistency validation."""
    is_valid: bool
    score: float  # 0.0 to 1.0
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


# Compatible Enneagram types per DISC primary
DISC_ENNEAGRAM_COMPAT: dict[str, set[int]] = {
    "D": {1, 3, 7, 8},
    "I": {2, 3, 7, 9},
    "S": {2, 6, 9},
    "C": {1, 5, 6},
}

# Compatible MBTI types per DISC primary
DISC_MBTI_COMPAT: dict[str, set[str]] = {
    "D": {"ENTJ", "ESTJ", "INTJ", "ESTP", "ENTP"},
    "I": {"ENFP", "ESFP", "ENFJ", "ENTP", "ESFJ"},
    "S": {"ISFJ", "INFP", "ESFJ", "ISFP", "INFJ"},
    "C": {"INTJ", "ISTJ", "INTP", "ISTP", "INFJ"},
}

# Big Five expectations per DISC primary (range: low/mid/high)
DISC_BIG5_EXPECTATIONS: dict[str, dict[str, str]] = {
    "D": {"extraversion": "mid-high", "agreeableness": "low-mid", "conscientiousness": "mid-high"},
    "I": {"extraversion": "high", "agreeableness": "mid-high", "openness": "mid-high"},
    "S": {"agreeableness": "high", "neuroticism": "low-mid", "extraversion": "low-mid"},
    "C": {"conscientiousness": "high", "openness": "mid-high", "neuroticism": "low-mid"},
}


def _check_range(value: int, expected: str) -> bool:
    """Check if a Big Five value falls within expected range."""
    ranges = {
        "low": (0, 35),
        "low-mid": (0, 55),
        "mid": (30, 70),
        "mid-high": (45, 100),
        "high": (65, 100),
    }
    lo, hi = ranges[expected]
    return lo <= value <= hi


def validate_agent_consistency(agent: Agent) -> ValidationResult:
    """Validate cross-framework consistency of an agent's behavioral DNA.

    Checks:
    1. DISC primary ↔ Enneagram type compatibility
    2. DISC primary ↔ MBTI type compatibility
    3. DISC primary ↔ Big Five expectations
    4. Tier ↔ Authority consistency
    """
    warnings: list[str] = []
    errors: list[str] = []
    checks_passed = 0
    total_checks = 0

    dna = agent.behavioral_dna
    disc_primary = dna.disc.primary.value

    # Check 1: DISC ↔ Enneagram
    total_checks += 1
    compat_enneagram = DISC_ENNEAGRAM_COMPAT.get(disc_primary, set())
    if dna.enneagram.type.value in compat_enneagram:
        checks_passed += 1
    else:
        warnings.append(
            f"DISC {disc_primary} with Enneagram {dna.enneagram.type.value} is unusual. "
            f"Expected: {compat_enneagram}. This may be intentional for a unique personality."
        )

    # Check 2: DISC ↔ MBTI
    total_checks += 1
    compat_mbti = DISC_MBTI_COMPAT.get(disc_primary, set())
    if dna.mbti.type.value in compat_mbti:
        checks_passed += 1
    else:
        warnings.append(
            f"DISC {disc_primary} with MBTI {dna.mbti.type.value} is unusual. "
            f"Expected: {compat_mbti}."
        )

    # Check 3: DISC ↔ Big Five
    expectations = DISC_BIG5_EXPECTATIONS.get(disc_primary, {})
    for trait, expected_range in expectations.items():
        total_checks += 1
        value = getattr(dna.big_five, trait)
        if _check_range(value, expected_range):
            checks_passed += 1
        else:
            warnings.append(
                f"DISC {disc_primary} expects Big Five {trait} in {expected_range} range, "
                f"got {value}. This creates tension in the personality."
            )

    # Check 4: Tier ↔ Authority
    total_checks += 1
    if agent.tier == 0:
        if not agent.authority.veto:
            warnings.append("Tier 0 agents typically have veto power.")
        else:
            checks_passed += 1
    elif agent.tier >= 2:
        if agent.authority.veto:
            errors.append("Tier 2+ agents should not have veto power.")
        else:
            checks_passed += 1
    else:
        checks_passed += 1

    # Check 5: Tier 0 should have escalates_to = None
    total_checks += 1
    if agent.tier == 0 and agent.authority.escalates_to is not None:
        warnings.append("Tier 0 agents are top-level and typically don't escalate.")
    else:
        checks_passed += 1

    score = checks_passed / total_checks if total_checks > 0 else 0.0
    is_valid = len(errors) == 0

    return ValidationResult(
        is_valid=is_valid,
        score=round(score, 2),
        warnings=warnings,
        errors=errors,
    )

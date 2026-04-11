"""Forge complexity scorer — 5-dimension analysis with tier determination."""

import re

from core.forge.schema import ComplexityDimensions, ComplexityScore, ForgeTier

_WEIGHTS = {
    "scope": 0.30,
    "dependencies": 0.25,
    "ambiguity": 0.20,
    "risk": 0.15,
    "novelty": 0.10,
}

_RISK_KEYWORDS = re.compile(
    r"\b(auth\w*|security\w*|encrypt\w*|password\w*|token\w*|secret\w*|permission\w*|migration\w*|database\w*|schema\w*|deploy\w*|infra\w*|production\w*|payment\w*|billing\w*)",
    re.IGNORECASE,
)
_VAGUE_PATTERNS = re.compile(
    r"\b(fix|improve|make.*better|update|change|refactor|clean|optimize)\b",
    re.IGNORECASE,
)


def score_dimensions(
    prompt: str,
    affected_files: list[str],
    departments: list[str],
    similar_plans: list[str],
    reused_patterns: list[str],
) -> ComplexityDimensions:
    """Score all 5 complexity dimensions from prompt and context."""
    return ComplexityDimensions(
        scope=_score_scope(affected_files, departments),
        dependencies=_score_dependencies(affected_files),
        ambiguity=_score_ambiguity(prompt, affected_files),
        risk=_score_risk(prompt, affected_files),
        novelty=_score_novelty(similar_plans, reused_patterns),
    )


def calculate_weighted_score(dims: ComplexityDimensions) -> int:
    """Calculate weighted total score from dimensions."""
    total = (
        dims.scope * _WEIGHTS["scope"]
        + dims.dependencies * _WEIGHTS["dependencies"]
        + dims.ambiguity * _WEIGHTS["ambiguity"]
        + dims.risk * _WEIGHTS["risk"]
        + dims.novelty * _WEIGHTS["novelty"]
    )
    return round(total)


def determine_tier(score: int) -> ForgeTier:
    """Map a 0-100 score to a forge tier."""
    if score <= 30:
        return ForgeTier.SHALLOW
    if score <= 65:
        return ForgeTier.STANDARD
    return ForgeTier.DEEP


def analyze_complexity(
    prompt: str,
    affected_files: list[str],
    departments: list[str],
    similar_plans: list[str],
    reused_patterns: list[str],
) -> ComplexityScore:
    """Full complexity analysis: dimensions, weighted score, tier."""
    dims = score_dimensions(prompt, affected_files, departments, similar_plans, reused_patterns)
    score = calculate_weighted_score(dims)
    tier = determine_tier(score)
    return ComplexityScore(
        score=score,
        tier=tier,
        dimensions=dims,
        similar_plans=similar_plans,
        reused_patterns=reused_patterns,
    )


def _score_scope(files: list[str], departments: list[str]) -> int:
    file_score = min(100, len(files) * 10)
    dept_score = min(100, len(departments) * 30)
    return min(100, (file_score + dept_score) // 2)


def _score_dependencies(files: list[str]) -> int:
    if not files:
        return 20
    core_files = sum(1 for f in files if f.startswith("core/"))
    ratio = core_files / len(files)
    return min(100, int(ratio * 80) + 20)


def _score_ambiguity(prompt: str, files: list[str]) -> int:
    score = 50
    if len(prompt.split()) < 5:
        score += 30
    if not files:
        score += 20
    vague_matches = len(_VAGUE_PATTERNS.findall(prompt))
    score += min(20, vague_matches * 10)
    specific_indicators = len(re.findall(r"[/\.]", prompt))
    score -= min(30, specific_indicators * 5)
    return max(0, min(100, score))


def _score_risk(prompt: str, files: list[str]) -> int:
    score = 20
    risk_matches = len(_RISK_KEYWORDS.findall(prompt))
    score += min(50, risk_matches * 15)
    sensitive_paths = sum(
        1 for f in files if any(kw in f for kw in ("auth", "security", "migration", "deploy", "config"))
    )
    score += min(30, sensitive_paths * 15)
    return min(100, score)


def _score_novelty(similar_plans: list[str], patterns: list[str]) -> int:
    score = 90
    score -= min(40, len(similar_plans) * 20)
    score -= min(30, len(patterns) * 15)
    return max(10, score)

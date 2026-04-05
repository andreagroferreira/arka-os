"""Conclave matcher — selects 5 aligned + 5 contrarian advisors for a user.

The algorithm:
1. Score every advisor against the user's behavioral DNA
2. Sort by match score (high = similar, low = different)
3. Top 5 scores = aligned advisors (think like the user)
4. Bottom 5 scores = contrarian advisors (challenge the user)
5. Ensure at least 2 of 4 DNA frameworks differ for contrarians
"""

from core.conclave.schema import UserProfile, Advisor, AdvisorType, ConclaveBoard
from core.conclave.advisor_db import get_all_advisors


def match_advisors(
    user: UserProfile,
    advisor_pool: list[Advisor] | None = None,
    aligned_count: int = 5,
    contrarian_count: int = 5,
) -> ConclaveBoard:
    """Match advisors to a user's behavioral DNA.

    Args:
        user: The user's profile with behavioral DNA.
        advisor_pool: Custom advisor pool (defaults to built-in database).
        aligned_count: Number of aligned advisors (default 5).
        contrarian_count: Number of contrarian advisors (default 5).

    Returns:
        A ConclaveBoard with aligned and contrarian advisors.
    """
    pool = advisor_pool or get_all_advisors()

    # Score each advisor
    scored = []
    for advisor in pool:
        score = advisor.match_score_to(user.behavioral_dna)
        scored.append((score, advisor))

    # Sort by score: highest first
    scored.sort(key=lambda x: x[0], reverse=True)

    # Top N = aligned (most similar to user)
    aligned = []
    for score, advisor in scored[:aligned_count]:
        advisor = advisor.model_copy()
        advisor.advisor_type = AdvisorType.ALIGNED
        advisor.why_selected = (
            f"Match score {score:.0%} — similar thinking style to yours"
        )
        aligned.append(advisor)

    # Bottom N = contrarian (most different from user)
    contrarian = []
    for score, advisor in scored[-contrarian_count:]:
        advisor = advisor.model_copy()
        advisor.advisor_type = AdvisorType.CONTRARIAN
        advisor.why_selected = (
            f"Match score {score:.0%} — challenges your blind spots"
        )
        contrarian.append(advisor)

    return ConclaveBoard(
        user=user,
        aligned=aligned,
        contrarian=contrarian,
    )


def explain_match(user: UserProfile, advisor: Advisor) -> dict:
    """Explain why a specific advisor was matched.

    Returns a dict with dimension-by-dimension comparison.
    """
    u = user.behavioral_dna
    a = advisor.behavioral_dna

    return {
        "advisor": advisor.name,
        "type": advisor.advisor_type.value,
        "overall_score": advisor.match_score_to(u),
        "disc": {
            "user": f"{u.disc.primary.value}+{u.disc.secondary.value}",
            "advisor": f"{a.disc.primary.value}+{a.disc.secondary.value}",
            "match": u.disc.primary == a.disc.primary,
        },
        "enneagram": {
            "user": f"{u.enneagram.type.value}w{u.enneagram.wing}",
            "advisor": f"{a.enneagram.type.value}w{a.enneagram.wing}",
            "same_center": u.enneagram.center == a.enneagram.center,
        },
        "big_five_diff": {
            "openness": abs(u.big_five.openness - a.big_five.openness),
            "conscientiousness": abs(u.big_five.conscientiousness - a.big_five.conscientiousness),
            "extraversion": abs(u.big_five.extraversion - a.big_five.extraversion),
            "agreeableness": abs(u.big_five.agreeableness - a.big_five.agreeableness),
            "neuroticism": abs(u.big_five.neuroticism - a.big_five.neuroticism),
        },
        "mbti": {
            "user": u.mbti.type.value,
            "advisor": a.mbti.type.value,
            "same_dominant": u.mbti.dominant == a.mbti.dominant,
        },
    }

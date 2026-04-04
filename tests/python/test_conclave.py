"""Tests for The Conclave — Personal AI Advisory Board."""

import pytest

from core.agents.schema import (
    BehavioralDNA, DISCProfile, DISCType,
    EnneagramProfile, EnneagramType,
    BigFiveProfile, MBTIProfile, MBTIType,
)
from core.conclave.schema import (
    UserProfile, Advisor, AdvisorType, ConclaveBoard, MentalModel,
)
from core.conclave.advisor_db import get_all_advisors, get_advisor_by_id, ADVISORS
from core.conclave.matcher import match_advisors, explain_match


# --- Fixtures ---

def make_user_dna(disc_p="D", disc_s="C", enn=5, enn_w=6,
                  o=78, c=85, e=35, a=40, n=25, mbti="INTJ") -> BehavioralDNA:
    return BehavioralDNA(
        disc=DISCProfile(primary=DISCType(disc_p), secondary=DISCType(disc_s)),
        enneagram=EnneagramProfile(type=EnneagramType(enn), wing=enn_w),
        big_five=BigFiveProfile(openness=o, conscientiousness=c, extraversion=e, agreeableness=a, neuroticism=n),
        mbti=MBTIProfile(type=MBTIType(mbti)),
    )


def make_user(disc_p="D", disc_s="C", **kwargs) -> UserProfile:
    return UserProfile(
        name="Test User",
        company="TestCorp",
        role="CEO",
        behavioral_dna=make_user_dna(disc_p, disc_s, **kwargs),
    )


# --- Advisor Database Tests ---

class TestAdvisorDB:
    def test_has_at_least_10_advisors(self):
        assert len(ADVISORS) >= 10

    def test_all_advisors_have_dna(self):
        for a in ADVISORS:
            assert a.behavioral_dna.disc.primary != a.behavioral_dna.disc.secondary
            assert a.behavioral_dna.enneagram.type is not None
            assert a.behavioral_dna.mbti.type is not None

    def test_all_advisors_have_mental_models(self):
        for a in ADVISORS:
            assert len(a.mental_models) >= 2, f"{a.name} needs mental models"

    def test_all_advisors_have_key_questions(self):
        for a in ADVISORS:
            assert len(a.key_questions) >= 1, f"{a.name} needs key questions"

    def test_get_by_id(self):
        munger = get_advisor_by_id("charlie-munger")
        assert munger is not None
        assert munger.name == "Charlie Munger"

    def test_get_by_id_not_found(self):
        assert get_advisor_by_id("nonexistent") is None

    def test_unique_ids(self):
        ids = [a.id for a in ADVISORS]
        assert len(ids) == len(set(ids)), "Duplicate advisor IDs"

    def test_disc_diversity(self):
        """Advisors should cover multiple DISC primaries."""
        primaries = {a.behavioral_dna.disc.primary.value for a in ADVISORS}
        assert len(primaries) >= 3, f"Only {primaries} DISC primaries represented"

    def test_mbti_diversity(self):
        """Advisors should cover multiple MBTI types."""
        types = {a.behavioral_dna.mbti.type.value for a in ADVISORS}
        assert len(types) >= 5, f"Only {len(types)} MBTI types represented"


# --- Match Score Tests ---

class TestMatchScore:
    def test_identical_profile_scores_high(self):
        """An advisor matching the user exactly should score highest."""
        user_dna = make_user_dna()
        # Find advisor most similar to DC/5w6/INTJ
        best = max(ADVISORS, key=lambda a: a.match_score_to(user_dna))
        assert best.match_score_to(user_dna) >= 0.5

    def test_opposite_profile_scores_low(self):
        """An IS profile user should score low with DC advisors."""
        user_dna = make_user_dna(disc_p="I", disc_s="S", enn=2, enn_w=3,
                                  o=85, c=55, e=80, a=80, n=35, mbti="ENFJ")
        # Find advisor with DC profile
        dc_advisors = [a for a in ADVISORS if a.behavioral_dna.disc.primary == DISCType.D]
        if dc_advisors:
            low_match = dc_advisors[0].match_score_to(user_dna)
            assert low_match < 0.8  # Not a perfect match

    def test_score_between_0_and_1(self):
        user_dna = make_user_dna()
        for a in ADVISORS:
            score = a.match_score_to(user_dna)
            assert 0.0 <= score <= 1.0, f"{a.name} score {score} out of range"


# --- Matcher Tests ---

class TestMatcher:
    def test_match_returns_board(self):
        user = make_user()
        board = match_advisors(user)
        assert isinstance(board, ConclaveBoard)

    def test_board_has_5_aligned_5_contrarian(self):
        user = make_user()
        board = match_advisors(user)
        assert len(board.aligned) == 5
        assert len(board.contrarian) == 5
        assert board.size == 10

    def test_aligned_are_most_similar(self):
        user = make_user()
        board = match_advisors(user)
        # Aligned should have higher scores than contrarian
        aligned_scores = [a.match_score_to(user.behavioral_dna) for a in board.aligned]
        contrarian_scores = [a.match_score_to(user.behavioral_dna) for a in board.contrarian]
        assert min(aligned_scores) >= max(contrarian_scores) - 0.1  # Allow small overlap

    def test_aligned_marked_correctly(self):
        user = make_user()
        board = match_advisors(user)
        for a in board.aligned:
            assert a.advisor_type == AdvisorType.ALIGNED

    def test_contrarian_marked_correctly(self):
        user = make_user()
        board = match_advisors(user)
        for a in board.contrarian:
            assert a.advisor_type == AdvisorType.CONTRARIAN

    def test_different_user_gets_different_board(self):
        """Different DNA profiles should get different advisor sets."""
        user_dc = make_user(disc_p="D", disc_s="C", mbti="INTJ")
        user_is = make_user(disc_p="I", disc_s="S", enn=2, enn_w=3,
                            o=85, c=55, e=80, a=80, n=35, mbti="ENFJ")
        board_dc = match_advisors(user_dc)
        board_is = match_advisors(user_is)
        # At least some advisors should be different
        dc_aligned = {a.id for a in board_dc.aligned}
        is_aligned = {a.id for a in board_is.aligned}
        assert dc_aligned != is_aligned, "Same DNA profiles shouldn't get identical boards"

    def test_custom_counts(self):
        user = make_user()
        board = match_advisors(user, aligned_count=3, contrarian_count=3)
        assert len(board.aligned) == 3
        assert len(board.contrarian) == 3

    def test_get_advisor_from_board(self):
        user = make_user()
        board = match_advisors(user)
        first = board.all_advisors[0]
        found = board.get_advisor(first.id)
        assert found is not None
        assert found.id == first.id

    def test_advisor_names(self):
        user = make_user()
        board = match_advisors(user)
        names = board.advisor_names()
        assert len(names["aligned"]) == 5
        assert len(names["contrarian"]) == 5

    def test_why_selected_populated(self):
        user = make_user()
        board = match_advisors(user)
        for a in board.all_advisors:
            assert a.why_selected, f"{a.name} missing why_selected"


# --- Explain Match Tests ---

class TestExplainMatch:
    def test_explain_returns_dimensions(self):
        user = make_user()
        advisor = ADVISORS[0]
        explanation = explain_match(user, advisor)
        assert "disc" in explanation
        assert "enneagram" in explanation
        assert "big_five_diff" in explanation
        assert "mbti" in explanation
        assert "overall_score" in explanation

    def test_explain_disc_comparison(self):
        user = make_user(disc_p="D", disc_s="C")
        munger = get_advisor_by_id("charlie-munger")
        explanation = explain_match(user, munger)
        assert explanation["disc"]["user"] == "D+C"


# --- ConclaveBoard Tests ---

class TestConclaveBoard:
    def test_all_advisors_combines_lists(self):
        user = make_user()
        board = match_advisors(user)
        assert len(board.all_advisors) == 10

    def test_empty_board(self):
        user = make_user()
        board = ConclaveBoard(user=user)
        assert board.size == 0
        assert board.get_advisor("anyone") is None

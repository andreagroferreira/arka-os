"""Tests for the Conclave Profiler — user DNA extraction."""

import pytest

from core.conclave.profiler import (
    get_all_questions, ProfileQuestion, ProfilingSession,
    process_answer, score_disc, score_enneagram, score_big_five,
    score_mbti, build_profile_from_session,
    DISC_QUESTIONS, ENNEAGRAM_QUESTIONS, BIG_FIVE_QUESTIONS, MBTI_QUESTIONS,
)
from core.agents.schema import DISCType, MBTIType
from core.conclave.advisor_db import ADVISORS


class TestProfilingQuestions:
    def test_total_questions(self):
        questions = get_all_questions()
        assert len(questions) >= 17  # 4 DISC + 4 Enn + 5 BF + 4 MBTI

    def test_disc_questions_count(self):
        assert len(DISC_QUESTIONS) == 4

    def test_enneagram_questions_count(self):
        assert len(ENNEAGRAM_QUESTIONS) == 4

    def test_big_five_questions_count(self):
        assert len(BIG_FIVE_QUESTIONS) == 5

    def test_mbti_questions_count(self):
        assert len(MBTI_QUESTIONS) == 4

    def test_every_question_has_options(self):
        for q in get_all_questions():
            assert len(q.options) >= 2, f"{q.id} needs options"
            for opt in q.options:
                assert "label" in opt
                assert "scores" in opt

    def test_unique_question_ids(self):
        ids = [q.id for q in get_all_questions()]
        assert len(ids) == len(set(ids))


class TestProcessAnswer:
    def test_process_first_option(self):
        session = ProfilingSession()
        q = DISC_QUESTIONS[0]
        process_answer(session, q, 0)  # First option = D
        assert "D" in session.scores
        assert session.scores["D"] > 0
        assert q.id in session.answers

    def test_process_all_disc_as_d(self):
        session = ProfilingSession()
        for q in DISC_QUESTIONS:
            process_answer(session, q, 0)  # Always pick first option (D-oriented)
        primary, secondary = score_disc(session)
        assert primary == DISCType.D

    def test_process_all_disc_as_c(self):
        session = ProfilingSession()
        # Pick C-oriented options (index 2 for most, index 3 for some)
        c_indices = [2, 3, 3, 3]  # Map to C options
        for q, idx in zip(DISC_QUESTIONS, c_indices):
            process_answer(session, q, idx)
        primary, _ = score_disc(session)
        assert primary == DISCType.C


class TestScoring:
    def _run_full_session(self, disc_idx=0, enn_idx=0, bf_idx=0, mbti_indices=None):
        """Helper to run a complete profiling session."""
        if mbti_indices is None:
            mbti_indices = [1, 1, 0, 0]  # INTJ

        session = ProfilingSession()
        for q in DISC_QUESTIONS:
            process_answer(session, q, disc_idx)
        for q in ENNEAGRAM_QUESTIONS:
            process_answer(session, q, enn_idx)
        for q in BIG_FIVE_QUESTIONS:
            process_answer(session, q, bf_idx)
        for q, idx in zip(MBTI_QUESTIONS, mbti_indices):
            process_answer(session, q, idx)
        return session

    def test_score_disc_returns_two_types(self):
        session = self._run_full_session(disc_idx=0)
        primary, secondary = score_disc(session)
        assert isinstance(primary, DISCType)
        assert isinstance(secondary, DISCType)
        assert primary != secondary

    def test_score_enneagram_returns_valid_type(self):
        session = self._run_full_session()
        enn_type, wing = score_enneagram(session)
        assert 1 <= enn_type <= 9
        assert 1 <= wing <= 9
        # Wing must be adjacent
        assert wing in {enn_type - 1 if enn_type > 1 else 9, enn_type + 1 if enn_type < 9 else 1}

    def test_score_big_five_returns_valid_range(self):
        session = self._run_full_session()
        bf = score_big_five(session)
        for trait in [bf.openness, bf.conscientiousness, bf.extraversion, bf.agreeableness, bf.neuroticism]:
            assert 0 <= trait <= 100

    def test_score_mbti_intj(self):
        session = self._run_full_session(mbti_indices=[1, 1, 0, 0])  # I, N, T, J
        mbti = score_mbti(session)
        assert mbti == MBTIType.INTJ

    def test_score_mbti_enfp(self):
        session = self._run_full_session(mbti_indices=[0, 1, 1, 1])  # E, N, F, P
        mbti = score_mbti(session)
        assert mbti == MBTIType.ENFP

    def test_build_complete_profile(self):
        session = self._run_full_session()
        profile = build_profile_from_session(session, name="Test", company="Corp", role="CEO")
        assert profile.name == "Test"
        assert profile.behavioral_dna.disc.primary is not None
        assert profile.behavioral_dna.enneagram.type is not None
        assert profile.behavioral_dna.mbti.type is not None
        assert 0 <= profile.behavioral_dna.big_five.openness <= 100


class TestAdvisorExpansion:
    def test_has_20_advisors(self):
        assert len(ADVISORS) == 20

    def test_all_new_advisors_have_dna(self):
        for a in ADVISORS:
            assert a.behavioral_dna.disc.primary != a.behavioral_dna.disc.secondary
            assert len(a.mental_models) >= 2
            assert len(a.key_questions) >= 1

    def test_unique_advisor_ids(self):
        ids = [a.id for a in ADVISORS]
        assert len(ids) == len(set(ids))

    def test_new_advisors_present(self):
        ids = {a.id for a in ADVISORS}
        new_expected = {"warren-buffett", "reed-hastings", "marty-cagan", "alex-hormozi",
                       "april-dunford", "james-clear", "tim-ferriss"}
        assert new_expected.issubset(ids)

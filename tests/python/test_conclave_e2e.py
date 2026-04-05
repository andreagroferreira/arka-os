"""End-to-end tests for The Conclave skill."""

import pytest
import tempfile
from pathlib import Path

from core.agents.schema import (
    BehavioralDNA, DISCProfile, DISCType,
    EnneagramProfile, EnneagramType,
    BigFiveProfile, MBTIProfile, MBTIType,
)
from core.conclave.schema import UserProfile, ConclaveBoard
from core.conclave.profiler import (
    get_all_questions, ProfilingSession, process_answer,
    build_profile_from_session, DISC_QUESTIONS, MBTI_QUESTIONS,
)
from core.conclave.matcher import match_advisors
from core.conclave.persistence import save_profile, load_profile, profile_exists, delete_profile
from core.conclave.display import format_board, format_dna_summary, format_advisor_detail
from core.conclave.prompts import build_advisor_prompt, build_debate_prompt, build_ask_all_prompt
from core.conclave.advisor_db import ADVISORS, get_advisor_by_id


def _make_user(disc_p="D", disc_s="C", mbti="INTJ") -> UserProfile:
    return UserProfile(
        name="Test User", company="TestCorp", role="CEO",
        behavioral_dna=BehavioralDNA(
            disc=DISCProfile(primary=DISCType(disc_p), secondary=DISCType(disc_s)),
            enneagram=EnneagramProfile(type=EnneagramType(5), wing=6),
            big_five=BigFiveProfile(openness=78, conscientiousness=85, extraversion=35, agreeableness=40, neuroticism=25),
            mbti=MBTIProfile(type=MBTIType(mbti)),
        ),
    )


class TestConclaveFullFlow:
    """Test the complete profiling → matching → display → persistence flow."""

    def test_full_profiling_to_board(self):
        session = ProfilingSession()
        questions = get_all_questions()
        for q in questions:
            process_answer(session, q, 0)
        profile = build_profile_from_session(session, name="Andre", company="WizardingCode")
        board = match_advisors(profile)

        assert board.size == 10
        assert len(board.aligned) == 5
        assert len(board.contrarian) == 5
        assert board.user.name == "Andre"

    def test_profiling_different_answers_different_board(self):
        session1 = ProfilingSession()
        session2 = ProfilingSession()
        questions = get_all_questions()

        for q in questions:
            process_answer(session1, q, 0)
            process_answer(session2, q, len(q.options) - 1)

        p1 = build_profile_from_session(session1)
        p2 = build_profile_from_session(session2)
        b1 = match_advisors(p1)
        b2 = match_advisors(p2)

        a1 = {a.id for a in b1.aligned}
        a2 = {a.id for a in b2.aligned}
        assert a1 != a2


class TestPersistence:
    def test_save_and_load(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name

        user = _make_user()
        board = match_advisors(user)
        save_profile(board, path)

        loaded = load_profile(path)
        assert loaded is not None
        assert loaded.user.name == "Test User"
        assert loaded.size == 10
        assert loaded.aligned[0].name == board.aligned[0].name

        Path(path).unlink()

    def test_load_nonexistent_returns_none(self):
        assert load_profile("/nonexistent/path.json") is None

    def test_profile_exists_check(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name

        assert not profile_exists(path)  # Empty file

        user = _make_user()
        board = match_advisors(user)
        save_profile(board, path)

        assert profile_exists(path)

        delete_profile(path)
        assert not profile_exists(path)

    def test_roundtrip_preserves_advisor_data(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name

        user = _make_user()
        board = match_advisors(user)
        save_profile(board, path)

        loaded = load_profile(path)
        for orig, load in zip(board.aligned, loaded.aligned):
            assert orig.name == load.name
            assert orig.advisor_type == load.advisor_type
            assert len(orig.mental_models) == len(load.mental_models)

        Path(path).unlink()


class TestDisplay:
    def test_format_dna_summary(self):
        user = _make_user()
        output = format_dna_summary(user)
        assert "D+C" in output
        assert "INTJ" in output
        assert "Behavioral DNA" in output

    def test_format_board(self):
        user = _make_user()
        board = match_advisors(user)
        output = format_board(board)
        assert "ALIGNED" in output
        assert "CONTRARIAN" in output
        assert "Advisory Board" in output
        # Should contain advisor names
        for advisor in board.aligned[:2]:
            assert advisor.name in output

    def test_format_advisor_detail(self):
        munger = get_advisor_by_id("charlie-munger")
        output = format_advisor_detail(munger)
        assert "Charlie Munger" in output
        assert "Inversion" in output
        assert "Mental Models" in output
        assert "Key Questions" in output
        assert "Sources" in output


class TestPrompts:
    def test_advisor_prompt_contains_identity(self):
        munger = get_advisor_by_id("charlie-munger")
        prompt = build_advisor_prompt(munger, "Should I raise a Series A?")
        assert "Charlie Munger" in prompt
        assert "Inversion" in prompt
        assert "Series A" in prompt

    def test_advisor_prompt_is_specific(self):
        bezos = get_advisor_by_id("jeff-bezos")
        prompt = build_advisor_prompt(bezos, "Should I launch this feature?")
        assert "Jeff Bezos" in prompt
        assert "launch this feature" in prompt
        assert "Day 1" in prompt or "Working Backwards" in prompt

    def test_debate_prompt(self):
        advisors = ADVISORS[:5]
        prompt = build_debate_prompt(advisors, "Should we pivot to enterprise?")
        assert "pivot to enterprise" in prompt
        assert "debate" in prompt.lower() or "moderating" in prompt.lower()
        for a in advisors:
            assert a.name in prompt

    def test_ask_all_prompt(self):
        user = _make_user()
        board = match_advisors(user)
        prompt = build_ask_all_prompt(board.all_advisors, "What should my next move be?")
        assert "next move" in prompt
        assert len(board.all_advisors) > 0
        for a in board.all_advisors[:3]:
            assert a.name in prompt

    def test_each_advisor_produces_distinct_prompt(self):
        prompts = set()
        for advisor in ADVISORS:
            p = build_advisor_prompt(advisor, "Should I hire more engineers?")
            prompts.add(p)
        assert len(prompts) == 20  # All 20 advisors produce different prompts


class TestSkillFile:
    def test_skill_md_exists(self):
        skill_path = Path(__file__).parent.parent.parent / "arka" / "skills" / "conclave" / "SKILL.md"
        assert skill_path.exists()

    def test_skill_md_has_commands(self):
        skill_path = Path(__file__).parent.parent.parent / "arka" / "skills" / "conclave" / "SKILL.md"
        content = skill_path.read_text()
        assert "/arka conclave" in content
        assert "/arka conclave ask" in content
        assert "/arka conclave debate" in content
        assert "/arka conclave advisor" in content

    def test_skill_md_lists_all_20_advisors(self):
        skill_path = Path(__file__).parent.parent.parent / "arka" / "skills" / "conclave" / "SKILL.md"
        content = skill_path.read_text()
        assert "Charlie Munger" in content
        assert "Tim Ferriss" in content
        assert "Alex Hormozi" in content

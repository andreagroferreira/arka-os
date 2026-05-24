"""Tests for core.governance.skill_proposer (PR44 v2.63.0)."""

from __future__ import annotations

from pathlib import Path

import pytest

from core.governance.skill_proposer import SkillProposal, evaluate


class TestBypass:
    def test_trivial_marker_short_circuits(self, tmp_path: Path):
        result = evaluate("[arka:trivial] one-line typo fix", output_dir=tmp_path)
        assert result.should_propose is False
        assert result.reason == "bypass-marker"

    def test_skill_skip_marker_short_circuits(self, tmp_path: Path):
        result = evaluate(
            "[arka:phase:13] done. [arka:skill-skip] one-off cleanup",
            output_dir=tmp_path,
        )
        assert result.should_propose is False


class TestCompletionGate:
    def test_no_completion_signal_no_proposal(self, tmp_path: Path):
        text = (
            "Working on the workflow with multiple phases and a checklist. "
            "Still in flight, no closure yet."
        )
        result = evaluate(text, output_dir=tmp_path)
        assert result.should_propose is False
        assert result.reason == "no-completion-signal"

    def test_phase13_unlocks_proposal(self, tmp_path: Path):
        text = (
            "[arka:phase:13] Built a 10-phase workflow with a template, "
            "a playbook, a checklist, and a procedure for the recurring "
            "task that will be repeated across many contexts."
        )
        result = evaluate(text, output_dir=tmp_path)
        assert result.should_propose is True
        assert result.reason == "proposed"


class TestTrivialLength:
    def test_short_completion_signal_is_trivial(self, tmp_path: Path):
        result = evaluate("[arka:phase:13] done", output_dir=tmp_path)
        assert result.should_propose is False
        assert result.reason == "trivial-length"


class TestSkillHintFloor:
    def test_below_hint_floor_no_proposal(self, tmp_path: Path):
        text = (
            "[arka:phase:13] Finished the workflow but the actual change "
            "was a one-off bug fix that does not generalise into anything "
            "repeatable, just a localised tweak in a specific config file "
            "under conditions that are unlikely to recur in this codebase."
        )
        result = evaluate(text, output_dir=tmp_path)
        assert result.should_propose is False
        assert result.reason == "below-skill-hint-floor"

    def test_two_plus_hints_meets_floor(self, tmp_path: Path):
        text = (
            "[arka:phase:13] Built a 10-phase workflow with a checklist "
            "and a template that will be repeated for similar projects "
            "going forward in many contexts and teams."
        )
        result = evaluate(text, output_dir=tmp_path)
        assert result.should_propose is True


class TestProposalFile:
    def test_proposal_is_written(self, tmp_path: Path):
        text = (
            "[arka:phase:13] Built a 10-phase workflow with a playbook "
            "and a template for the recurring procedure that will "
            "be reused across many similar projects in the future."
        )
        result = evaluate(text, output_dir=tmp_path, today="2026-05-25")
        assert result.proposal_path is not None
        assert result.proposal_path.exists()
        assert "2026-05-25" in result.proposal_path.name


class TestResultShape:
    def test_frozen(self, tmp_path: Path):
        result = evaluate("[arka:trivial]", output_dir=tmp_path)
        assert isinstance(result, SkillProposal)
        with pytest.raises((AttributeError, Exception)):
            result.should_propose = True

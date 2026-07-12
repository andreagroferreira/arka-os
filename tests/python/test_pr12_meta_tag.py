"""PR12 v2.34.0 — Transparency [arka:meta] tag tests.

This PR is mostly hook-side (session-start.sh systemMessage instruction
+ stop.sh measurement). The Python testable surface is small: regex
that matches the tag, the spec rendering in arka/SKILL.md, and the
documented field set.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

# Regex must match the canonical tag format.
META_TAG_RE = re.compile(
    r"\[arka:meta\]"
    r"\s+kb=\d+"
    r"\s+research=\S+"
    r"\s+persona=\S+"
    r"\s+gap=\S+"
    r"\s+critic=(passed|failed|skipped)",
    re.IGNORECASE,
)


# ─── Tag regex (the lingua franca the Stop hook scans for) ─────────────


class TestMetaTagRegex:
    def test_matches_canonical_form(self):
        text = "Response body.\n[arka:meta] kb=3 research=context7 persona=Marco gap=none critic=passed"
        assert META_TAG_RE.search(text) is not None

    def test_matches_with_multiple_research_sources(self):
        text = "[arka:meta] kb=5 research=perplexity,exa,context7 persona=Tomas gap=cognitive-layer critic=passed"
        assert META_TAG_RE.search(text) is not None

    def test_matches_failed_critic(self):
        text = "[arka:meta] kb=0 research=none persona=orchestrator gap=none critic=failed"
        assert META_TAG_RE.search(text) is not None

    def test_matches_skipped_critic(self):
        text = "[arka:meta] kb=0 research=none persona=orchestrator gap=none critic=skipped"
        assert META_TAG_RE.search(text) is not None

    def test_rejects_invalid_critic_value(self):
        text = "[arka:meta] kb=0 research=none persona=orchestrator gap=none critic=maybe"
        assert META_TAG_RE.search(text) is None

    def test_rejects_missing_field(self):
        text = "[arka:meta] kb=3 research=context7 persona=Marco critic=passed"  # gap missing
        assert META_TAG_RE.search(text) is None

    def test_case_insensitive_tag(self):
        text = "[ARKA:META] kb=1 research=none persona=Eduardo gap=none critic=passed"
        assert META_TAG_RE.search(text) is not None


# ─── SessionStart hook contract ─────────────────────────────────────────


class TestSessionStartHookContract:
    @pytest.fixture
    def session_start_text(self):
        # F2-2: the systemMessage (and its contracts) moved from the shell
        # hook into the consolidated python entrypoint.
        path = Path(__file__).resolve().parents[2] / "core" / "hooks" / "session_start.py"
        return path.read_text(encoding="utf-8")

    def test_session_start_mentions_meta_tag(self, session_start_text):
        assert "[ARKA:META-TAG]" in session_start_text

    def test_session_start_documents_all_fields(self, session_start_text):
        for field in ("kb=N", "research=X", "persona=Y", "gap=Z", "critic"):
            assert field in session_start_text, f"missing field documentation: {field}"

    def test_session_start_marks_warn_only_mode(self, session_start_text):
        assert "warn" in session_start_text.lower() or "warn-only" in session_start_text.lower()

    def test_session_start_calls_out_mandatory_cases(self, session_start_text):
        # mandatory for (a) effect tool calls (b) plan/recommendation (c) QG verdicts
        assert "EFFECT tool" in session_start_text
        assert "plan" in session_start_text.lower() or "recommendation" in session_start_text.lower()
        assert "QG" in session_start_text


# ─── Stop hook measurement ──────────────────────────────────────────────


class TestStopHookMeasurement:
    @pytest.fixture
    def stop_text(self):
        path = Path(__file__).resolve().parents[2] / "config" / "hooks" / "stop.sh"
        return path.read_text(encoding="utf-8")

    def test_stop_hook_scans_for_meta_tag(self, stop_text):
        assert "meta_tag_found" in stop_text
        assert "arka:meta" in stop_text

    def test_stop_hook_in_warn_mode_only(self, stop_text):
        # PR12 ships measurement; promotion to enforce is a later PR.
        assert "warn" in stop_text.lower()

    def test_stop_hook_logs_meta_to_telemetry(self, stop_text):
        # The meta_tag_found field must land in the telemetry entry dict
        assert "meta_tag_found" in stop_text


# ─── arka/SKILL.md spec ─────────────────────────────────────────────────


class TestArkaSkillMetaSpec:
    @pytest.fixture
    def arka_skill_text(self):
        path = Path(__file__).resolve().parents[2] / "arka" / "SKILL.md"
        return path.read_text(encoding="utf-8")

    def test_skill_documents_meta_tag_section(self, arka_skill_text):
        assert "[arka:meta]" in arka_skill_text
        assert "Transparency tag contract" in arka_skill_text

    def test_skill_documents_all_five_fields(self, arka_skill_text):
        for field in ("kb=N", "research=X", "persona=Y", "gap=Z", "critic=W"):
            assert field in arka_skill_text, f"missing field: {field}"

    def test_skill_lists_mandatory_and_optional_cases(self, arka_skill_text):
        assert "Mandatory for" in arka_skill_text
        assert "Optional for" in arka_skill_text

    def test_skill_shows_example(self, arka_skill_text):
        # The doc must show at least one concrete example to be useful
        assert "kb=3 research=context7" in arka_skill_text or "kb=3" in arka_skill_text

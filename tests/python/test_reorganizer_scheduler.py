"""Tests for core.cognition.reorganizer_scheduler (PR24 v2.46.0).

Stale-aware trigger driven by the existence of today's proposal file.
Avoids platform-specific cron in favour of a session-start fire-and-
forget pattern.

Tests use synthetic proposal files in `tmp_path` and monkeypatch the
`_today_iso` helper so the date is deterministic.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from core.cognition.reorganizer_scheduler import (
    SchedulerStatus,
    is_stale,
    render_status_md,
    status_summary,
)


# ─── Fixture: deterministic "today" ─────────────────────────────────────


@pytest.fixture(autouse=True)
def fixed_today(monkeypatch):
    monkeypatch.setattr(
        "core.cognition.reorganizer_scheduler._today_iso",
        lambda: "2026-05-24",
    )


# ─── is_stale ────────────────────────────────────────────────────────────


class TestIsStale:
    def test_missing_directory_is_stale(self, tmp_path: Path):
        nowhere = tmp_path / "does-not-exist"
        assert is_stale(output_dir=nowhere) is True

    def test_empty_directory_is_stale(self, tmp_path: Path):
        tmp_path.mkdir(exist_ok=True)
        assert is_stale(output_dir=tmp_path) is True

    def test_today_proposal_present_is_fresh(self, tmp_path: Path):
        (tmp_path / "2026-05-24.md").write_text("# proposal\n")
        assert is_stale(output_dir=tmp_path) is False

    def test_only_yesterday_proposal_is_stale(self, tmp_path: Path):
        (tmp_path / "2026-05-23.md").write_text("# old\n")
        assert is_stale(output_dir=tmp_path) is True


# ─── status_summary ─────────────────────────────────────────────────────


class TestStatusSummary:
    def test_present_proposal_parses_artifact_count(self, tmp_path: Path):
        (tmp_path / "2026-05-24.md").write_text(
            "# ArkaOS Reorganization Proposal — 2026-05-24\n"
            "\n"
            "## Summary\n"
            "\n"
            "- Window: last 7 days\n"
            "- Artifacts: **145**\n"
            "- Patterns: 65\n",
            encoding="utf-8",
        )
        status = status_summary(output_dir=tmp_path)
        assert isinstance(status, SchedulerStatus)
        assert status.today_proposal_exists is True
        assert status.artifact_count == 145
        assert status.last_generated_at is not None

    def test_absent_proposal_returns_none_fields(self, tmp_path: Path):
        status = status_summary(output_dir=tmp_path)
        assert status.today_proposal_exists is False
        assert status.last_generated_at is None
        assert status.artifact_count is None

    def test_malformed_proposal_returns_unknown_count(self, tmp_path: Path):
        (tmp_path / "2026-05-24.md").write_text(
            "garbage with no Artifacts line\n",
            encoding="utf-8",
        )
        status = status_summary(output_dir=tmp_path)
        assert status.today_proposal_exists is True
        # Could not parse count — None is acceptable
        assert status.artifact_count is None


# ─── render_status_md ───────────────────────────────────────────────────


class TestRenderStatusMd:
    def test_present_status_renders_with_path_and_count(self, tmp_path: Path):
        (tmp_path / "2026-05-24.md").write_text(
            "Artifacts: **42**\n", encoding="utf-8",
        )
        status = status_summary(output_dir=tmp_path)
        rendered = render_status_md(status)
        assert "42" in rendered
        assert "2026-05-24.md" in rendered
        assert "Reorganization" in rendered

    def test_absent_status_renders_no_proposal_message(self, tmp_path: Path):
        status = status_summary(output_dir=tmp_path)
        rendered = render_status_md(status)
        assert "no proposal" in rendered.lower() or "not yet" in rendered.lower()

"""Tests for core.cognition.reorganizer (PR20 v2.42.0).

Propose-only Dreaming → Agent reorganizer. Scans KB pattern/anti-pattern/
lesson files, sanitizes client identifiers, renders a markdown proposal
report. Never writes to agent YAMLs.

Test fixtures use *synthetic* client names (acmecorp / globexsa / initechinc)
injected via the ``synthetic_clients`` fixture. Real client identifiers
never appear in test inputs — `feedback_confidentiality.md` and
`feedback_npm_publish_safety.md` (v2.18.0 leaked real names through
fixture-style strings; do not repeat).
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from core.cognition.reorganizer import (
    KbArtifact,
    ProposalReport,
    build_proposal,
)


# ─── Synthetic client fixture (replaces real names in production list) ──


@pytest.fixture(autouse=True)
def synthetic_clients(monkeypatch):
    """Swap the production `_CLIENT_PATTERNS` for synthetic names.

    Autouse so every test in this module exercises the redaction path
    against safe inputs. Production list ships untouched.
    """
    synthetic = ("acmecorp", "globexsa", "initechinc")
    monkeypatch.setattr(
        "core.cognition.reorganizer._CLIENT_PATTERNS",
        synthetic,
    )
    monkeypatch.setattr(
        "core.cognition.reorganizer._REDACT_RE",
        re.compile(
            r"(?<![a-z0-9])(" + "|".join(synthetic) + r")(?![a-z0-9])",
            re.IGNORECASE,
        ),
    )
    return synthetic


# ─── Fixtures ───────────────────────────────────────────────────────────


def _today_iso() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _days_ago_iso(days: int) -> str:
    return (datetime.now(timezone.utc).date() - timedelta(days=days)).isoformat()


def _write_pattern(
    kb_dir: Path,
    name: str,
    *,
    category: str = "pattern",
    confidence: str = "validated",
    times_used: int = 1,
    tags: list[str] | None = None,
    first_seen: str | None = None,
    last_seen: str | None = None,
    source_project: str | None = None,
    body: str = "What it is: a useful pattern.",
) -> Path:
    kb_dir.mkdir(parents=True, exist_ok=True)
    path = kb_dir / f"{category}-{name}.md"
    tags_block = ""
    if tags:
        tags_block = "tags: [" + ", ".join(tags) + "]\n"
    src_block = f"source_project: {source_project}\n" if source_project else ""
    fm = (
        "---\n"
        f"title: {name}\n"
        f"category: {category}\n"
        f"confidence: {confidence}\n"
        f"times_used: {times_used}\n"
        f"first_seen: {first_seen or _today_iso()}\n"
        f"last_seen: {last_seen or _today_iso()}\n"
        f"{tags_block}"
        f"{src_block}"
        "---\n\n"
        f"# {name}\n\n"
        f"{body}\n"
    )
    path.write_text(fm, encoding="utf-8")
    return path


# ─── Discovery + categorization ─────────────────────────────────────────


class TestDiscovery:
    def test_empty_kb_dir_returns_empty_report(self, tmp_path: Path):
        result = build_proposal(tmp_path, since_days=7, dry_run=True)
        assert isinstance(result, ProposalReport)
        assert result.artifact_count == 0
        assert result.by_category == {}

    def test_nonexistent_kb_dir_returns_empty(self, tmp_path: Path):
        nowhere = tmp_path / "does-not-exist"
        result = build_proposal(nowhere, since_days=7, dry_run=True)
        assert result.artifact_count == 0

    def test_three_patterns_counted_correctly(self, tmp_path: Path):
        _write_pattern(tmp_path, "alpha", category="pattern")
        _write_pattern(tmp_path, "beta", category="pattern")
        _write_pattern(tmp_path, "gamma", category="pattern")
        result = build_proposal(tmp_path, since_days=7, dry_run=True)
        assert result.artifact_count == 3
        assert result.by_category == {"pattern": 3}

    def test_mixed_categories_grouped(self, tmp_path: Path):
        _write_pattern(tmp_path, "alpha", category="pattern")
        _write_pattern(tmp_path, "beta", category="anti-pattern")
        _write_pattern(tmp_path, "gamma", category="lesson")
        _write_pattern(tmp_path, "delta", category="pattern")
        result = build_proposal(tmp_path, since_days=7, dry_run=True)
        assert result.by_category["pattern"] == 2
        assert result.by_category["anti-pattern"] == 1
        assert result.by_category["lesson"] == 1


# ─── Client name redaction (NON-NEGOTIABLE) ─────────────────────────────


class TestRedaction:
    def test_source_project_field_dropped_from_output(self, tmp_path: Path):
        _write_pattern(
            tmp_path, "alpha",
            source_project="acmecorp-supplier-sync",
        )
        result = build_proposal(tmp_path, since_days=7, dry_run=True)
        # source_project must not appear anywhere in the report markdown
        assert "acmecorp" not in result.report_markdown.lower()
        assert "source_project" not in result.report_markdown.lower()

    def test_client_name_in_body_redacted(self, tmp_path: Path):
        _write_pattern(
            tmp_path, "alpha",
            body="Discovered while integrating Acmecorp SAP exports.",
        )
        result = build_proposal(tmp_path, since_days=7, dry_run=True)
        assert "acmecorp" not in result.report_markdown.lower()
        assert "<redacted-client>" in result.report_markdown.lower()

    def test_client_name_in_title_redacted(self, tmp_path: Path):
        _write_pattern(
            tmp_path, "globexsa-billing-quirk",
            body="content",
        )
        result = build_proposal(tmp_path, since_days=7, dry_run=True)
        # Title in markdown should redact the client prefix from the title.
        assert "globexsa-billing-quirk" not in result.report_markdown.lower()

    def test_multiple_client_names_all_redacted(self, tmp_path: Path):
        _write_pattern(
            tmp_path, "alpha",
            body="Saw this in Acmecorp AND globexsa AND INITECHINC.",
        )
        result = build_proposal(tmp_path, since_days=7, dry_run=True)
        lower = result.report_markdown.lower()
        assert "acmecorp" not in lower
        assert "globexsa" not in lower
        # Standalone client token must be word-boundary redacted.
        assert " initechinc " not in f" {lower} "


# ─── Date filtering ─────────────────────────────────────────────────────


class TestDateFilter:
    def test_old_pattern_excluded_when_outside_window(self, tmp_path: Path):
        _write_pattern(
            tmp_path, "old",
            first_seen=_days_ago_iso(30),
            last_seen=_days_ago_iso(30),
        )
        _write_pattern(
            tmp_path, "fresh",
            first_seen=_today_iso(),
            last_seen=_today_iso(),
        )
        result = build_proposal(tmp_path, since_days=7, dry_run=True)
        assert result.artifact_count == 1

    def test_last_seen_within_window_includes(self, tmp_path: Path):
        # first_seen old but last_seen recent → included
        _write_pattern(
            tmp_path, "revisited",
            first_seen=_days_ago_iso(60),
            last_seen=_days_ago_iso(2),
        )
        result = build_proposal(tmp_path, since_days=7, dry_run=True)
        assert result.artifact_count == 1


# ─── Robustness ─────────────────────────────────────────────────────────


class TestRobustness:
    def test_malformed_frontmatter_skipped_no_crash(self, tmp_path: Path):
        bad = tmp_path / "pattern-broken.md"
        bad.write_text("---\nnot: valid: yaml: chaos\n: : :\n---\n\n# broken\n", encoding="utf-8")
        # Plus one valid file
        _write_pattern(tmp_path, "alpha")
        result = build_proposal(tmp_path, since_days=7, dry_run=True)
        # At least the valid one should be counted; malformed skipped
        assert result.artifact_count >= 1

    def test_no_frontmatter_skipped(self, tmp_path: Path):
        bare = tmp_path / "pattern-bare.md"
        bare.write_text("# just markdown, no frontmatter\n", encoding="utf-8")
        result = build_proposal(tmp_path, since_days=7, dry_run=True)
        assert result.artifact_count == 0

    def test_body_excerpt_truncated_at_500_chars(self, tmp_path: Path):
        long_body = "x" * 2000
        _write_pattern(tmp_path, "long", body=long_body)
        result = build_proposal(tmp_path, since_days=7, dry_run=True)
        # The proposal markdown should not contain the full 2000-char body
        assert "x" * 2000 not in result.report_markdown


# ─── Dry-run vs file write ──────────────────────────────────────────────


class TestOutputMode:
    def test_dry_run_does_not_create_file(self, tmp_path: Path):
        _write_pattern(tmp_path, "alpha")
        out = tmp_path / "proposals"
        result = build_proposal(
            tmp_path, since_days=7, output_dir=out, dry_run=True,
        )
        assert result.report_path is None
        assert not out.exists() or list(out.iterdir()) == []

    def test_write_mode_creates_dated_file(self, tmp_path: Path):
        _write_pattern(tmp_path, "alpha")
        out = tmp_path / "proposals"
        result = build_proposal(
            tmp_path, since_days=7, output_dir=out, dry_run=False,
        )
        assert result.report_path is not None
        assert result.report_path.exists()
        assert result.report_path.suffix == ".md"
        # File name should encode the date
        today = _today_iso()
        assert today in result.report_path.name


# ─── Report shape ───────────────────────────────────────────────────────


class TestReportShape:
    def test_report_markdown_has_required_sections(self, tmp_path: Path):
        _write_pattern(tmp_path, "alpha", category="pattern")
        _write_pattern(tmp_path, "beta", category="anti-pattern")
        result = build_proposal(tmp_path, since_days=7, dry_run=True)
        md = result.report_markdown
        # Must explicitly state propose-only contract
        assert "propose-only" in md.lower() or "no agent" in md.lower()
        # Must surface counts
        assert "alpha" in md.lower() or "1" in md
        # Must contain header
        assert md.startswith("# ")

    def test_report_includes_generated_at_iso_timestamp(self, tmp_path: Path):
        _write_pattern(tmp_path, "alpha")
        result = build_proposal(tmp_path, since_days=7, dry_run=True)
        # ISO timestamp like 2026-05-24
        assert _today_iso() in result.generated_at


# ─── md_escape: stored-XSS / markdown-injection neutralisation ──────────


class TestMdEscape:
    """md_escape neutralises untrusted titles for HTML-rendering md viewers.

    Titles flow from web/YouTube/PDF metadata into .md files opened in
    Obsidian, which renders raw HTML. md_escape must HTML-escape <> (CWE-79)
    while preserving the existing pipe/backtick/newline neutralisation.
    """

    def test_script_tag_is_html_neutralised(self):
        from core.cognition.reorganizer import md_escape

        out = md_escape("Course <script>alert(1)</script> | review")
        assert "<script>" not in out
        assert "</script>" not in out
        assert "&lt;script&gt;alert(1)&lt;/script&gt;" in out

    def test_img_onerror_payload_is_neutralised(self):
        from core.cognition.reorganizer import md_escape

        out = md_escape('<img src=x onerror="alert(1)">')
        assert "<img" not in out
        assert "&lt;img src=x onerror=" in out
        assert out.endswith("&gt;")

    def test_legitimate_angle_brackets_render_as_literal_text(self):
        from core.cognition.reorganizer import md_escape

        # "C++ <vector>" must survive as visible literal text, not a swallowed tag.
        assert md_escape("C++ <vector>") == "C++ &lt;vector&gt;"

    def test_pipe_backtick_newline_neutralisation_unchanged(self):
        from core.cognition.reorganizer import md_escape

        out = md_escape("a | b `c`\nd\re")
        assert "\\|" in out          # pipe escaped (table-safe)
        assert "`" not in out         # backticks stripped
        assert "\n" not in out and "\r" not in out  # newlines flattened
        assert "c" in out and "d" in out and "e" in out

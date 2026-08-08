"""Tests for core.sync.marker_audit — the feature-marker self-check.

Regression origin (issue #492): eight STAMPED `arka:feature` markers — the
bare marker with `version=… hash=…` appended, borrowed from the
`arkaos:managed` block convention — lived across five installed skills for
two full releases (v5.10 → v5.14) without a single check firing. Every
consumer matched the marker literally, so a stamped marker read as "no
marker here" instead of "this marker is broken": a non-match was silently
treated as evidence of absence. They were normalised by hand on 2026-08-07
(~/.arkaos/audit/phase4-sync-2026-08-07.json).

Two properties are locked here:
- classification is total — bare is the contract, everything else is a
  NAMED violation carrying path, line and the offending marker text;
- the scan reaches the INSTALLED tree (~/.claude/skills), where the markers
  actually live, not only the repo.

Every test drives a tmp_path tree. The one test that touches the real
installed tree is opt-in via skipif and read-only.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from core.sync.marker_audit import (
    DEFAULT_SKILLS_ROOT,
    MarkerViolation,
    audit_installed_skills,
    scan_text,
    scan_tree,
)

# ---------------------------------------------------------------------------
# Fixtures — the exact shapes seen in the wild
# ---------------------------------------------------------------------------

_BARE = (
    "# Ecosystem\n\n"
    "<!-- arka:feature:quality-gate:start -->\n"
    "## Quality Gate\n\n"
    "Body.\n"
    "<!-- arka:feature:quality-gate:end -->\n"
)

# The v5.10.0 shape recovered from the five drifted skills.
_STAMPED = (
    "# Ecosystem\n\n"
    "<!-- arka:feature:quality-gate:start version=5.10.0 hash=deadbeef1234 -->\n"
    "## Quality Gate\n\n"
    "Body.\n"
    "<!-- arka:feature:quality-gate:end version=5.10.0 hash=deadbeef1234 -->\n"
)


def _skill(root: Path, slug: str, text: str) -> Path:
    """Write an installed-skill SKILL.md under root and return its path."""
    target = root / slug / "SKILL.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    return target


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------


class TestClassification:
    def test_bare_markers_are_the_contract(self) -> None:
        assert scan_text(_BARE, Path("SKILL.md")) == []

    def test_stamped_start_marker_is_a_named_violation(self) -> None:
        violations = scan_text(_STAMPED, Path("SKILL.md"))
        starts = [v for v in violations if ":start" in v.marker]
        assert len(starts) == 1, "a stamped start marker must never be skipped"
        assert starts[0].kind == "stamped"

    def test_stamped_end_marker_is_a_named_violation(self) -> None:
        """The end marker is the removal anchor; a stamp there orphans the
        block just as badly as a stamp on the start marker."""
        ends = [v for v in scan_text(_STAMPED, Path("SKILL.md")) if ":end" in v.marker]
        assert len(ends) == 1
        assert ends[0].kind == "stamped"

    def test_violation_names_path_line_and_the_stamp_found(self) -> None:
        violation = scan_text(_STAMPED, Path("arka-edp/SKILL.md"))[0]
        assert violation.line == 3, "line must point at the offending marker"
        assert violation.path == Path("arka-edp/SKILL.md")
        assert "version=5.10.0" in violation.marker
        assert "hash=deadbeef1234" in violation.marker
        rendered = violation.describe()
        assert "arka-edp/SKILL.md" in rendered
        assert ":3" in rendered
        assert "version=5.10.0" in rendered

    @pytest.mark.parametrize(
        "body",
        [
            "<!-- arka:feature:quality-gate:begin -->",
            "<!-- arka:feature:quality-gate -->",
            "<!--arka:feature:quality-gate:start-->",
            "<!--  arka:feature:quality-gate:start  -->",
            "<!-- arka:feature:quality gate:start -->",
        ],
        ids=["wrong-side", "no-side", "no-spaces", "double-spaces", "space-in-name"],
    )
    def test_malformed_markers_are_named_never_skipped(self, body: str) -> None:
        """Anything a literal consumer would miss is a violation. Whitespace
        counts: `<!--arka:feature:x:start-->` is invisible to the removal
        pattern exactly like a stamp is."""
        violations = scan_text(f"# S\n\n{body}\n", Path("SKILL.md"))
        assert len(violations) == 1
        assert violations[0].kind == "malformed"

    def test_marker_swallowed_by_an_open_comment_is_named(self) -> None:
        """Found live by this scanner on its first run over the real tree
        (arka-scaffold/SKILL.md:20): an unterminated `<!--` sat above the
        injection point, so the first marker's `-->` closed THAT comment
        instead. The section is eaten and the old comment's tail renders as
        visible garbage — and no check saw any of it."""
        text = (
            "## Commands\n\n"
            "<!-- Column convention: command | DESCRIPTION | repo\n\n"
            "<!-- arka:feature:forge-integration:start -->\n"
            "## Forge Integration\n"
            "<!-- arka:feature:forge-integration:end -->\n"
        )

        violations = scan_text(text, Path("arka-scaffold/SKILL.md"))

        assert [v.line for v in violations] == [3]
        assert violations[0].kind == "malformed"
        assert "unterminated HTML comment" in violations[0].reason

    def test_unrelated_comments_are_ignored(self) -> None:
        text = "<!-- arkaos:managed:start version=5.14.0 hash=abcdef123456 -->\n"
        assert scan_text(text, Path("CLAUDE.md")) == []

    def test_markers_inside_code_spans_are_documentation(self) -> None:
        """`departments/ops/skills/update/references/sync-engine.md` documents
        the contract with a `<name>` placeholder inside backticks. Prose ABOUT
        a marker is not a marker — otherwise the lock cries wolf on its own
        documentation and gets muted."""
        text = (
            "- `content` — wrapped in `<!-- arka:feature:<name>:start -->` / "
            "`<!-- arka:feature:<name>:end -->` markers.\n"
        )
        assert scan_text(text, Path("sync-engine.md")) == []

    def test_markers_inside_fenced_blocks_are_documentation(self) -> None:
        text = (
            "Example of the broken shape:\n\n"
            "```markdown\n"
            "<!-- arka:feature:quality-gate:start version=5.10.0 hash=deadbeef1234 -->\n"
            "```\n"
        )
        assert scan_text(text, Path("guide.md")) == []

    def test_line_numbers_survive_code_stripping(self) -> None:
        """Code spans are blanked, not deleted: a violation after a fenced
        block must still report its true line."""
        text = "```\ncode\n```\n\n<!--arka:feature:forge:start-->\n"
        assert scan_text(text, Path("SKILL.md"))[0].line == 5


# ---------------------------------------------------------------------------
# Tree scanning
# ---------------------------------------------------------------------------


class TestScanTree:
    def test_finds_stamped_marker_in_an_installed_skill_tree(
        self, tmp_path: Path
    ) -> None:
        skills = tmp_path / "skills"
        _skill(skills, "arka-edp", _STAMPED)
        _skill(skills, "arka-rockport", _BARE)

        violations = scan_tree(skills)

        assert [v.path.parent.name for v in violations] == ["arka-edp", "arka-edp"]
        assert all(v.kind == "stamped" for v in violations)

    def test_clean_tree_yields_no_violations(self, tmp_path: Path) -> None:
        skills = tmp_path / "skills"
        for slug in ("arka-rockport", "arka-fovory", "arka-adamastor"):
            _skill(skills, slug, _BARE)
        assert scan_tree(skills) == []

    def test_missing_tree_is_not_a_violation(self, tmp_path: Path) -> None:
        """A fresh install or a CI box has no installed skills. Absent is not
        broken — but it must not raise either."""
        assert scan_tree(tmp_path / "never-installed") == []

    def test_results_are_ordered_by_path_then_line(self, tmp_path: Path) -> None:
        skills = tmp_path / "skills"
        _skill(skills, "arka-zeta", _STAMPED)
        _skill(skills, "arka-alpha", _STAMPED)
        paths = [str(v.path) for v in scan_tree(skills)]
        assert paths == sorted(paths)
        alpha = [v for v in scan_tree(skills) if v.path.parent.name == "arka-alpha"]
        assert [v.line for v in alpha] == [3, 7]

    def test_non_markdown_files_are_not_scanned(self, tmp_path: Path) -> None:
        skills = tmp_path / "skills"
        skills.mkdir()
        (skills / "notes.txt").write_text(_STAMPED, encoding="utf-8")
        assert scan_tree(skills) == []

    def test_undecodable_file_is_reported_not_swallowed(self, tmp_path: Path) -> None:
        """The whole defect was a silent skip. A file the scanner cannot read
        is reported as such rather than counted as clean."""
        skills = tmp_path / "skills"
        skills.mkdir()
        (skills / "broken.md").write_bytes(b"\xff\xfe not utf-8 \xff")

        violations = scan_tree(skills)

        assert len(violations) == 1
        assert violations[0].kind == "unreadable"


# ---------------------------------------------------------------------------
# Installed-tree self-check
# ---------------------------------------------------------------------------


class TestAuditInstalledSkills:
    def test_defaults_to_the_installed_skills_root(self) -> None:
        assert Path.home() / ".claude" / "skills" == DEFAULT_SKILLS_ROOT

    def test_explicit_root_overrides_the_default(self, tmp_path: Path) -> None:
        skills = tmp_path / "skills"
        _skill(skills, "arka-edp", _STAMPED)
        assert len(audit_installed_skills(skills)) == 2

    def test_absent_installed_tree_returns_empty(self, tmp_path: Path) -> None:
        assert audit_installed_skills(tmp_path / "nothing-here") == []

    @pytest.mark.skipif(
        os.environ.get("ARKA_AUDIT_INSTALLED_SKILLS") != "1"
        or not DEFAULT_SKILLS_ROOT.is_dir(),
        reason="opt-in diagnostic: set ARKA_AUDIT_INSTALLED_SKILLS=1",
    )
    def test_real_installed_tree_is_canonical(self) -> None:
        """Opt-in diagnostic, read-only, never part of a normal suite run.

        The installed tree is operator state, not a repo fact — gating CI on
        it would make the suite red for a defect no commit introduced. The
        engine reports the same scan on every `/arka update`
        (`run_sync` -> `SyncReport.errors`); that is the enforcing channel.
        This test is the manual probe of the same function.
        """
        violations = audit_installed_skills()
        assert violations == [], "\n".join(v.describe() for v in violations)


# ---------------------------------------------------------------------------
# Report wiring — the self-check has to reach a human
# ---------------------------------------------------------------------------


class TestReportWiring:
    def _violation(self) -> MarkerViolation:
        return scan_text(_STAMPED, Path("arka-edp/SKILL.md"))[0]

    def test_violations_land_in_report_errors(self) -> None:
        from core.sync.reporter import build_report

        report = build_report(
            "5.13.0", "5.14.0", [], [], [], [], marker_violations=[self._violation()]
        )

        assert len(report.errors) == 1, "a stamped marker must not report Errors: 0"
        assert "arka-edp/SKILL.md" in report.errors[0]
        assert report.marker_violations == report.errors

    def test_report_output_names_the_markers(self) -> None:
        from core.sync.reporter import build_report, format_report

        output = format_report(
            build_report(
                "5.13.0", "5.14.0", [], [], [], [], marker_violations=[self._violation()]
            )
        )

        assert "Feature markers" in output
        assert "version=5.10.0" in output
        assert "Errors: 1" in output

    def test_clean_run_says_nothing_about_markers(self) -> None:
        from core.sync.reporter import build_report, format_report

        output = format_report(build_report("5.13.0", "5.14.0", [], [], [], []))

        assert "Feature markers" not in output
        assert "Errors: 0" in output

    def test_run_sync_audits_the_installed_skills_tree(self, tmp_path: Path) -> None:
        """The self-check runs where the sync already reports. Project
        discovery is stubbed: unstubbed, run_sync resolves the operator's REAL
        ~/.arkaos/projects and writes into those directories."""
        from unittest.mock import patch

        from core.sync.engine import run_sync

        skills = tmp_path / "skills"
        _skill(skills, "arka-edp", _STAMPED)
        arkaos_home = tmp_path / "arkaos-home"
        arkaos_home.mkdir()

        with patch("core.sync.engine._discover_projects", return_value=[]):
            report = run_sync(
                arkaos_home=arkaos_home,
                skills_dir=skills,
                home_path=str(tmp_path),
            )

        assert len(report.marker_violations) == 2
        assert all("arka-edp" in v for v in report.marker_violations)

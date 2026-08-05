"""Tests for core.sync.feature_merger — named feature-block merge algorithm."""

from __future__ import annotations

from core.sync.content_merger import compute_managed_hash
from core.sync.feature_merger import (
    canonical_body,
    merge_feature,
    merge_skill,
)
from core.sync.schema import FeatureSpec

CANON = "## Forge Integration\n\nComplexity >= 5 routes to The Forge.\n\n- Phase 0.5"
VERSION = "5.10.0"


def _feature(
    *,
    name: str = "forge-integration",
    title: str = "Forge Integration",
    body: str = CANON,
    deprecated_in: str | None = None,
) -> FeatureSpec:
    return FeatureSpec(
        name=name,
        added_in="5.0.0",
        mandatory=True,
        section_title=title,
        detection_pattern=rf"arka:feature:{name}|## {title}",
        content=(
            f"<!-- arka:feature:{name}:start -->\n{body}\n"
            f"<!-- arka:feature:{name}:end -->\n"
        ),
        deprecated_in=deprecated_in,
    )


def _block(body: str = CANON, *, version: str = VERSION, name: str = "forge-integration") -> str:
    h = compute_managed_hash(body)
    return (
        f"<!-- arka:feature:{name}:start version={version} hash={h} -->\n"
        f"{body}\n"
        f"<!-- arka:feature:{name}:end -->"
    )


# ---------------------------------------------------------------------------
# canonical_body
# ---------------------------------------------------------------------------


def test_canonical_body_strips_legacy_marker_lines() -> None:
    assert canonical_body(_feature()) == CANON


# ---------------------------------------------------------------------------
# Managed blocks — the aligned path
# ---------------------------------------------------------------------------


def test_stale_content_is_rewritten_from_canonical() -> None:
    """The whole point of PR-A: an outdated block must be brought forward."""
    old = "## Forge Integration\n\nOLD DOCTRINE"
    text = f"# Skill\n\n{_block(old, version='5.0.0')}\n"

    result = merge_feature(text, _feature(), VERSION)

    assert result.status == "updated"
    assert "OLD DOCTRINE" not in result.new_text
    assert "Complexity >= 5 routes to The Forge." in result.new_text
    assert "# Skill" in result.new_text


def test_current_content_with_stale_version_is_restamped() -> None:
    text = f"# Skill\n\n{_block(version='5.0.0')}\n"

    result = merge_feature(text, _feature(), VERSION)

    assert result.status == "restamped"
    assert f"version={VERSION}" in result.new_text


def test_fully_current_block_is_unchanged() -> None:
    text = f"# Skill\n\n{_block()}\n"

    result = merge_feature(text, _feature(), VERSION)

    assert result.status == "unchanged"
    assert result.new_text == text


def test_merge_is_idempotent() -> None:
    text = "# Skill\n\n## Commands\n\nsome table\n"

    once = merge_feature(text, _feature(), VERSION).new_text
    twice = merge_feature(once, _feature(), VERSION)

    assert twice.status == "unchanged"
    assert twice.new_text == once


# ---------------------------------------------------------------------------
# Legacy sections — adoption vs. refusal
# ---------------------------------------------------------------------------


def test_identical_legacy_section_is_adopted_into_a_block() -> None:
    text = f"# Skill\n\n{CANON}\n\n## Project notes\n\nMine.\n"

    result = merge_feature(text, _feature(), VERSION)

    assert result.status == "adopted"
    assert "arka:feature:forge-integration:start" in result.new_text
    assert f"version={VERSION}" in result.new_text
    assert "Mine." in result.new_text


def test_adoption_preserves_the_projects_own_spacing() -> None:
    """Adoption must not reflow blank lines the project wrote.

    Rendering is unaffected either way — an HTML comment closes its block on
    the `-->` line, so a following heading still parses — but silently eating
    a blank line is still editing project-authored text, which is exactly
    what the managed-block contract forbids.
    """
    text = f"# Skill\n\n{CANON}\n\n## Project notes\n\nMine.\n"

    new_text = merge_feature(text, _feature(), VERSION).new_text

    lines = new_text.splitlines()
    heading = lines.index("## Project notes")
    assert lines[heading - 1] == "", "adopted block must not touch the next heading"


def test_adoption_does_not_accumulate_blank_lines_across_runs() -> None:
    text = f"# Skill\n\n{CANON}\n\n## Project notes\n\nMine.\n"

    once = merge_feature(text, _feature(), VERSION).new_text
    twice = merge_feature(once, _feature(), VERSION).new_text

    assert once == twice


def test_diverged_legacy_section_is_never_overwritten() -> None:
    """Aligning must not delete operator customisation."""
    custom = (
        "## Forge Integration\n\nComplexity >= 5 routes to The Forge.\n\n"
        "- Phase 0.5\n- Project-specific rule Bruno added"
    )
    text = f"# Skill\n\n{custom}\n\n## Project notes\n\nMine.\n"

    result = merge_feature(text, _feature(), VERSION)

    assert result.status == "pending_adoption"
    assert result.new_text == text
    assert "Project-specific rule Bruno added" in result.new_text
    assert "arka:feature" not in result.new_text
    assert "Project-specific rule Bruno added" in result.legacy_body


def test_legacy_heading_with_project_suffix_is_recognised() -> None:
    """A project may harden the heading: `## Quality Gate (NON-NEGOTIABLE)`."""
    feature = _feature(
        name="quality-gate", title="Quality Gate", body="## Quality Gate\n\nMarta vetoes."
    )
    text = "# Skill\n\n## Quality Gate (NON-NEGOTIABLE)\n\nBruno mandatory on every tier.\n"

    result = merge_feature(text, feature, VERSION)

    assert result.status == "pending_adoption"
    assert "Bruno mandatory on every tier." in result.legacy_body


def test_missing_feature_is_injected() -> None:
    text = "# Skill\n\n## Commands\n\ntable\n"

    result = merge_feature(text, _feature(), VERSION)

    assert result.status == "injected"
    assert "arka:feature:forge-integration:start" in result.new_text
    assert "## Commands" in result.new_text


def test_injected_block_lands_after_the_last_existing_block() -> None:
    existing = _block(body="## Quality Gate\n\nMarta.", name="quality-gate")
    text = f"# Skill\n\n{existing}\n\n## Trailing project notes\n"

    result = merge_feature(text, _feature(), VERSION)

    assert result.status == "injected"
    new = result.new_text
    assert new.index("quality-gate:end") < new.index("forge-integration:start")
    assert "## Trailing project notes" in new


# ---------------------------------------------------------------------------
# Malformed markers — the data-loss contract
#
# _find_block used to pair a start marker with ANY later end marker. An orphan
# start therefore paired with the NEXT block's end and the splice deleted every
# byte in between — project-authored sections included — reported as a benign
# "updated". _append_block manufactured that pairing on run 1, so two ordinary
# syncs were enough. Target is ~/.claude/skills/, which is not a git repo.
# ---------------------------------------------------------------------------


def test_orphan_start_marker_never_splices() -> None:
    text = (
        "# Skill\n\n<!-- arka:feature:forge-integration:start -->\n\n"
        "## Deploy runbook\n\nIRREPLACEABLE\n"
    )

    result = merge_feature(text, _feature(), VERSION)

    assert result.status == "malformed_markers"
    assert result.new_text == text
    assert "IRREPLACEABLE" in result.new_text
    assert "unbalanced" in (result.error or "")


def test_orphan_start_survives_two_consecutive_syncs() -> None:
    """The original escalation: run 1 appended a block, run 2 detonated it."""
    text = (
        "# Skill\n\n<!-- arka:feature:forge-integration:start -->\n\n"
        "## Deploy runbook\n\nIRREPLACEABLE\n"
    )

    once = merge_feature(text, _feature(), VERSION).new_text
    twice = merge_feature(once, _feature(), VERSION).new_text

    assert twice == text
    assert "IRREPLACEABLE" in twice


def test_orphan_end_marker_never_splices() -> None:
    text = "# Skill\n\n## Mine\n\nKEEP\n<!-- arka:feature:forge-integration:end -->\n"

    result = merge_feature(text, _feature(), VERSION)

    assert result.status == "malformed_markers"
    assert result.new_text == text


def test_duplicate_blocks_never_splice() -> None:
    text = f"# Skill\n\n{_block()}\n\n## Mine\n\nKEEP\n\n{_block()}\n"

    result = merge_feature(text, _feature(), VERSION)

    assert result.status == "malformed_markers"
    assert result.new_text == text
    assert "KEEP" in result.new_text


def test_inverted_markers_never_splice() -> None:
    text = (
        "# Skill\n\n<!-- arka:feature:forge-integration:end -->\n\nKEEP\n\n"
        "<!-- arka:feature:forge-integration:start -->\n"
    )

    result = merge_feature(text, _feature(), VERSION)

    assert result.status == "malformed_markers"
    assert result.new_text == text
    assert "end marker appears before start marker" in (result.error or "")


def test_deprecation_also_refuses_malformed_markers() -> None:
    """_remove_feature carried the identical splice."""
    text = (
        "# Skill\n\n<!-- arka:feature:forge-integration:start -->\n\n"
        "## Mine\n\nIRREPLACEABLE\n"
    )

    result = merge_feature(text, _feature(deprecated_in="5.10.0"), VERSION)

    assert result.status == "malformed_markers"
    assert "IRREPLACEABLE" in result.new_text


def test_malformed_markers_never_count_as_a_write() -> None:
    text = "<!-- arka:feature:forge-integration:start -->\nMINE\n"

    report = merge_skill(text, "arka-acme", [_feature()], VERSION)

    assert not report.changed
    assert report.new_text == text


# ---------------------------------------------------------------------------
# Deprecation
# ---------------------------------------------------------------------------


def test_deprecated_feature_with_block_is_removed() -> None:
    text = f"# Skill\n\n{_block()}\n\n## Mine\n"

    result = merge_feature(text, _feature(deprecated_in="5.10.0"), VERSION)

    assert result.status == "removed"
    assert "Forge Integration" not in result.new_text
    assert "## Mine" in result.new_text


def test_deprecated_feature_with_diverged_legacy_is_not_deleted() -> None:
    custom = f"{CANON}\n- extra project rule"
    text = f"# Skill\n\n{custom}\n"

    result = merge_feature(text, _feature(deprecated_in="5.10.0"), VERSION)

    assert result.status == "pending_removal"
    assert result.new_text == text
    assert "extra project rule" in result.new_text


# ---------------------------------------------------------------------------
# Whole-skill merge
# ---------------------------------------------------------------------------


def test_merge_skill_applies_every_feature_and_preserves_project_content() -> None:
    features = [
        _feature(),
        _feature(name="quality-gate", title="Quality Gate", body="## Quality Gate\n\nMarta."),
    ]
    text = "# arka-acme\n\n## Commands\n\n| cmd | desc |\n"

    report = merge_skill(text, "arka-acme", features, VERSION)

    assert report.by_status("injected") == ["forge-integration", "quality-gate"]
    assert report.changed
    assert "| cmd | desc |" in report.new_text
    again = merge_skill(report.new_text, "arka-acme", features, VERSION)
    assert not again.changed

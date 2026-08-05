"""Tests for core.sync.content_merger — managed-region merge algorithm."""

from __future__ import annotations

from pathlib import Path

from core.sync.content_merger import (
    compute_managed_hash,
    merge_managed_content,
)


def test_hash_is_stable_for_same_content() -> None:
    h1 = compute_managed_hash("hello world")
    h2 = compute_managed_hash("hello world")
    assert h1 == h2
    assert len(h1) == 12


def test_hash_differs_for_different_content() -> None:
    assert compute_managed_hash("a") != compute_managed_hash("b")


def test_merge_into_file_without_markers_prepends_block(tmp_path: Path) -> None:
    target = tmp_path / "CLAUDE.md"
    target.write_text("# Project notes\n\nCustom content here.\n", encoding="utf-8")

    result = merge_managed_content(
        target_text="# Project notes\n\nCustom content here.\n",
        managed_content="CORE",
        version="2.17.0",
    )

    assert result.status == "updated"
    assert "<!-- arkaos:managed:start" in result.new_text
    assert "CORE" in result.new_text
    assert "<!-- arkaos:managed:end -->" in result.new_text
    assert "Custom content here." in result.new_text
    assert result.new_text.index("CORE") < result.new_text.index("Custom content")


def test_merge_replaces_existing_managed_block() -> None:
    target = (
        "<!-- arkaos:managed:start version=2.16.0 hash=abc123abc123 -->\n"
        "OLD CORE\n"
        "<!-- arkaos:managed:end -->\n\n"
        "## Project notes\n\nCustom.\n"
    )

    result = merge_managed_content(
        target_text=target,
        managed_content="NEW CORE",
        version="2.17.0",
    )

    assert result.status == "updated"
    assert "OLD CORE" not in result.new_text
    assert "NEW CORE" in result.new_text
    assert "Custom." in result.new_text
    assert "version=2.17.0" in result.new_text


def test_merge_unchanged_when_hash_matches() -> None:
    managed = "STABLE"
    hash12 = compute_managed_hash(managed)
    target = (
        f"<!-- arkaos:managed:start version=2.17.0 hash={hash12} -->\n"
        f"{managed}\n"
        "<!-- arkaos:managed:end -->\n"
    )

    result = merge_managed_content(
        target_text=target,
        managed_content=managed,
        version="2.17.0",
    )

    assert result.status == "unchanged"
    assert result.new_text == target


def test_merge_restamps_when_content_current_but_version_stale() -> None:
    """A file whose content is already current must still get a fresh stamp.

    Regression guard for the pre-5.9 behaviour that froze `version=` at
    whichever release last changed the content: 51 of 78 real projects were
    stamped 4.23.0 / 2.17.0 while carrying byte-identical 5.9.0 content.
    """
    managed = "STABLE"
    hash12 = compute_managed_hash(managed)
    target = (
        f"<!-- arkaos:managed:start version=4.23.0 hash={hash12} -->\n"
        f"{managed}\n"
        "<!-- arkaos:managed:end -->\n\n"
        "## Project notes\n\nCustom.\n"
    )

    result = merge_managed_content(
        target_text=target, managed_content=managed, version="5.9.0"
    )

    assert result.status == "restamped"
    assert "version=5.9.0" in result.new_text
    assert "version=4.23.0" not in result.new_text
    assert f"hash={hash12}" in result.new_text
    assert managed in result.new_text
    assert "Custom." in result.new_text


def test_restamp_is_idempotent() -> None:
    managed = "STABLE"
    target = merge_managed_content("", managed, "5.9.0").new_text

    second = merge_managed_content(target, managed, "5.9.0")

    assert second.status == "unchanged"
    assert second.new_text == target


def test_merge_restamps_block_missing_a_version_stamp() -> None:
    managed = "STABLE"
    hash12 = compute_managed_hash(managed)
    target = (
        f"<!-- arkaos:managed:start hash={hash12} -->\n"
        f"{managed}\n"
        "<!-- arkaos:managed:end -->\n"
    )

    result = merge_managed_content(target, managed, "5.9.0")

    assert result.status == "restamped"
    assert "version=5.9.0" in result.new_text


def test_changed_content_still_reports_updated_not_restamped() -> None:
    """Real content drift must never be downgraded to a cosmetic restamp."""
    old_hash = compute_managed_hash("OLD CORE")
    target = (
        f"<!-- arkaos:managed:start version=4.23.0 hash={old_hash} -->\n"
        "OLD CORE\n"
        "<!-- arkaos:managed:end -->\n"
    )

    result = merge_managed_content(target, "NEW CORE", "5.9.0")

    assert result.status == "updated"
    assert "NEW CORE" in result.new_text
    assert "OLD CORE" not in result.new_text


def test_merge_detects_end_before_start_as_error() -> None:
    target = (
        "<!-- arkaos:managed:end -->\n"
        "INVERTED\n"
        "<!-- arkaos:managed:start version=4.23.0 hash=abc123abc123 -->\n"
    )

    result = merge_managed_content(target, "CORE", "5.9.0")

    assert result.status == "error"
    assert "end marker appears before start marker" in (result.error or "")
    assert result.new_text == target


def test_merge_detects_unbalanced_markers_as_error() -> None:
    target = (
        "<!-- arkaos:managed:start version=2.16.0 hash=abc123abc123 -->\n"
        "ORPHAN START\n"
    )

    result = merge_managed_content(
        target_text=target,
        managed_content="ANYTHING",
        version="2.17.0",
    )

    assert result.status == "error"
    assert "unbalanced" in (result.error or "").lower()


def test_merge_preserves_empty_target() -> None:
    result = merge_managed_content(
        target_text="",
        managed_content="CORE",
        version="2.17.0",
    )
    assert result.status == "updated"
    assert "CORE" in result.new_text


# ---------------------------------------------------------------------------
# In-place edits inside the managed block (QG round 3)
#
# The stored stamp is a CLAIM about the content, not a measurement of it. The
# first cut of `restamped` trusted the claim: an operator who edited inside
# the block left the stamp untouched, so the merger judged the content
# current and rewrote the block from canonical — deleting the edit in order
# to correct a version number. On master the same case returned `unchanged`
# and the edit survived, so this was a regression introduced by the fix.
# ---------------------------------------------------------------------------


def _block(body: str, *, version: str, stamped: str | None = None) -> str:
    """A managed block whose stamp may deliberately disagree with its body."""
    hash12 = compute_managed_hash(stamped if stamped is not None else body)
    return (
        f"<!-- arkaos:managed:start version={version} hash={hash12} -->\n"
        f"{body}\n"
        "<!-- arkaos:managed:end -->\n"
    )


def test_in_place_edit_is_never_overwritten_by_a_restamp() -> None:
    canonical = "CORE DOCTRINE"
    target = _block(
        f"{canonical}\nMY OWN RULE", version="5.9.0", stamped=canonical
    ) + "\n## Project notes\n"

    result = merge_managed_content(target, canonical, "5.10.0")

    assert result.status == "drifted"
    assert result.new_text == target
    assert "MY OWN RULE" in result.new_text
    assert "edited in place" in (result.error or "")


def test_in_place_edit_is_not_overwritten_at_the_same_version_either() -> None:
    canonical = "CORE DOCTRINE"
    target = _block(f"{canonical}\nMY OWN RULE", version="5.10.0", stamped=canonical)

    result = merge_managed_content(target, canonical, "5.10.0")

    assert result.status == "drifted"
    assert "MY OWN RULE" in result.new_text


def test_untouched_block_with_a_stale_stamp_still_restamps() -> None:
    """The drift guard must not disable the restamp it protects."""
    canonical = "CORE DOCTRINE"
    target = _block(canonical, version="5.9.0")

    result = merge_managed_content(target, canonical, "5.10.0")

    assert result.status == "restamped"
    assert "version=5.10.0" in result.new_text
    assert canonical in result.new_text


def test_real_canonical_change_still_updates_over_an_edited_block() -> None:
    """Drift must not shield a block from a genuine doctrine change."""
    target = _block("OLD DOCTRINE\nMY OWN RULE", version="5.9.0", stamped="OLD DOCTRINE")

    result = merge_managed_content(target, "NEW DOCTRINE", "5.10.0")

    assert result.status == "updated"
    assert "NEW DOCTRINE" in result.new_text

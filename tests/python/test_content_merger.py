"""Tests for core.sync.content_merger — managed-region merge algorithm."""

from __future__ import annotations

from pathlib import Path

import pytest

from core.sync.content_merger import (
    MergeResult,
    merge_managed_content,
    compute_managed_hash,
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
    target.write_text("# Project notes\n\nCustom content here.\n")

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

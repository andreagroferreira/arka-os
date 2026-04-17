"""Regression tests for core.runtime.user_paths.

Context: ArkaOS v2.19.0 relocates user-mutable data from
~/.claude/skills/arka/ (installer-managed) to ~/.arkaos/ (user-managed).
During the deprecation window both paths are readable with a one-shot
warning for the legacy location. See
docs/adr/2026-04-17-user-data-separation.md.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from core.runtime import user_paths


@pytest.fixture(autouse=True)
def redirect_home(tmp_path, monkeypatch):
    """Redirect Path.home() so each test runs in an isolated filesystem."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setattr(user_paths, "_USER_DATA_ROOT", tmp_path / ".arkaos")
    monkeypatch.setattr(
        user_paths, "_LEGACY_SKILLS_ROOT", tmp_path / ".claude" / "skills" / "arka"
    )
    user_paths.reset_warnings()
    yield tmp_path


def test_projects_dir_returns_new_path_when_present(redirect_home):
    new = redirect_home / ".arkaos" / "projects"
    new.mkdir(parents=True)
    assert user_paths.projects_dir() == new


def test_projects_dir_falls_back_to_legacy_with_warning(redirect_home, caplog):
    legacy = redirect_home / ".claude" / "skills" / "arka" / "projects"
    legacy.mkdir(parents=True)
    with caplog.at_level(logging.WARNING, logger="core.runtime.user_paths"):
        assert user_paths.projects_dir() == legacy
    assert any("legacy location" in r.getMessage() for r in caplog.records)


def test_projects_dir_returns_none_when_neither_exists(redirect_home):
    assert user_paths.projects_dir() is None


def test_ecosystems_file_returns_new_path_when_present(redirect_home):
    new = redirect_home / ".arkaos" / "ecosystems.json"
    new.parent.mkdir(parents=True)
    new.write_text('{"ecosystems": {}}')
    assert user_paths.ecosystems_file() == new


def test_ecosystems_file_falls_back_to_legacy_with_warning(redirect_home, caplog):
    legacy = (
        redirect_home / ".claude" / "skills" / "arka" / "knowledge" / "ecosystems.json"
    )
    legacy.parent.mkdir(parents=True)
    legacy.write_text('{"ecosystems": {}}')
    with caplog.at_level(logging.WARNING, logger="core.runtime.user_paths"):
        assert user_paths.ecosystems_file() == legacy
    assert any("legacy location" in r.getMessage() for r in caplog.records)


def test_warning_emitted_only_once_per_process(redirect_home, caplog):
    legacy = redirect_home / ".claude" / "skills" / "arka" / "projects"
    legacy.mkdir(parents=True)
    with caplog.at_level(logging.WARNING, logger="core.runtime.user_paths"):
        user_paths.projects_dir()
        user_paths.projects_dir()
        user_paths.projects_dir()
    warnings = [r for r in caplog.records if "legacy location" in r.getMessage()]
    assert len(warnings) == 1


def test_write_helpers_always_target_new_path_and_create_parents(redirect_home):
    pd = user_paths.projects_dir_for_write()
    assert pd == redirect_home / ".arkaos" / "projects"
    assert pd.is_dir()

    ef = user_paths.ecosystems_file_for_write()
    assert ef == redirect_home / ".arkaos" / "ecosystems.json"
    assert ef.parent.is_dir()


def test_new_path_wins_over_legacy_when_both_exist(redirect_home):
    new = redirect_home / ".arkaos" / "projects"
    new.mkdir(parents=True)
    legacy = redirect_home / ".claude" / "skills" / "arka" / "projects"
    legacy.mkdir(parents=True)
    assert user_paths.projects_dir() == new


def test_legacy_helpers_return_deprecated_locations(redirect_home):
    assert user_paths.legacy_projects_dir() == (
        redirect_home / ".claude" / "skills" / "arka" / "projects"
    )
    assert user_paths.legacy_ecosystems_file() == (
        redirect_home / ".claude" / "skills" / "arka" / "knowledge" / "ecosystems.json"
    )

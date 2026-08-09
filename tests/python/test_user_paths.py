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
    # Every test below asserts the NON-overridden chain; an override left
    # in the ambient environment would silently win over all of it.
    monkeypatch.delenv(user_paths.PROJECTS_DIR_ENV, raising=False)
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
    new.write_text('{"ecosystems": {}}', encoding="utf-8")
    assert user_paths.ecosystems_file() == new


def test_ecosystems_file_falls_back_to_legacy_with_warning(redirect_home, caplog):
    legacy = (
        redirect_home / ".claude" / "skills" / "arka" / "knowledge" / "ecosystems.json"
    )
    legacy.parent.mkdir(parents=True)
    legacy.write_text('{"ecosystems": {}}', encoding="utf-8")
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


class TestProjectsDirEnvOverride:
    """ARKA_PROJECTS_DIR — the isolation lever from #497 (ex-#510).

    The override exists so a caller can guarantee it is NOT touching the
    operator's real descriptors, so every property here is load-bearing:
    it wins over both candidates, it applies to writes as well as reads,
    and it never falls back — a fallback on a missing directory would put
    the writes straight back into the real home.
    """

    def test_override_wins_over_the_canonical_path(
        self, redirect_home, monkeypatch
    ):
        (redirect_home / ".arkaos" / "projects").mkdir(parents=True)
        override = redirect_home / "elsewhere"
        override.mkdir()
        monkeypatch.setenv(user_paths.PROJECTS_DIR_ENV, str(override))
        assert user_paths.projects_dir() == override

    def test_override_wins_over_the_legacy_path(
        self, redirect_home, monkeypatch
    ):
        (redirect_home / ".claude" / "skills" / "arka" / "projects").mkdir(
            parents=True
        )
        override = redirect_home / "elsewhere"
        override.mkdir()
        monkeypatch.setenv(user_paths.PROJECTS_DIR_ENV, str(override))
        assert user_paths.projects_dir() == override

    def test_override_never_falls_back_when_missing(
        self, redirect_home, monkeypatch
    ):
        """A non-existent override still wins — falling back to the real
        home is exactly the accident the override prevents."""
        (redirect_home / ".arkaos" / "projects").mkdir(parents=True)
        override = redirect_home / "does-not-exist"
        monkeypatch.setenv(user_paths.PROJECTS_DIR_ENV, str(override))
        assert user_paths.projects_dir() == override

    def test_override_redirects_writes_too(self, redirect_home, monkeypatch):
        override = redirect_home / "write-here"
        monkeypatch.setenv(user_paths.PROJECTS_DIR_ENV, str(override))
        target = user_paths.projects_dir_for_write()
        assert target == override
        assert target.is_dir(), "the write target is created like the default"
        assert not (redirect_home / ".arkaos" / "projects").exists()

    def test_blank_override_is_ignored(self, redirect_home, monkeypatch):
        new = redirect_home / ".arkaos" / "projects"
        new.mkdir(parents=True)
        monkeypatch.setenv(user_paths.PROJECTS_DIR_ENV, "   ")
        assert user_paths.projects_dir() == new

    def test_override_expands_user(self, redirect_home, monkeypatch):
        monkeypatch.setenv("HOME", str(redirect_home))
        monkeypatch.setenv(user_paths.PROJECTS_DIR_ENV, "~/tilde-projects")
        assert user_paths.projects_dir() == redirect_home / "tilde-projects"

    def test_override_is_read_at_call_time(self, redirect_home, monkeypatch):
        """Never cached: a per-test override must take effect immediately."""
        first = redirect_home / "one"
        second = redirect_home / "two"
        monkeypatch.setenv(user_paths.PROJECTS_DIR_ENV, str(first))
        assert user_paths.projects_dir() == first
        monkeypatch.setenv(user_paths.PROJECTS_DIR_ENV, str(second))
        assert user_paths.projects_dir() == second


def test_legacy_helpers_return_deprecated_locations(redirect_home):
    assert user_paths.legacy_projects_dir() == (
        redirect_home / ".claude" / "skills" / "arka" / "projects"
    )
    assert user_paths.legacy_ecosystems_file() == (
        redirect_home / ".claude" / "skills" / "arka" / "knowledge" / "ecosystems.json"
    )

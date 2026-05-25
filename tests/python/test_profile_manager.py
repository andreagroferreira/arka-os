"""Tests for the operator profile manager (PR63 v2.81.0)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.profile.manager import (
    Profile,
    ProfileManager,
    parse_projects_dirs,
)


# ─── Profile.from_dict ──────────────────────────────────────────────────


class TestFromDict:
    def test_empty_dict_yields_defaults(self):
        p = Profile.from_dict({})
        assert p.name == ""
        assert p.language == "en"
        assert p.version == "2"

    def test_known_fields_preserved(self):
        p = Profile.from_dict({
            "name": "André",
            "language": "pt",
            "company": "WizardingCode",
            "role": "founder",
        })
        assert p.name == "André"
        assert p.language == "pt"
        assert p.company == "WizardingCode"
        assert p.role == "founder"

    def test_unknown_fields_silently_dropped(self):
        p = Profile.from_dict({
            "name": "Test",
            "secret_key": "should-be-dropped",
            "evil": {"nested": "blob"},
        })
        assert p.name == "Test"
        assert not hasattr(p, "secret_key")

    def test_non_string_values_coerced(self):
        p = Profile.from_dict({
            "name": 42,            # int → "42"
            "language": True,      # bool → "True"
            "market": None,        # None → dropped (handled by from_dict)
        })
        assert p.name == "42"
        assert p.language == "True"
        assert p.market == ""  # None values dropped, default applies

    def test_non_dict_yields_default_profile(self):
        assert Profile.from_dict([]) == Profile()  # type: ignore[arg-type]
        assert Profile.from_dict("not-a-dict") == Profile()  # type: ignore[arg-type]


# ─── ProfileManager.read ────────────────────────────────────────────────


class TestRead:
    def test_returns_default_when_file_missing(self, tmp_path):
        mgr = ProfileManager(tmp_path / "no-such-file.json")
        p = mgr.read()
        assert p == Profile()

    def test_returns_parsed_profile(self, tmp_path):
        path = tmp_path / "profile.json"
        path.write_text(json.dumps({
            "version": "2",
            "name": "Test",
            "company": "ACME",
            "language": "pt",
        }))
        p = ProfileManager(path).read()
        assert p.name == "Test"
        assert p.company == "ACME"
        assert p.language == "pt"

    def test_returns_default_on_corrupt_json(self, tmp_path):
        path = tmp_path / "profile.json"
        path.write_text("not-json{")
        p = ProfileManager(path).read()
        assert p == Profile()

    def test_returns_default_on_top_level_array(self, tmp_path):
        """A JSON array at top level shouldn't crash — from_dict guards."""
        path = tmp_path / "profile.json"
        path.write_text(json.dumps(["not", "an", "object"]))
        p = ProfileManager(path).read()
        assert p == Profile()


# ─── ProfileManager.patch ───────────────────────────────────────────────


class TestPatch:
    def test_writes_new_file_on_first_patch(self, tmp_path):
        path = tmp_path / "profile.json"
        mgr = ProfileManager(path)
        updated = mgr.patch({"name": "André", "company": "WizardingCode"})
        assert path.exists()
        assert updated.name == "André"
        assert updated.company == "WizardingCode"
        # Round-trip
        reloaded = ProfileManager(path).read()
        assert reloaded.name == "André"

    def test_merges_with_existing_data(self, tmp_path):
        path = tmp_path / "profile.json"
        path.write_text(json.dumps({"name": "Old", "language": "en", "company": "Keep"}))
        updated = ProfileManager(path).patch({"name": "New", "role": "founder"})
        assert updated.name == "New"          # patched
        assert updated.role == "founder"      # added
        assert updated.language == "en"       # preserved
        assert updated.company == "Keep"      # preserved

    def test_drops_unwritable_fields(self, tmp_path):
        path = tmp_path / "profile.json"
        mgr = ProfileManager(path)
        mgr.patch({"name": "Test", "version": "99", "created": "fake"})
        data = json.loads(path.read_text())
        # 'version' is locked to "2"; 'created' is bootstrapped by patch
        assert data["version"] == "2"
        assert data["created"] != "fake"
        # created stamps an ISO timestamp on first patch
        assert "T" in data["created"]

    def test_updates_timestamp_on_every_patch(self, tmp_path):
        path = tmp_path / "profile.json"
        mgr = ProfileManager(path)
        first = mgr.patch({"name": "A"})
        second = mgr.patch({"name": "B"})
        assert first.updated != ""
        assert second.updated != ""
        assert second.updated >= first.updated

    def test_preserves_created_on_subsequent_patches(self, tmp_path):
        path = tmp_path / "profile.json"
        mgr = ProfileManager(path)
        first = mgr.patch({"name": "A"})
        second = mgr.patch({"name": "B"})
        assert second.created == first.created

    def test_coerces_non_string_values(self, tmp_path):
        path = tmp_path / "profile.json"
        ProfileManager(path).patch({"market": 42, "role": True})
        data = json.loads(path.read_text())
        assert data["market"] == "42"
        assert data["role"] == "True"

    def test_silently_ignores_disk_failure(self, tmp_path, monkeypatch):
        """Patch returns a Profile object even when the write fails."""
        path = tmp_path / "readonly" / "profile.json"
        mgr = ProfileManager(path)
        # Don't create the parent. Make write raise.
        def fake_replace(self, target):
            raise OSError("simulated disk failure")
        monkeypatch.setattr(Path, "replace", fake_replace)
        # Must not raise
        result = mgr.patch({"name": "X"})
        assert isinstance(result, Profile)


# ─── parse_projects_dirs ────────────────────────────────────────────────


class TestParseProjectsDirs:
    def test_empty_returns_empty_list(self):
        assert parse_projects_dirs("") == []
        assert parse_projects_dirs("   ") == []

    def test_single_path(self):
        assert parse_projects_dirs("/Users/foo/Work") == ["/Users/foo/Work"]

    def test_comma_separated_paths(self):
        result = parse_projects_dirs("/Users/foo/Herd, /Users/foo/Work")
        assert result == ["/Users/foo/Herd", "/Users/foo/Work"]

    def test_handles_prose_between_paths(self):
        """Historical schema: '/path/A para X, /path/B para Y'."""
        result = parse_projects_dirs(
            "/Users/foo/Herd para projectos laravel, "
            "/Users/foo/Work para projectos Nuxt, js, e python"
        )
        assert result == ["/Users/foo/Herd", "/Users/foo/Work"]

    def test_picks_first_path_per_segment(self):
        """If a segment has two paths, only the first wins (rare edge)."""
        result = parse_projects_dirs("/a /b, /c")
        assert result == ["/a", "/c"]

    def test_accepts_home_relative(self):
        result = parse_projects_dirs("~/dev, ~/work")
        assert result == ["~/dev", "~/work"]

    def test_skips_non_paths(self):
        result = parse_projects_dirs("relative/no-leading-slash, /good/one")
        assert result == ["/good/one"]

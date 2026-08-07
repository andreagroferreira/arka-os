"""core.harness.paths — call-time resolution, no import-time capture."""

from pathlib import Path

from core.harness import paths


class TestExplicitHome:
    def test_all_home_paths_land_under_the_given_home(self, tmp_path):
        assert paths.claude_home(tmp_path) == tmp_path / ".claude"
        assert (
            paths.claude_settings_path(tmp_path)
            == tmp_path / ".claude" / "settings.json"
        )
        assert (
            paths.claude_global_md_path(tmp_path)
            == tmp_path / ".claude" / "CLAUDE.md"
        )
        assert paths.arkaos_home(tmp_path) == tmp_path / ".arkaos"
        assert (
            paths.ownership_manifest_path(tmp_path)
            == tmp_path / ".arkaos" / "ownership.json"
        )
        assert paths.audit_dir(tmp_path) == tmp_path / ".arkaos" / "audit"
        assert (
            paths.harness_audit_log_path(tmp_path)
            == tmp_path / ".arkaos" / "audit" / "harness-mutations.jsonl"
        )
        assert (
            paths.hard_deny_extension_path(tmp_path)
            == tmp_path / ".arkaos" / "hard-deny.json"
        )
        assert (
            paths.arkaos_config_path(tmp_path)
            == tmp_path / ".arkaos" / "config.json"
        )


class TestCallTimeResolution:
    def test_default_home_is_read_at_call_time(self, tmp_path, monkeypatch):
        """Two calls under two HOMEs give two answers — nothing is
        captured at import, the failure mode PR-A2 closed."""
        home_a = tmp_path / "a"
        home_b = tmp_path / "b"
        monkeypatch.setenv("HOME", str(home_a))
        first = paths.claude_settings_path()
        monkeypatch.setenv("HOME", str(home_b))
        second = paths.claude_settings_path()
        assert first == home_a / ".claude" / "settings.json"
        assert second == home_b / ".claude" / "settings.json"

    def test_hooks_dir_honours_explicit_root(self, tmp_path):
        assert (
            paths.hooks_dir(str(tmp_path))
            == tmp_path / "config" / "hooks"
        )

    def test_hooks_dir_resolves_root_at_call_time(self, monkeypatch):
        monkeypatch.setattr(
            paths, "resolve_arkaos_root", lambda: "/resolved/root"
        )
        assert paths.hooks_dir() == Path("/resolved/root/config/hooks")

"""Tests for the one-stop /arka update orchestrator (PR61 v2.78.0)."""

from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from core.sync import update_orchestrator as uo
from core.sync.schema import SyncReport


# ─── Semver helpers ─────────────────────────────────────────────────────


class TestSemverHelpers:
    @pytest.mark.parametrize("value,expected", [
        ("2.77.0", True),
        ("2.77.0-beta.1", True),
        ("1.0.0", True),
        ("v1.0.0", False),     # leading v not allowed by our shape
        ("2.77", False),       # missing patch
        ("a.b.c", False),
        ("", False),
        ("x" * 40, False),     # too long
    ])
    def test_looks_like_semver(self, value, expected):
        assert uo._looks_like_semver(value) is expected

    def test_parse_semver_handles_prerelease(self):
        assert uo._parse_semver("2.77.0-beta.1") == (2, 77, 0)
        assert uo._parse_semver("2.39.0") == (2, 39, 0)

    def test_parse_semver_handles_garbage(self):
        assert uo._parse_semver("not-a-version") == (0, 0, 0)

    @pytest.mark.parametrize("installed,latest,expected", [
        ("2.39.0", "2.77.0", True),
        ("2.77.0", "2.77.0", False),
        ("2.77.0", "2.39.0", False),
        ("2.0.0", "2.10.0", True),
        ("2.39.0-beta.1", "2.39.0", False),  # equal major.minor.patch
    ])
    def test_is_older(self, installed, latest, expected):
        assert uo._is_older(installed, latest) is expected


# ─── npm probe ──────────────────────────────────────────────────────────


class TestNpmProbe:
    def test_returns_cached_when_fresh(self, tmp_path):
        cache = tmp_path / "cache.json"
        cache.write_text(json.dumps({"version": "2.77.0", "ts": time.time()}), encoding="utf-8")
        assert uo._probe_npm_latest(cache) == "2.77.0"

    def test_ignores_expired_cache(self, tmp_path, monkeypatch):
        cache = tmp_path / "cache.json"
        old_ts = time.time() - 2 * uo._NPM_CACHE_TTL_SECONDS
        cache.write_text(json.dumps({"version": "2.39.0", "ts": old_ts}), encoding="utf-8")
        # Force the shell probe to return a different version
        called = MagicMock()

        def fake_run(cmd, **kw):
            called(cmd)
            return MagicMock(returncode=0, stdout="2.77.0\n", stderr="")

        monkeypatch.setattr(uo.subprocess, "run", fake_run)
        assert uo._probe_npm_latest(cache) == "2.77.0"
        called.assert_called_once()
        # Cache is rewritten with the fresh value
        refreshed = json.loads(cache.read_text(encoding="utf-8"))
        assert refreshed["version"] == "2.77.0"

    def test_returns_none_on_timeout(self, tmp_path, monkeypatch):
        import subprocess as sp

        def fake_run(cmd, **kw):
            raise sp.TimeoutExpired(cmd=cmd, timeout=5)

        monkeypatch.setattr(uo.subprocess, "run", fake_run)
        assert uo._probe_npm_latest(tmp_path / "cache.json") is None

    def test_returns_none_on_non_zero_exit(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            uo.subprocess, "run",
            lambda cmd, **kw: MagicMock(returncode=1, stdout="", stderr="oops"),
        )
        assert uo._probe_npm_latest(tmp_path / "cache.json") is None

    def test_returns_none_on_garbage_output(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            uo.subprocess, "run",
            lambda cmd, **kw: MagicMock(
                returncode=0, stdout="latest is now garbage\n", stderr="",
            ),
        )
        assert uo._probe_npm_latest(tmp_path / "cache.json") is None

    def test_returns_none_on_oserror(self, tmp_path, monkeypatch):
        def fake_run(cmd, **kw):
            raise OSError("npm not on PATH")

        monkeypatch.setattr(uo.subprocess, "run", fake_run)
        assert uo._probe_npm_latest(tmp_path / "cache.json") is None


# ─── orchestrate end-to-end (with fakes) ────────────────────────────────


def _stub_report() -> SyncReport:
    return SyncReport(
        previous_version="2.39.0",
        current_version="2.77.0",
        new_features=[],
        deprecated_features=[],
        mcp_results=[],
        settings_results=[],
        descriptor_results=[],
        ecosystem_skill_results=[],
        sync_state_path="stub",
        warnings=[],
    )


class TestOrchestrate:
    def test_runs_npx_when_installed_is_older(self, tmp_path, monkeypatch):
        npx_called = MagicMock()
        monkeypatch.setattr(
            uo, "run_sync",
            lambda **kw: _stub_report(),
        )
        monkeypatch.setattr(
            uo, "_safe_read_version",
            lambda _home: "2.39.0",
        )
        installed, latest, report = uo.orchestrate(
            arkaos_home=tmp_path,
            skills_dir=tmp_path,
            home_path=str(tmp_path),
            npm_probe=lambda _cache: "2.77.0",
            npx_run=npx_called,
        )
        assert installed == "2.39.0"
        assert latest == "2.77.0"
        npx_called.assert_called_once()
        assert report is not None

    def test_skips_npx_when_already_latest(self, tmp_path, monkeypatch):
        npx_called = MagicMock()
        monkeypatch.setattr(
            uo, "run_sync",
            lambda **kw: _stub_report(),
        )
        monkeypatch.setattr(
            uo, "_safe_read_version",
            lambda _home: "2.77.0",
        )
        uo.orchestrate(
            arkaos_home=tmp_path,
            skills_dir=tmp_path,
            home_path=str(tmp_path),
            npm_probe=lambda _cache: "2.77.0",
            npx_run=npx_called,
        )
        npx_called.assert_not_called()

    def test_skips_npx_when_probe_returns_none(self, tmp_path, monkeypatch):
        """npm offline / slow → probe returns None → skip npx, run sync anyway."""
        npx_called = MagicMock()
        monkeypatch.setattr(
            uo, "run_sync",
            lambda **kw: _stub_report(),
        )
        monkeypatch.setattr(
            uo, "_safe_read_version",
            lambda _home: "2.39.0",
        )
        uo.orchestrate(
            arkaos_home=tmp_path,
            skills_dir=tmp_path,
            home_path=str(tmp_path),
            npm_probe=lambda _cache: None,
            npx_run=npx_called,
        )
        npx_called.assert_not_called()

    def test_skips_npx_when_installed_unknown(self, tmp_path, monkeypatch):
        """No VERSION readable → can't compare → don't auto-update."""
        npx_called = MagicMock()
        monkeypatch.setattr(uo, "run_sync", lambda **kw: _stub_report())
        monkeypatch.setattr(uo, "_safe_read_version", lambda _home: None)
        uo.orchestrate(
            arkaos_home=tmp_path,
            skills_dir=tmp_path,
            home_path=str(tmp_path),
            npm_probe=lambda _cache: "2.77.0",
            npx_run=npx_called,
        )
        npx_called.assert_not_called()

    def test_always_returns_sync_report(self, tmp_path, monkeypatch):
        monkeypatch.setattr(uo, "run_sync", lambda **kw: _stub_report())
        monkeypatch.setattr(uo, "_safe_read_version", lambda _home: "2.39.0")
        _, _, report = uo.orchestrate(
            arkaos_home=tmp_path,
            skills_dir=tmp_path,
            home_path=str(tmp_path),
            npm_probe=lambda _cache: None,
            npx_run=lambda _home: None,
        )
        assert report is not None


# ─── _run_npx_update never raises ───────────────────────────────────────


class TestRunNpxUpdate:
    def test_swallows_oserror(self, tmp_path, monkeypatch, capsys):
        def fake_run(cmd, **kw):
            raise OSError("npx missing")

        monkeypatch.setattr(uo.subprocess, "run", fake_run)
        # Must not raise
        uo._run_npx_update(tmp_path)
        err = capsys.readouterr().err
        assert "npx arkaos@latest update failed" in err

    def test_swallows_timeout(self, tmp_path, monkeypatch, capsys):
        import subprocess as sp

        def fake_run(cmd, **kw):
            raise sp.TimeoutExpired(cmd=cmd, timeout=600)

        monkeypatch.setattr(uo.subprocess, "run", fake_run)
        uo._run_npx_update(tmp_path)
        assert "npx arkaos@latest update failed" in capsys.readouterr().err

    def test_returncode_nonzero_does_not_raise(self, tmp_path, monkeypatch):
        """check=False means we never raise on non-zero exit; we log via
        stderr inside subprocess and the orchestrator falls through."""
        monkeypatch.setattr(
            uo.subprocess, "run",
            lambda cmd, **kw: MagicMock(returncode=1),
        )
        # Must not raise
        uo._run_npx_update(tmp_path)

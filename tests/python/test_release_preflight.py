"""Tests for core.release.preflight (PR21 v2.43.0).

Pre-release pipeline gate. Validates version alignment + npm/gh
credentials + git state BEFORE the irreversible tag/push/publish
steps. Closes a debt identified during v2.40.0 release (1h lost
to expired npm token discovered post-merge).

Subprocess is fully mocked — these tests never touch the network,
the npm CLI, or the gh CLI.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from core.release.preflight import (
    CheckResult,
    PreflightReport,
    _format_leak_check_result,
    check_git_clean,
    check_git_remote,
    check_gh_auth,
    check_npm_auth,
    check_npm_publish_capability,
    check_version_alignment,
    run_preflight,
)


# ─── Subprocess mock helpers ────────────────────────────────────────────


def _fake_run(stdout: str = "", stderr: str = "", returncode: int = 0):
    def runner(*args, **kwargs):
        return subprocess.CompletedProcess(
            args=args[0] if args else [],
            returncode=returncode,
            stdout=stdout,
            stderr=stderr,
        )
    return runner


def _patch_subprocess(monkeypatch, mapping: dict[str, tuple[str, str, int]]):
    """Route subprocess.run to canned responses keyed by the first arg.

    mapping maps the executable name (e.g. "npm", "gh", "git") to a
    (stdout, stderr, returncode) tuple.
    """
    def router(cmd, *args, **kwargs):
        exe = cmd[0] if isinstance(cmd, (list, tuple)) else cmd.split()[0]
        if exe in mapping:
            stdout, stderr, rc = mapping[exe]
        else:
            stdout, stderr, rc = "", "command not found", 127
        return subprocess.CompletedProcess(
            args=cmd, returncode=rc, stdout=stdout, stderr=stderr,
        )
    monkeypatch.setattr(subprocess, "run", router)


# ─── Version alignment ──────────────────────────────────────────────────


class TestVersionAlignment:
    def _write_versions(self, tmp_path: Path, v_ver: str, v_pkg: str, v_pyproj: str):
        (tmp_path / "VERSION").write_text(v_ver, encoding="utf-8")
        (tmp_path / "package.json").write_text(
            f'{{"name":"arkaos","version":"{v_pkg}"}}\n', encoding="utf-8",
        )
        (tmp_path / "pyproject.toml").write_text(
            f'[project]\nname = "arkaos-core"\nversion = "{v_pyproj}"\n',
            encoding="utf-8",
        )

    def test_aligned_versions_pass(self, tmp_path: Path):
        self._write_versions(tmp_path, "2.42.0", "2.42.0", "2.42.0")
        result = check_version_alignment(repo_root=tmp_path)
        assert isinstance(result, CheckResult)
        assert result.passed is True
        assert result.severity == "blocking"

    def test_mismatch_fails_with_diagnostic(self, tmp_path: Path):
        self._write_versions(tmp_path, "2.42.0", "2.41.0", "2.42.0")
        result = check_version_alignment(repo_root=tmp_path)
        assert result.passed is False
        assert "2.41.0" in result.reason or "package.json" in result.reason

    def test_missing_file_fails_blocking(self, tmp_path: Path):
        # No VERSION file
        result = check_version_alignment(repo_root=tmp_path)
        assert result.passed is False
        assert result.severity == "blocking"


# ─── npm auth ───────────────────────────────────────────────────────────


class TestNpmAuth:
    def test_whoami_success_passes(self, monkeypatch):
        _patch_subprocess(monkeypatch, {"npm": ("wizardingcode\n", "", 0)})
        result = check_npm_auth(expected_user="wizardingcode")
        assert result.passed is True

    def test_whoami_401_fails(self, monkeypatch):
        _patch_subprocess(monkeypatch, {"npm": ("", "E401 Unauthorized", 1)})
        result = check_npm_auth(expected_user="wizardingcode")
        assert result.passed is False
        assert result.remediation is not None
        assert "npm" in result.remediation.lower()

    def test_unexpected_user_fails(self, monkeypatch):
        _patch_subprocess(monkeypatch, {"npm": ("someone-else\n", "", 0)})
        result = check_npm_auth(expected_user="wizardingcode")
        assert result.passed is False

    def test_no_expected_user_passes_any_login(self, monkeypatch):
        _patch_subprocess(monkeypatch, {"npm": ("anyone\n", "", 0)})
        result = check_npm_auth(expected_user=None)
        assert result.passed is True


# ─── npm publish capability ─────────────────────────────────────────────


class TestNpmPublishCapability:
    def test_pack_dry_run_succeeds(self, monkeypatch):
        _patch_subprocess(monkeypatch, {"npm": ("tarball-name.tgz\n", "", 0)})
        result = check_npm_publish_capability()
        assert result.passed is True

    def test_pack_dry_run_fails(self, monkeypatch):
        _patch_subprocess(monkeypatch, {"npm": ("", "ENOENT", 1)})
        result = check_npm_publish_capability()
        assert result.passed is False


# ─── gh auth ────────────────────────────────────────────────────────────


class TestGhAuth:
    def test_auth_status_ok(self, monkeypatch):
        _patch_subprocess(monkeypatch, {"gh": ("Logged in as user", "", 0)})
        result = check_gh_auth()
        assert result.passed is True

    def test_auth_status_fail(self, monkeypatch):
        _patch_subprocess(monkeypatch, {"gh": ("", "not logged in", 1)})
        result = check_gh_auth()
        assert result.passed is False


# ─── git checks ─────────────────────────────────────────────────────────


class TestGitChecks:
    def test_remote_ok(self, monkeypatch):
        _patch_subprocess(
            monkeypatch,
            {"git": ("https://github.com/foo/bar.git\n", "", 0)},
        )
        result = check_git_remote()
        assert result.passed is True

    def test_remote_missing_fails(self, monkeypatch):
        _patch_subprocess(monkeypatch, {"git": ("", "no remote", 1)})
        result = check_git_remote()
        assert result.passed is False

    def test_git_clean_is_warning_not_blocking(self, monkeypatch):
        _patch_subprocess(
            monkeypatch,
            {"git": (" M VERSION\n M package.json\n", "", 0)},
        )
        result = check_git_clean()
        # Dirty tree is a warning, not a block — releases from dirty
        # branches are sometimes intentional.
        assert result.severity == "warning"
        assert result.passed is False  # but flagged

    def test_git_clean_when_clean_passes(self, monkeypatch):
        _patch_subprocess(monkeypatch, {"git": ("", "", 0)})
        result = check_git_clean()
        assert result.passed is True


# ─── Aggregation ────────────────────────────────────────────────────────


# ─── PR23 v2.45.0 contract: leak check severity is BLOCKING ─────────────


class TestLeakCheckSeverity:
    """PR23 locks the post-cleanup contract: when scan returns hits, the
    check MUST be 'blocking' (never downgraded to 'warning' again).

    PR22 v2.44.0 introduced this check at 'warning' to ship the scanner
    without blocking on 39 pre-existing leaks. PR23 scrubbed those leaks
    and flipped the severity. This test asserts the flip stays put.
    """

    def test_severity_is_blocking_when_hits_present(self):
        # Build a synthetic ScanReport that has hits — same shape the
        # real scanner returns, sufficient for the formatter contract.
        from types import SimpleNamespace
        from pathlib import Path
        fake_report = SimpleNamespace(
            pattern_count=3,
            files_scanned=10,
            clean=False,
            hits=[SimpleNamespace(
                path=Path("fake.py"),
                line_number=42,
                matched_token="acmecorp",
            )],
        )
        result = _format_leak_check_result(fake_report)
        assert result.severity == "blocking"
        assert result.passed is False
        assert "acmecorp" in result.reason

    def test_severity_remains_blocking_for_clean_pass(self):
        # Clean reports still pass — but the contract is that the FAIL
        # path must be blocking, not warning.
        from types import SimpleNamespace
        fake_report = SimpleNamespace(
            pattern_count=3,
            files_scanned=10,
            clean=True,
            hits=[],
        )
        result = _format_leak_check_result(fake_report)
        assert result.passed is True


class TestAggregation:
    def test_run_preflight_aggregates_results(self, monkeypatch, tmp_path: Path):
        # All systems green
        (tmp_path / "VERSION").write_text("2.43.0", encoding="utf-8")
        (tmp_path / "package.json").write_text(
            '{"name":"arkaos","version":"2.43.0"}\n', encoding="utf-8",
        )
        (tmp_path / "pyproject.toml").write_text(
            'version = "2.43.0"\n', encoding="utf-8",
        )
        _patch_subprocess(monkeypatch, {
            "npm": ("wizardingcode\n", "", 0),
            "gh":  ("Logged in", "", 0),
            "git": ("https://github.com/foo/bar.git\n", "", 0),
        })
        report = run_preflight(
            repo_root=tmp_path,
            expected_npm_user="wizardingcode",
        )
        assert isinstance(report, PreflightReport)
        assert report.all_passed is True
        assert report.blocking_failures == []

    def test_run_preflight_collects_failures(self, monkeypatch, tmp_path: Path):
        # Version mismatch — should block
        (tmp_path / "VERSION").write_text("2.43.0", encoding="utf-8")
        (tmp_path / "package.json").write_text(
            '{"name":"arkaos","version":"2.42.0"}\n', encoding="utf-8",
        )
        (tmp_path / "pyproject.toml").write_text(
            'version = "2.43.0"\n', encoding="utf-8",
        )
        _patch_subprocess(monkeypatch, {
            "npm": ("wizardingcode\n", "", 0),
            "gh":  ("Logged in", "", 0),
            "git": ("https://github.com/foo/bar.git\n", "", 0),
        })
        report = run_preflight(repo_root=tmp_path, expected_npm_user=None)
        assert report.all_passed is False
        assert any(r.name == "version-alignment" for r in report.blocking_failures)

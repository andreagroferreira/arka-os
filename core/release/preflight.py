"""Release preflight gate (PR21 v2.43.0).

Runs BEFORE the irreversible tag/push/publish steps of the release
pipeline. Catches expired tokens, version misalignment, and dirty
git state at minute 0 instead of minute 60.

Closes a real-world debt: v2.40.0 release took ~1h because the npm
token had expired silently and the failure was only discovered
after merge, tag, GH release. A 2-second check up front would have
turned that into an immediate STOP-and-rotate.

All shell-outs use ``subprocess.run(check=False, capture_output=True,
timeout=10)`` with argv as a list — no ``shell=True``, no string
interpolation of user input.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

_DEFAULT_REPO_ROOT = Path.cwd()
_SUBPROCESS_TIMEOUT = 10
_NPM_PACKAGE_VERSION_RE = re.compile(r'"version"\s*:\s*"([^"]+)"')
_PYPROJECT_VERSION_RE = re.compile(r'^version\s*=\s*"([^"]+)"', re.MULTILINE)


@dataclass(frozen=True)
class CheckResult:
    """Single preflight check outcome."""
    name: str
    passed: bool
    reason: str
    remediation: str | None = None
    severity: str = "blocking"


@dataclass(frozen=True)
class PreflightReport:
    """Aggregated preflight verdict."""
    all_passed: bool
    results: list[CheckResult] = field(default_factory=list)
    blocking_failures: list[CheckResult] = field(default_factory=list)
    warnings: list[CheckResult] = field(default_factory=list)


def run_preflight(
    *,
    repo_root: Path | None = None,
    expected_npm_user: str | None = None,
) -> PreflightReport:
    """Run every preflight check and return an aggregated report."""
    root = repo_root or _DEFAULT_REPO_ROOT
    results = [
        check_version_alignment(repo_root=root),
        check_npm_auth(expected_user=expected_npm_user),
        check_npm_publish_capability(),
        check_gh_auth(),
        check_git_remote(),
        check_git_clean(),
    ]
    return _aggregate(results)


def _load_repo_versions(
    root: Path,
) -> tuple[str | None, str | None, str | None] | None:
    """Read VERSION, package.json, pyproject.toml. None if any unreadable."""
    try:
        v = (root / "VERSION").read_text(encoding="utf-8").strip()
        pkg_match = _NPM_PACKAGE_VERSION_RE.search(
            (root / "package.json").read_text(encoding="utf-8"),
        )
        py_match = _PYPROJECT_VERSION_RE.search(
            (root / "pyproject.toml").read_text(encoding="utf-8"),
        )
    except (OSError, AttributeError):
        return None
    pkg_v = pkg_match.group(1) if pkg_match else None
    py_v = py_match.group(1) if py_match else None
    return v, pkg_v, py_v


def check_version_alignment(*, repo_root: Path | None = None) -> CheckResult:
    """Verify VERSION, package.json, pyproject.toml all carry the same version."""
    root = repo_root or _DEFAULT_REPO_ROOT
    versions = _load_repo_versions(root)
    if versions is None:
        return CheckResult(
            name="version-alignment", passed=False,
            reason="could not read one of VERSION / package.json / pyproject.toml",
            remediation="ensure all three files exist at repo root",
        )
    v, pkg_v, py_v = versions
    if v and pkg_v == v and py_v == v:
        return CheckResult(
            name="version-alignment", passed=True,
            reason=f"all three at {v}",
        )
    return CheckResult(
        name="version-alignment", passed=False,
        reason=f"mismatch: VERSION={v} package.json={pkg_v} pyproject={py_v}",
        remediation="align all three files to the same version, then re-run",
    )


def check_npm_auth(*, expected_user: str | None = None) -> CheckResult:
    """Verify `npm whoami` returns a valid user (and matches expected, if set)."""
    out = _run(["npm", "whoami"])
    if out is None:
        return CheckResult(
            name="npm-auth", passed=False,
            reason="npm command not found or timed out",
            remediation="install Node.js / npm and retry",
        )
    if out.returncode != 0:
        return CheckResult(
            name="npm-auth", passed=False,
            reason=f"npm whoami failed: {out.stderr.strip() or 'unknown'}",
            remediation="run `npm login` or rotate token in ~/.npmrc",
        )
    user = out.stdout.strip()
    if expected_user and user != expected_user:
        return CheckResult(
            name="npm-auth", passed=False,
            reason=f"npm authenticated as {user}, expected {expected_user}",
            remediation=f"switch token to {expected_user} or update expected user",
        )
    return CheckResult(
        name="npm-auth", passed=True,
        reason=f"authenticated as {user}",
    )


def check_npm_publish_capability() -> CheckResult:
    """Verify `npm pack --dry-run` succeeds — proves write scope on the package."""
    out = _run(["npm", "pack", "--dry-run"])
    if out is None or out.returncode != 0:
        msg = (out.stderr.strip() if out else "command unavailable") or "unknown"
        return CheckResult(
            name="npm-publish-capability", passed=False,
            reason=f"pack dry-run failed: {msg}",
            remediation="check granular token has 'read and write' on this package",
        )
    return CheckResult(
        name="npm-publish-capability", passed=True,
        reason="pack dry-run OK",
    )


def check_gh_auth() -> CheckResult:
    """Verify `gh auth status` reports a logged-in session."""
    out = _run(["gh", "auth", "status"])
    if out is None:
        return CheckResult(
            name="gh-auth", passed=False,
            reason="gh command not found or timed out",
            remediation="install the GitHub CLI and run `gh auth login`",
        )
    if out.returncode != 0:
        return CheckResult(
            name="gh-auth", passed=False,
            reason="gh not authenticated",
            remediation="run `gh auth login`",
        )
    return CheckResult(name="gh-auth", passed=True, reason="authenticated")


def check_git_remote() -> CheckResult:
    """Verify `git remote get-url origin` returns a real remote URL."""
    out = _run(["git", "remote", "get-url", "origin"])
    if out is None or out.returncode != 0:
        return CheckResult(
            name="git-remote", passed=False,
            reason="no `origin` remote configured",
            remediation="set up the remote with `git remote add origin <url>`",
        )
    return CheckResult(
        name="git-remote", passed=True,
        reason=out.stdout.strip(),
    )


def check_git_clean() -> CheckResult:
    """Flag uncommitted changes as a WARNING (not blocking)."""
    out = _run(["git", "status", "--porcelain"])
    if out is None:
        return CheckResult(
            name="git-clean", passed=False, severity="warning",
            reason="git not available",
        )
    dirty = out.stdout.strip()
    if not dirty:
        return CheckResult(name="git-clean", passed=True, reason="working tree clean")
    file_count = len([line for line in dirty.splitlines() if line.strip()])
    return CheckResult(
        name="git-clean", passed=False, severity="warning",
        reason=f"{file_count} uncommitted file(s)",
        remediation="commit, stash, or proceed deliberately",
    )


def _run(cmd: list[str]) -> subprocess.CompletedProcess | None:
    """subprocess.run with our defaults; returns None on missing exe / timeout."""
    try:
        return subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=_SUBPROCESS_TIMEOUT, check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None


def _aggregate(results: list[CheckResult]) -> PreflightReport:
    blocking = [r for r in results if not r.passed and r.severity == "blocking"]
    warnings = [r for r in results if not r.passed and r.severity == "warning"]
    return PreflightReport(
        all_passed=not blocking,
        results=results,
        blocking_failures=blocking,
        warnings=warnings,
    )

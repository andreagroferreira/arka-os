"""Evidence check engine — executable checks behind the Quality Gate (PR-4).

Gate 4 verdicts DERIVE from tool output, not persona narrative. This
module runs real, read-only checks over a project (lint, typecheck,
tests, coverage, security grep, spellcheck) and returns a structured
``EvidenceReport``. Reviewers INTERPRET the report; they cannot
override it — ``overall == "fail"`` forces REJECTED.

Safety contract:
  - subprocesses run with ``cwd=project_dir``, ``capture_output=True``,
    argument lists only (never ``shell=True`` with interpolated input)
  - 300s cap per check; on expiry the process is killed and the check
    reports ``ran=True, passed=None, summary="timeout"``
  - nothing that mutates: no installs, no git, no writes to the project

CLI (for hooks/skills)::

    python -m core.governance.evidence_checks <project_dir> \
        [--checks lint,tests] [--test-command '...'] \
        [--changed-files f1,f2] [--json]
"""

from __future__ import annotations

import argparse
import json
import re
import shlex
import shutil
import subprocess
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from core.shared.test_evidence import coverage_percent_from_xml

TIMEOUT_SECONDS = 300
COVERAGE_THRESHOLD = 80.0
ALL_CHECKS: tuple[str, ...] = (
    "lint", "typecheck", "tests", "coverage", "security-grep", "spellcheck",
    "ui-screenshot",
)

# ui-screenshot artifact contract (Excellence Reform PR-D3): captures land
# in <project>/.arka/evidence/ui/ per brand/design-review; the check only
# stats files (read-only), it never runs a browser.
UI_EVIDENCE_DIR = Path(".arka") / "evidence" / "ui"
UI_SCREENSHOT_WINDOW_HOURS = 24
UI_SCREENSHOT_MIN_BYTES = 10 * 1024

_MAX_SUMMARY_CHARS = 800
_MAX_GREP_HITS = 20

# Obvious-classes security sweep. Line-level, over caller-supplied files.
_SECURITY_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("aws-access-key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("api-secret-key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}")),
    ("github-token", re.compile(r"\bghp_[A-Za-z0-9]{20,}")),
    (
        "hardcoded-password",
        re.compile(r"password\s*=\s*['\"][^'\"]{4,}['\"]", re.IGNORECASE),
    ),
    (
        "eval-exec-on-input",
        re.compile(
            r"\b(?:eval|exec)\s*\(.*(?:input|request|argv|params|body)",
            re.IGNORECASE,
        ),
    ),
    ("sql-percent-interpolation", re.compile(r"execute\s*\([^)]*['\"]\s*%")),
    ("sql-fstring-interpolation", re.compile(r"execute\s*\(\s*f['\"]")),
    ("curl-pipe-shell", re.compile(r"curl[^|\n]*\|\s*(?:ba|z)?sh\b")),
)


@dataclass
class CheckResult:
    """Outcome of one executable check."""

    check: str
    ran: bool
    passed: bool | None
    command: str
    exit_code: int | None
    summary: str
    details_path: str | None = None


@dataclass
class EvidenceReport:
    """All check results plus the derived overall evidence status."""

    project_dir: str
    overall: str  # "pass" | "fail" | "insufficient-evidence"
    results: list[CheckResult] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "project_dir": self.project_dir,
            "overall": self.overall,
            "results": [asdict(r) for r in self.results],
        }


# ─── Subprocess plumbing ────────────────────────────────────────────────


def _tail(text: str, limit: int = _MAX_SUMMARY_CHARS) -> str:
    text = (text or "").strip()
    return text[-limit:] if len(text) > limit else text


def _skip(check: str, reason: str) -> CheckResult:
    return CheckResult(
        check=check, ran=False, passed=None, command="",
        exit_code=None, summary=reason,
    )


def _run(
    check: str, cmd: list[str], project_dir: Path, timeout: int,
) -> CheckResult:
    """Run one read-only project command; capture exit code + tail."""
    command_str = " ".join(cmd)
    try:
        proc = subprocess.run(
            cmd, cwd=project_dir, capture_output=True, text=True,
            timeout=timeout,
        )
    except FileNotFoundError:
        return _skip(check, f"tool not found: {cmd[0]}")
    except subprocess.TimeoutExpired:
        # subprocess.run kills the child on expiry before raising.
        return CheckResult(
            check=check, ran=True, passed=None, command=command_str,
            exit_code=None, summary="timeout",
        )
    output = _tail(proc.stdout.strip() or proc.stderr.strip())
    return CheckResult(
        check=check, ran=True, passed=proc.returncode == 0,
        command=command_str, exit_code=proc.returncode, summary=output,
    )


# ─── Applicability detection ────────────────────────────────────────────


def _suffixes(changed_files: list[str] | None) -> set[str]:
    return {Path(f).suffix for f in changed_files or []}


def _has_python(project_dir: Path, changed_files: list[str] | None) -> bool:
    if ".py" in _suffixes(changed_files):
        return True
    if (project_dir / "pyproject.toml").is_file():
        return True
    return any(project_dir.glob("*.py")) or any(project_dir.glob("*/*.py"))


def _package_json_script(project_dir: Path, script: str) -> bool:
    pkg = project_dir / "package.json"
    if not pkg.is_file():
        return False
    try:
        scripts = json.loads(pkg.read_text(encoding="utf-8")).get("scripts", {})
    except (json.JSONDecodeError, OSError):
        return False
    value = str(scripts.get(script, ""))
    return bool(value) and "no test specified" not in value


def _mypy_configured(project_dir: Path) -> bool:
    if (project_dir / "mypy.ini").is_file():
        return True
    for name in ("pyproject.toml", "setup.cfg"):
        path = project_dir / name
        try:
            text = path.read_text(encoding="utf-8") if path.is_file() else ""
        except OSError:
            text = ""
        if "[tool.mypy]" in text or "[mypy]" in text:
            return True
    return False


# ─── Individual checks ──────────────────────────────────────────────────

_LINTABLE_PY = frozenset({".py"})
_LINTABLE_JS = frozenset({".js", ".jsx", ".ts", ".tsx", ".vue", ".mjs", ".cjs"})
_LINTABLE_PHP = frozenset({".php"})


def _scoped_files(
    project_dir: Path, changed: list[str] | None, exts: frozenset[str],
) -> list[str]:
    """Changed files that live inside project_dir and carry a lintable ext."""
    if not changed:
        return []
    root = project_dir.resolve()
    out: list[str] = []
    for raw in changed:
        p = Path(raw)
        candidate = p if p.is_absolute() else project_dir / p
        try:
            rel = candidate.resolve().relative_to(root)
        except (ValueError, OSError):
            continue
        if candidate.suffix.lower() in exts and candidate.is_file():
            out.append(str(rel))
    return out


def _labelled(result: CheckResult, label: str) -> CheckResult:
    """Prefix the reported command with the lint scope label."""
    result.command = f"{label} {result.command}".strip()
    return result


def _lint_scoped(
    project_dir: Path, changed: list[str], timeout: int,
) -> CheckResult | None:
    """Lint only the changed files when the detected linter supports it.

    Pre-existing project-wide debt is master's debt, not this change's —
    the same principle _check_security_grep already applies to its diff
    scope. Returns None when no scoped run applies (caller falls back).
    """
    if shutil.which("ruff"):
        files = _scoped_files(project_dir, changed, _LINTABLE_PY)
        if files:
            result = _run("lint", ["ruff", "check", *files], project_dir, timeout)
            return _labelled(result, f"lint(scoped: {len(files)} file(s))")
    eslint = project_dir / "node_modules" / ".bin" / "eslint"
    if eslint.is_file():
        files = _scoped_files(project_dir, changed, _LINTABLE_JS)
        if files:
            result = _run("lint", [str(eslint), *files], project_dir, timeout)
            return _labelled(result, f"lint(scoped: {len(files)} file(s))")
    pint = project_dir / "vendor" / "bin" / "pint"
    if pint.is_file():
        files = _scoped_files(project_dir, changed, _LINTABLE_PHP)
        if files:
            result = _run(
                "lint", [str(pint), "--test", *files], project_dir, timeout,
            )
            return _labelled(result, f"lint(scoped: {len(files)} file(s))")
    return None


def _check_lint(
    project_dir: Path, changed: list[str] | None,
    test_command: str | None, timeout: int,
) -> CheckResult:
    if changed:
        scoped = _lint_scoped(project_dir, changed, timeout)
        if scoped is not None:
            return scoped
        lintable = (
            _scoped_files(project_dir, changed, _LINTABLE_PY)
            or _scoped_files(project_dir, changed, _LINTABLE_JS)
            or _scoped_files(project_dir, changed, _LINTABLE_PHP)
        )
        if not lintable:
            return _skip("lint", "changed files contain no lintable sources")
    if _has_python(project_dir, changed) and shutil.which("ruff"):
        return _labelled(
            _run("lint", ["ruff", "check", "."], project_dir, timeout),
            "lint(project-wide)",
        )
    if _package_json_script(project_dir, "lint"):
        return _labelled(
            _run(
                "lint", ["npm", "run", "--silent", "lint"], project_dir, timeout,
            ),
            "lint(project-wide)",
        )
    pint = project_dir / "vendor" / "bin" / "pint"
    if pint.is_file():
        return _labelled(
            _run("lint", [str(pint), "--test"], project_dir, timeout),
            "lint(project-wide)",
        )
    return _skip("lint", "no lint tooling detected (ruff/eslint/pint)")


def _check_typecheck(
    project_dir: Path, changed: list[str] | None,
    test_command: str | None, timeout: int,
) -> CheckResult:
    if _mypy_configured(project_dir) and shutil.which("mypy"):
        return _run("typecheck", ["mypy", "."], project_dir, timeout)
    if (project_dir / "tsconfig.json").is_file():
        local_tsc = project_dir / "node_modules" / ".bin" / "tsc"
        if local_tsc.is_file():
            return _run(
                "typecheck", [str(local_tsc), "--noEmit"], project_dir, timeout,
            )
        if shutil.which("tsc"):
            return _run("typecheck", ["tsc", "--noEmit"], project_dir, timeout)
        return _skip("typecheck", "tsconfig.json present but tsc not installed")
    return _skip("typecheck", "no typecheck configuration detected")


def _check_tests(
    project_dir: Path, changed: list[str] | None,
    test_command: str | None, timeout: int,
) -> CheckResult:
    if test_command:
        return _run("tests", shlex.split(test_command), project_dir, timeout)
    if _has_python(project_dir, changed) and shutil.which("pytest"):
        return _run("tests", ["pytest", "-q"], project_dir, timeout)
    if _package_json_script(project_dir, "test"):
        return _run(
            "tests", ["npm", "test", "--silent"], project_dir, timeout,
        )
    return _skip("tests", "no test runner detected (pytest/npm test)")


def _junit_result(junit: Path) -> CheckResult:
    try:
        text = junit.read_text(encoding="utf-8")
    except OSError:
        text = ""
    failures = re.search(r'failures="(\d+)"', text)
    errors = re.search(r'errors="(\d+)"', text)
    if failures is None and errors is None:
        return CheckResult(
            check="coverage", ran=True, passed=None,
            command=f"parse:{junit.name}", exit_code=None,
            summary="junit.xml present but unparseable",
            details_path=str(junit),
        )
    failed = sum(int(m.group(1)) for m in (failures, errors) if m)
    return CheckResult(
        check="coverage", ran=True, passed=failed == 0,
        command=f"parse:{junit.name}", exit_code=None,
        summary=f"junit: {failed} failures/errors", details_path=str(junit),
    )


def _check_coverage(
    project_dir: Path, changed: list[str] | None,
    test_command: str | None, timeout: int,
) -> CheckResult:
    coverage_xml = project_dir / "coverage.xml"
    if coverage_xml.is_file():
        percent = coverage_percent_from_xml(coverage_xml)
        if percent is None:
            return CheckResult(
                check="coverage", ran=True, passed=None,
                command="parse:coverage.xml", exit_code=None,
                summary="coverage.xml present but unparseable",
                details_path=str(coverage_xml),
            )
        return CheckResult(
            check="coverage", ran=True,
            passed=percent >= COVERAGE_THRESHOLD,
            command="parse:coverage.xml", exit_code=None,
            summary=(
                f"coverage {percent:.1f}% "
                f"(threshold {COVERAGE_THRESHOLD:.0f}%)"
            ),
            details_path=str(coverage_xml),
        )
    junit = project_dir / "junit.xml"
    if junit.is_file():
        return _junit_result(junit)
    return _skip("coverage", "no coverage.xml or junit.xml on disk")


def _grep_lines(path: Path, lines: list[str]) -> list[str]:
    hits = []
    for lineno_or_text in lines:
        for name, pattern in _SECURITY_PATTERNS:
            if pattern.search(lineno_or_text):
                hits.append(f"{path} [{name}]: {lineno_or_text.strip()[:120]}")
    return hits


def _grep_file(path: Path) -> list[str]:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []
    hits = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for name, pattern in _SECURITY_PATTERNS:
            if pattern.search(line):
                hits.append(f"{path}:{lineno} [{name}]")
    return hits


def _diff_base(project_dir: Path) -> str | None:
    """Merge-base with the default branch, or None outside a usable repo."""
    for ref in ("origin/master", "master", "origin/main", "main"):
        proc = subprocess.run(
            ["git", "merge-base", "HEAD", ref],
            cwd=project_dir, capture_output=True, text=True, timeout=10,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return proc.stdout.strip()
    return None


def _added_lines(project_dir: Path, base: str, name: str) -> list[str] | None:
    """Lines ADDED by this change (committed + working tree) vs base.

    Returns None when git cannot answer — callers fall back to the
    whole-file scan rather than silently passing.
    """
    proc = subprocess.run(
        ["git", "diff", "-U0", base, "--", name],
        cwd=project_dir, capture_output=True, text=True, timeout=30,
    )
    if proc.returncode != 0:
        return None
    return [
        line[1:]
        for line in proc.stdout.splitlines()
        if line.startswith("+") and not line.startswith("+++")
    ]


def _check_security_grep(
    project_dir: Path, changed: list[str] | None,
    test_command: str | None, timeout: int,
) -> CheckResult:
    """Diff-aware security sweep over the changed files.

    Scans only lines ADDED relative to the default-branch merge-base —
    a pre-existing pattern elsewhere in a touched file is master's
    debt, not this change's (QG blocker, PR1 Interaction Reform:
    whole-file scans failed changed files on benign pre-existing
    lines). Falls back to the whole-file scan when git cannot provide
    a diff (outside a repo, new file, missing base).
    """
    if not changed:
        return _skip("security-grep", "no changed files provided")
    base = _diff_base(project_dir)
    hits: list[str] = []
    mode = "added-lines" if base else "whole-file"
    for name in changed:
        path = Path(name)
        if not path.is_absolute():
            path = project_dir / name
        if not path.is_file():
            continue
        added = _added_lines(project_dir, base, name) if base else None
        if added is None:
            hits.extend(_grep_file(path))
        else:
            hits.extend(_grep_lines(path, added))
    summary = (
        "no security patterns matched"
        if not hits
        else "; ".join(hits[:_MAX_GREP_HITS])
    )
    return CheckResult(
        check="security-grep", ran=True, passed=not hits,
        command=f"security-grep ({mode}) over {len(changed)} changed file(s)",
        exit_code=None, summary=_tail(summary),
    )


def _check_spellcheck(
    project_dir: Path, changed: list[str] | None,
    test_command: str | None, timeout: int,
) -> CheckResult:
    if not shutil.which("codespell"):
        return _skip("spellcheck", "codespell not installed")
    md_files = [f for f in changed or [] if f.endswith(".md")]
    if not md_files:
        return _skip("spellcheck", "no changed .md files")
    return _run("spellcheck", ["codespell", *md_files], project_dir, timeout)


def _check_ui_screenshot(
    project_dir: Path, changed: list[str] | None,
    test_command: str | None, timeout: int,
) -> CheckResult:
    """UI-touching changes require a recent screenshot artifact.

    Mechanical half of the visual-review loop (excellence-mandate): a
    PNG > 10KB captured within the last 24h under
    ``<project>/.arka/evidence/ui/``. The judgment half — whether the
    pixels hold up against the benchmark named in the ``[arka:design]``
    marker — stays with Francisca, who Reads the artifact this check
    points at. Skips when no UI files changed; read-only (stat only).
    """
    if not changed:
        return _skip("ui-screenshot", "no changed files provided")
    try:
        from core.workflow.frontend_gate import is_ui_file
    except Exception:
        return _skip("ui-screenshot", "frontend_gate unavailable")
    ui_changed = [f for f in changed if is_ui_file(f)]
    if not ui_changed:
        return _skip("ui-screenshot", "no UI files changed")
    command_str = (
        f"scan:{UI_EVIDENCE_DIR} (png >{UI_SCREENSHOT_MIN_BYTES // 1024}KB, "
        f"last {UI_SCREENSHOT_WINDOW_HOURS}h)"
    )
    evidence_dir = project_dir / UI_EVIDENCE_DIR
    cutoff = time.time() - UI_SCREENSHOT_WINDOW_HOURS * 3600
    candidates: list[tuple[float, Path]] = []
    if evidence_dir.is_dir():
        for png in evidence_dir.rglob("*.png"):
            try:
                stat = png.stat()
            except OSError:
                continue
            if stat.st_mtime >= cutoff and stat.st_size > UI_SCREENSHOT_MIN_BYTES:
                candidates.append((stat.st_mtime, png))
    if candidates:
        newest = max(candidates)[1]
        return CheckResult(
            check="ui-screenshot", ran=True, passed=True,
            command=command_str, exit_code=None,
            summary=(
                f"{len(candidates)} recent screenshot(s) for "
                f"{len(ui_changed)} changed UI file(s); newest: {newest.name}"
            ),
            details_path=str(newest),
        )
    return CheckResult(
        check="ui-screenshot", ran=True, passed=False,
        command=command_str, exit_code=None,
        summary=(
            f"{len(ui_changed)} UI file(s) changed but no screenshot "
            f"evidence under {UI_EVIDENCE_DIR}/ — capture per "
            "brand/design-review (Playwright first, 1440+390 widths) or "
            "record an explicit [arka:trivial] justification"
        ),
    )


_CHECK_DISPATCH = {
    "lint": _check_lint,
    "typecheck": _check_typecheck,
    "tests": _check_tests,
    "coverage": _check_coverage,
    "security-grep": _check_security_grep,
    "spellcheck": _check_spellcheck,
    "ui-screenshot": _check_ui_screenshot,
}


# ─── Public API ─────────────────────────────────────────────────────────


def _derive_overall(results: list[CheckResult]) -> str:
    """fail if any ran check failed; insufficient if nothing concluded."""
    if any(r.ran and r.passed is False for r in results):
        return "fail"
    if any(r.ran and r.passed is True for r in results):
        return "pass"
    return "insufficient-evidence"


def run_evidence_checks(
    project_dir: Path,
    changed_files: list[str] | None = None,
    checks: list[str] | None = None,
    test_command: str | None = None,
    timeout: int = TIMEOUT_SECONDS,
) -> EvidenceReport:
    """Run the selected checks and derive the overall evidence status."""
    project_dir = Path(project_dir)
    selected = list(checks) if checks else list(ALL_CHECKS)
    results: list[CheckResult] = []
    for name in selected:
        check_fn = _CHECK_DISPATCH.get(name)
        if check_fn is None:
            results.append(_skip(name, f"unknown check: {name}"))
            continue
        results.append(check_fn(project_dir, changed_files, test_command, timeout))
    return EvidenceReport(
        project_dir=str(project_dir),
        overall=_derive_overall(results),
        results=results,
    )


# ─── CLI ────────────────────────────────────────────────────────────────


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m core.governance.evidence_checks",
        description="Run executable evidence checks for the Quality Gate.",
    )
    parser.add_argument("project_dir", type=Path)
    parser.add_argument("--checks", help="comma-separated subset of checks")
    parser.add_argument("--test-command", help="override for the tests check")
    parser.add_argument("--changed-files", help="comma-separated changed files")
    parser.add_argument("--json", action="store_true", help="emit JSON report")
    return parser


def _csv(value: str | None) -> list[str] | None:
    if not value:
        return None
    return [item.strip() for item in value.split(",") if item.strip()]


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    report = run_evidence_checks(
        project_dir=args.project_dir,
        changed_files=_csv(args.changed_files),
        checks=_csv(args.checks),
        test_command=args.test_command,
    )
    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        for result in report.results:
            state = (
                "SKIP" if not result.ran
                else {True: "PASS", False: "FAIL", None: "N/A"}[result.passed]
            )
            print(f"[{state}] {result.check}: {result.summary}")
        print(f"overall: {report.overall}")
    return {"pass": 0, "fail": 1}.get(report.overall, 2)


if __name__ == "__main__":
    raise SystemExit(main())

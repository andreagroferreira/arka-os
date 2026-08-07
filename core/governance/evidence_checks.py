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
import configparser
import fnmatch
import importlib.util
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path, PurePosixPath
from xml.etree import ElementTree

from core.governance.qg_digest import evidence_digest
from core.shared.test_evidence import coverage_percent_from_xml

TIMEOUT_SECONDS = 300
COVERAGE_THRESHOLD = 80.0
ALL_CHECKS: tuple[str, ...] = (
    "lint", "typecheck", "tests", "coverage", "security-grep", "spellcheck",
    "ui-screenshot", "design-slop",
)

# ui-screenshot artifact contract (Excellence Reform PR-D3): captures land
# in <project>/.arka/evidence/ui/ per brand/design-review; the check only
# stats files (read-only), it never runs a browser.
UI_EVIDENCE_DIR = Path(".arka") / "evidence" / "ui"
UI_SCREENSHOT_WINDOW_HOURS = 24
UI_SCREENSHOT_MIN_BYTES = 10 * 1024

# design-slop: the deterministic static half of the visual-review loop.
# Shells the external `impeccable` npm CLI (46 anti-pattern rules, no
# LLM) over the CHANGED UI files only — never a whole-tree scan. The
# gate never installs anything (supply-chain: `npx --no-install`).
# Modes via ``governance.designSlop`` in ``~/.arkaos/config.json``:
# off → skip · warn (default) → advisory summary, never fails ·
# hard → `warning` findings fail; `advisory` findings never fail.
DESIGN_SLOP_TIMEOUT = 120
_DESIGN_SLOP_MIN_NODE = (22, 12)


def _design_slop_config_path() -> Path:
    """Resolved at call time so tests can redirect HOME (never baked)."""
    return Path.home() / ".arkaos" / "config.json"


def _design_slop_telemetry_path() -> Path:
    """Resolved at call time so tests can redirect HOME (never baked)."""
    return Path.home() / ".arkaos" / "telemetry" / "design-slop.jsonl"

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

# Sanctioned per-line suppression: `arka:sec-ok(<pattern-id>): <reason>`.
# A line that DEFINES a dangerous pattern — a deny rule, an egress
# scanner signature — necessarily contains the pattern it names, and a
# sweep with no escape valve forces either scanner evasion (splitting
# the literal) or a permanently red gate. The valve is deliberately
# narrow: the id must name the exact matched pattern and the reason
# must be non-empty. The reason is a formality for the record; the
# CONTROL is visibility — every suppression is carried in the
# structured `suppressions` / `suppressed_count` fields of the
# CheckResult (immune to summary truncation), and the string summary
# ends with a `(+N more suppressed)` marker when the listing is capped.
_SEC_OK_RE = re.compile(r"arka:sec-ok\(([a-z0-9-]+)\):\s*(\S.+)")


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
    # security-grep only: the FULL suppression record, structured so it
    # bypasses summary truncation entirely. Empty for other checks and
    # for pre-existing corpus records.
    suppressions: list[str] = field(default_factory=list)
    suppressed_count: int = 0


@dataclass
class EvidenceReport:
    """All check results plus the derived overall evidence status."""

    project_dir: str
    overall: str  # "pass" | "fail" | "insufficient-evidence"
    results: list[CheckResult] = field(default_factory=list)

    def to_dict(self) -> dict:
        payload = {
            "project_dir": self.project_dir,
            "overall": self.overall,
            "results": [asdict(r) for r in self.results],
        }
        # PR-B2: the digest excludes its own key, so recomputing over
        # the embedded dict reproduces it — reviewers can quote it and
        # the aggregate verifies it once PR-B3 wires the check.
        payload["report_digest"] = evidence_digest(payload)
        return payload


# ─── Subprocess plumbing ────────────────────────────────────────────────


def _tail(text: str, limit: int = _MAX_SUMMARY_CHARS) -> str:
    text = (text or "").strip()
    return text[-limit:] if len(text) > limit else text


def _skip(check: str, reason: str) -> CheckResult:
    return CheckResult(
        check=check, ran=False, passed=None, command="",
        exit_code=None, summary=reason,
    )


def _expand_argv(argv: list[str]) -> list[str]:
    """Expand `~` where it means a path; shlex.split leaves it literal.

    argv[0] is always a program path, so both `~/` and `~user` expand
    there. Later tokens expand only in the `~/` form: a bare `~word` is
    far more likely to be a filter expression (`pytest -k ~root`) than a
    home directory, and rewriting it would silently change what runs.
    """
    if not argv:
        return argv
    head = os.path.expanduser(argv[0]) if argv[0].startswith("~") else argv[0]
    tail = [
        os.path.expanduser(tok) if tok.startswith("~/") else tok
        for tok in argv[1:]
    ]
    return [head, *tail]


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
    except OSError as exc:
        # Anything else exec can refuse — a directory, a non-executable
        # file, a broken symlink. The gate must report, never raise: an
        # uncaught error here produces no EvidenceReport at all, which is
        # worse than the silent skip this module works to avoid.
        return CheckResult(
            check=check, ran=True, passed=False, command=command_str,
            exit_code=None, summary=f"cannot execute {cmd[0]}: {exc.strerror}",
        )
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


def _tool_cmd(tool: str, module: str | None = None) -> list[str] | None:
    """Resolve a Python tool: PATH binary, else the interpreter's module.

    Operator machines install ruff/pytest into the ArkaOS venv with no
    PATH binary — keying on shutil.which alone silently downgraded
    Python lint to eslint over installer/*.js, a FALSE GREEN on a
    NON-NEGOTIABLE gate (QG findings, F1-B2/F1-C1 reviews).

    ``module`` covers tools whose import name differs from the command
    (codespell ships ``codespell_lib``); without it the module fallback
    misses and the check skips forever on a venv install.
    """
    if shutil.which(tool):
        return [tool]
    if importlib.util.find_spec(module or tool) is not None:
        return [sys.executable, "-m", module or tool]
    return None


def _ruff_cmd() -> list[str] | None:
    return _tool_cmd("ruff")


def _lint_scoped(
    project_dir: Path, changed: list[str], timeout: int,
) -> CheckResult | None:
    """Lint only the changed files when the detected linter supports it.

    Pre-existing project-wide debt is master's debt, not this change's —
    the same principle _check_security_grep already applies to its diff
    scope. Returns None when no scoped run applies (caller falls back).
    """
    ruff = _ruff_cmd()
    if ruff:
        files = _scoped_files(project_dir, changed, _LINTABLE_PY)
        if files:
            result = _run("lint", [*ruff, "check", *files], project_dir, timeout)
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
    if changed is not None and not changed:
        # A KNOWN-empty diff must not inherit the project-wide baseline:
        # a zero-write deliverable was gated on master's pre-existing
        # ruff debt (QG 2026-08-04). None still means "scope unknown"
        # and keeps the project-wide run.
        return _skip("lint", "no changed files (empty diff)")
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
            # Skipping is only honest when the DIFF has no lintable
            # extensions. When it does but none resolved under
            # project_dir (deleted files, a different checkout/cwd,
            # cross-root paths), "no lintable sources" is a blind gate
            # (QG 2026-07-12: a 2 .py + 6 .js diff got skipped) — fall
            # through to the project-wide lint of what IS on disk.
            all_lintable_exts = _LINTABLE_PY | _LINTABLE_JS | _LINTABLE_PHP
            changed_exts = {s.lower() for s in _suffixes(changed)}
            if not (changed_exts & all_lintable_exts):
                return _skip(
                    "lint", "changed files contain no lintable sources"
                )
    ruff = _ruff_cmd()
    if _has_python(project_dir, changed) and ruff:
        return _labelled(
            _run("lint", [*ruff, "check", "."], project_dir, timeout),
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
    if changed is not None and not changed:
        # Same zero-diff contract as lint: mypy/tsc run project-wide and
        # never read the diff, so a known-empty diff would inherit
        # master's type debt the moment tooling is configured.
        return _skip("typecheck", "no changed files (empty diff)")
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


def _project_pytest(project_dir: Path) -> list[str] | None:
    """pytest belonging to the target project's own environment."""
    for rel in (".venv/bin/pytest", "venv/bin/pytest"):
        candidate = project_dir / rel
        if candidate.is_file():
            return [str(candidate)]
    return None


def _foreign_pytest_can_collect(
    pytest_cmd: list[str], project_dir: Path, timeout: int,
) -> bool:
    """A PATH/venv-foreign pytest must prove it can import the project.

    Running a foreign-env pytest blind produced false FAILs on projects
    whose dependencies live in their own venv (import errors read as
    test failures — issue #283, a blind gate on mandatory-qa). Exit 5
    ("no tests collected") still counts as a working import path.
    """
    try:
        probe = subprocess.run(
            [*pytest_cmd, "--collect-only", "-q"], cwd=project_dir,
            capture_output=True, text=True, timeout=min(timeout, 60),
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return probe.returncode in (0, 5)


def _degrade_pytest_no_tests(result: CheckResult) -> CheckResult:
    """Map pytest exit 5 (no tests collected) to insufficient evidence.

    A bare ``pytest`` in a Python project that ships no tests exits 5.
    Absence of tests is not evidence of FAILURE, yet ``passed =
    returncode == 0`` read exit 5 as FAIL and ``_derive_overall`` then
    forced REJECTED at the QG (issue #354). ``_foreign_pytest_can_collect``
    already treats exit 5 as a valid import path — this keeps that
    precedent for the verdict: exit 5 becomes ``passed=None``
    (non-conclusive), never ``False``.
    """
    if result.exit_code != 5:
        return result
    prefix = "no tests collected (pytest exit 5) — insufficient evidence; "
    return replace(result, passed=None, summary=prefix + result.summary)


def _run_pinned_tests(
    test_command: str, project_dir: Path, timeout: int,
) -> CheckResult:
    """Run the operator's pinned --test-command. Never skips."""
    argv = _expand_argv(shlex.split(test_command))
    result = _run("tests", argv, project_dir, timeout)
    if not result.ran:
        # A command the operator pinned explicitly is not optional.
        # _run reports an unresolvable binary as ran=False, which an
        # aggregator reads as "not applicable" — so a typo in the
        # path would let a PR through on a suite that never ran.
        return CheckResult(
            check="tests", ran=True, passed=False,
            command=" ".join(argv), exit_code=None,
            summary=f"pinned --test-command could not run: {result.summary}",
        )
    # exit 5 is pytest's "no tests collected"; scan the first 3
    # tokens so `python -m pytest` / `arka-py -m pytest` degrade too,
    # while non-pytest runners (npm test) stay a real FAIL. Bounded to
    # argv[:3] so a later test-path arg named *pytest* never matches
    # (issue #354).
    if any("pytest" in Path(tok).name for tok in argv[:3]):
        return _degrade_pytest_no_tests(result)
    return result


def _check_tests(
    project_dir: Path, changed: list[str] | None,
    test_command: str | None, timeout: int,
) -> CheckResult:
    if test_command:
        return _run_pinned_tests(test_command, project_dir, timeout)
    if _has_python(project_dir, changed):
        local_pytest = _project_pytest(project_dir)
        if local_pytest:
            return _labelled(
                _degrade_pytest_no_tests(
                    _run("tests", [*local_pytest, "-q"], project_dir, timeout),
                ),
                "tests(project-venv)",
            )
        pytest_cmd = _tool_cmd("pytest")
        if pytest_cmd and _foreign_pytest_can_collect(
            pytest_cmd, project_dir, timeout
        ):
            return _degrade_pytest_no_tests(
                _run("tests", [*pytest_cmd, "-q"], project_dir, timeout),
            )
        if pytest_cmd:
            return _skip(
                "tests",
                "pytest resolved outside the project env cannot import "
                "it — pin --test-command",
            )
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


def _coverage_from_xml(
    coverage_xml: Path, project_dir: Path, changed: list[str] | None,
) -> CheckResult:
    """Coverage verdict from an artefact, refusing one that cannot describe the diff."""
    stale = _stale_coverage_reason(coverage_xml, project_dir, changed)
    if stale is not None:
        return CheckResult(
            check="coverage", ran=True, passed=False,
            command="parse:coverage.xml", exit_code=None,
            summary=stale, details_path=str(coverage_xml),
        )
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
        summary=f"coverage {percent:.1f}% (threshold {COVERAGE_THRESHOLD:.0f}%)",
        details_path=str(coverage_xml),
    )


def _stale_coverage_reason(
    coverage_xml: Path, project_dir: Path, changed: list[str] | None,
) -> str | None:
    """Reason the artefact cannot describe this diff, or None if it can.

    A coverage.xml older than the newest changed source measured a different
    codebase, and a green number then vouches for code it never executed.
    """
    try:
        artefact_mtime = coverage_xml.stat().st_mtime
    except OSError:
        return "coverage.xml unreadable"

    newest_name = _newest_changed_after(project_dir, changed, artefact_mtime)
    if newest_name is not None:
        return (
            f"coverage.xml predates changed source ({newest_name}) — "
            "regenerate it; it cannot describe this diff"
        )
    return _missing_module_reason(coverage_xml, changed, project_dir)


def _missing_module_reason(
    coverage_xml: Path, changed: list[str] | None, project_dir: Path,
) -> str | None:
    """Reason a changed module is absent from the artefact, or None."""
    covered = _covered_paths(coverage_xml, project_dir)
    missing = [
        rel for rel in (changed or [])
        if rel.endswith(".py")
        and not rel.startswith("tests/")
        and not _is_covered(rel, covered)
    ]
    if not missing:
        return None
    return (
        f"coverage.xml has no entry for {len(missing)} changed module(s), "
        f"first: {missing[0]}"
    )


def _newest_changed_after(
    project_dir: Path, changed: list[str] | None, cutoff: float,
) -> str | None:
    """Name of the newest changed .py file modified after cutoff, else None.

    Only executable source can invalidate a coverage artefact — treating
    CHANGELOG.md as "changed source" forced a full regeneration for edits no
    test could ever execute (same filter the module-presence check applies).
    """
    newest = cutoff
    newest_name: str | None = None
    for rel in changed or []:
        if not rel.endswith(".py"):
            continue
        try:
            mtime = (project_dir / rel).stat().st_mtime
        except OSError:
            continue
        if mtime > newest:
            newest, newest_name = mtime, rel
    return newest_name


def _covered_paths(coverage_xml: Path, project_dir: Path) -> set[str]:
    """Covered files as paths relative to project_dir, exactly.

    A ``class/@filename`` is relative to one of the ``sources/source``
    roots, which are usually absolute and which the changed-file list never
    carries. Each candidate is therefore rebuilt against every source and
    re-expressed relative to the project, so comparison can be equality.

    Suffix or stem matching is not good enough here: `core/` alone carries
    14 colliding stems, this repo's own artefact yields five bare basenames,
    and a suffix rule cannot tell `core/sync/engine.py` from
    `vendor/core/sync/engine.py`. Equality can.
    """
    try:
        root = ElementTree.parse(coverage_xml).getroot()
    except (ElementTree.ParseError, OSError):
        return set()
    sources = [(el.text or "").strip() for el in root.iterfind("sources/source")]
    try:
        base = project_dir.resolve()
    except OSError:
        base = project_dir
    return {
        candidate
        for cls in root.iter("class")
        if cls.get("filename")
        for candidate in _source_candidates(cls.get("filename", ""), sources, base)
    }


def _source_candidates(
    filename: str, sources: list[str], base: Path,
) -> set[str]:
    """Project-relative spellings of one covered file, anchored.

    With ``<source>`` roots declared, every candidate must resolve through
    one of them into the project — the unanchored raw filename let another
    checkout's artefact vouch for this project's files. The raw spelling is
    a fallback only when no sources exist; a relative source resolves
    against the project, never the CWD.
    """
    if not sources:
        raw = PurePosixPath(filename)
        return set() if raw.is_absolute() else {raw.as_posix()}

    # Candidates must exist on disk; existence under more than one source
    # is ambiguous — vouch for neither (fail closed).
    found: set[str] = set()
    for source in sources:
        src = Path(source)
        if not src.is_absolute():
            src = base / src
        try:
            resolved = (src / filename).resolve()
            if not resolved.is_file():
                continue
            found.add(PurePosixPath(resolved.relative_to(base)).as_posix())
        except (OSError, ValueError):
            continue
    return found if len(found) == 1 else set()


def _is_covered(rel: str, covered: set[str]) -> bool:
    """True only when the artefact names exactly this project-relative path."""
    return PurePosixPath(rel).as_posix() in covered


def _check_coverage(
    project_dir: Path, changed: list[str] | None,
    test_command: str | None, timeout: int,
) -> CheckResult:
    coverage_xml = project_dir / "coverage.xml"
    if coverage_xml.is_file():
        return _coverage_from_xml(coverage_xml, project_dir, changed)
    junit = project_dir / "junit.xml"
    if junit.is_file():
        return _junit_result(junit)
    return _skip("coverage", "no coverage.xml or junit.xml on disk")


def _line_matches(line: str) -> tuple[list[str], list[str]]:
    """(flagged, suppressed) pattern names for one line.

    A pattern is suppressed only when the line carries an
    ``arka:sec-ok(<id>): <reason>`` annotation whose id names EXACTLY
    that pattern and whose reason is non-empty. A wrong id, a bare
    annotation, or an empty reason suppresses nothing.
    """
    ok = _SEC_OK_RE.search(line)
    allowed = ok.group(1) if ok else None
    flagged: list[str] = []
    suppressed: list[str] = []
    for name, pattern in _SECURITY_PATTERNS:
        if pattern.search(line):
            (suppressed if name == allowed else flagged).append(name)
    return flagged, suppressed


def _grep_lines(
    path: Path, lines: list[tuple[int, str]]
) -> tuple[list[str], list[str]]:
    hits, suppressed = [], []
    for lineno, text in lines:
        flagged, quiet = _line_matches(text)
        hits.extend(
            f"{path}:{lineno} [{n}]: {text.strip()[:120]}" for n in flagged
        )
        suppressed.extend(f"{path}:{lineno} [{n}]" for n in quiet)
    return hits, suppressed


def _grep_file(path: Path) -> tuple[list[str], list[str]]:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return [], []
    hits, suppressed = [], []
    for lineno, line in enumerate(text.splitlines(), start=1):
        flagged, quiet = _line_matches(line)
        hits.extend(f"{path}:{lineno} [{n}]" for n in flagged)
        suppressed.extend(f"{path}:{lineno} [{n}]" for n in quiet)
    return hits, suppressed


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


_HUNK_HEADER_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")


def _added_lines(
    project_dir: Path, base: str, name: str
) -> list[tuple[int, str]] | None:
    """(line number, text) pairs ADDED by this change vs base.

    Line numbers come from the ``+`` side of the ``-U0`` hunk headers,
    so findings carry a location in both scan modes. Returns None when
    git cannot answer — callers fall back to the whole-file scan
    rather than silently passing.
    """
    proc = subprocess.run(
        ["git", "diff", "-U0", base, "--", name],
        cwd=project_dir, capture_output=True, text=True, timeout=30,
    )
    if proc.returncode != 0:
        return None
    added: list[tuple[int, str]] = []
    lineno = 0
    for line in proc.stdout.splitlines():
        header = _HUNK_HEADER_RE.match(line)
        if header:
            lineno = int(header.group(1))
        elif line.startswith("+") and not line.startswith("+++"):
            added.append((lineno, line[1:]))
            lineno += 1
    return added


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
    hits, suppressed = [], []
    mode = "added-lines" if base else "whole-file"
    for name in changed:
        path = _resolve_changed_file(project_dir, name)
        if path is None:
            continue
        added = _added_lines(project_dir, base, name) if base else None
        found, quiet = (
            _grep_file(path) if added is None else _grep_lines(path, added)
        )
        hits.extend(found)
        suppressed.extend(quiet)
    return CheckResult(
        check="security-grep", ran=True, passed=not hits,
        command=f"security-grep ({mode}) over {len(changed)} changed file(s)",
        exit_code=None, summary=_tail(_grep_summary(hits, suppressed)),
        suppressions=list(suppressed), suppressed_count=len(suppressed),
    )


def _resolve_changed_file(project_dir: Path, name: str) -> Path | None:
    path = Path(name)
    if not path.is_absolute():
        path = project_dir / name
    return path if path.is_file() else None


def _grep_summary(hits: list[str], suppressed: list[str]) -> str:
    """String form of the sweep outcome, capped but never quietly.

    Both listings cap at ``_MAX_GREP_HITS`` with an explicit ``+N
    more`` marker. The suppression record rides at the END of the
    string because ``_tail`` keeps the tail — and the authoritative
    record is the structured ``suppressions`` field, not this string.
    """
    summary = (
        "no security patterns matched"
        if not hits
        else "; ".join(hits[:_MAX_GREP_HITS])
    )
    if len(hits) > _MAX_GREP_HITS:
        summary += f" (+{len(hits) - _MAX_GREP_HITS} more hits)"
    if suppressed:
        summary += (
            f"; suppressed with arka:sec-ok justification: "
            f"{'; '.join(suppressed[:_MAX_GREP_HITS])}"
        )
        if len(suppressed) > _MAX_GREP_HITS:
            summary += f" (+{len(suppressed) - _MAX_GREP_HITS} more suppressed)"
    return summary


def _check_spellcheck(
    project_dir: Path, changed: list[str] | None,
    test_command: str | None, timeout: int,
) -> CheckResult:
    # Resolve like lint/tests do. A bare shutil.which lookup left this check
    # dark on venv installs (the binary is not on the harness PATH), so three
    # consecutive QG rounds shipped with NO machine spellcheck signal.
    cmd = _tool_cmd("codespell", module="codespell_lib")
    if cmd is None:
        return _skip("spellcheck", "codespell not installed")
    md_files = [f for f in changed or [] if f.endswith(".md")]
    if not md_files:
        return _skip("spellcheck", "no changed .md files")
    result = _run("spellcheck", [*cmd, *md_files], project_dir, timeout)
    # codespell honours .codespellrc `skip` even for explicitly listed files,
    # so a PASS here can cover far fewer files than were handed in. Reporting
    # the raw count as coverage is how a narrowed scope reads as a full green
    # (QG finding: 8 of 220 inspected, reported as 220). State both.
    inspected = _spellcheck_inspected_count(project_dir, md_files)
    scope = f"{inspected} of {len(md_files)} changed .md inspected"
    if inspected < len(md_files):
        scope += f"; {len(md_files) - inspected} excluded by .codespellrc skip"
    summary = f"{scope}\n{result.summary}" if result.summary else scope
    return replace(result, summary=summary)


def _spellcheck_inspected_count(project_dir: Path, md_files: list[str]) -> int:
    """How many of ``md_files`` codespell actually reads after `skip`.

    Replays the config's skip globs with fnmatch rather than asking codespell
    itself — per-file ``--count`` probing is too slow, and a skipped file
    simply produces no output, so codespell cannot be asked which files it
    ignored.
    """
    patterns = _codespell_skip_globs(project_dir)
    if not patterns:
        return len(md_files)
    return sum(
        1 for f in md_files
        if not any(fnmatch.fnmatch(f, p) or fnmatch.fnmatch(f"./{f}", p) for p in patterns)
    )


def _codespell_skip_globs(project_dir: Path) -> list[str]:
    """`skip` globs from .codespellrc, or [] when unreadable/absent."""
    cfg = project_dir / ".codespellrc"
    try:
        parser = configparser.ConfigParser()
        parser.read(cfg, encoding="utf-8")
        raw = parser.get("codespell", "skip", fallback="")
    except (OSError, configparser.Error):
        return []
    return [p.strip() for p in raw.split(",") if p.strip()]


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


def _design_slop_mode() -> str:
    """Resolve ``governance.designSlop`` to 'off' | 'warn' | 'hard'."""
    config = _design_slop_config_path()
    if not config.exists():
        return "warn"
    try:
        data = json.loads(config.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return "warn"
    raw = data.get("governance", {}).get("designSlop", "warn")
    if raw in (False, "off", "false"):
        return "off"
    if raw in (True, "hard", "true"):
        return "hard"
    return "warn"


def _resolve_detector(project_dir: Path) -> list[str] | None:
    """Locate the impeccable CLI without ever installing it."""
    direct = shutil.which("impeccable")
    if direct:
        return [direct]
    local = project_dir / "node_modules" / ".bin" / "impeccable"
    if local.is_file():
        return [str(local)]
    if shutil.which("npx"):
        return ["npx", "--no-install", "impeccable"]
    return None


def _node_supports_detector() -> bool:
    """True when `node --version` meets the detector's floor (22.12)."""
    node = shutil.which("node")
    if not node:
        return False
    try:
        proc = subprocess.run(
            [node, "--version"], capture_output=True, text=True, timeout=10,
        )
        major, minor = proc.stdout.strip().lstrip("v").split(".")[:2]
        return (int(major), int(minor)) >= _DESIGN_SLOP_MIN_NODE
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return False


def _record_design_slop(payload: dict) -> None:
    """Best-effort telemetry append; never raises into the gate."""
    try:
        target = _design_slop_telemetry_path()
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"ts": time.time(), **payload}) + "\n")
    except OSError:
        pass


def _design_slop_verdict(
    findings: list[dict], mode: str, n_files: int, command_str: str,
) -> CheckResult:
    """Turn parsed detector findings into the check verdict."""
    warnings = [f for f in findings if f.get("severity") != "advisory"]
    advisories = [f for f in findings if f.get("severity") == "advisory"]
    top = "; ".join(
        f"{f.get('file', '?')}:{f.get('line', '?')} {f.get('antipattern', '?')}"
        for f in (warnings + advisories)[:10]
    )
    counts = (
        f"{len(warnings)} warning(s), {len(advisories)} advisory finding(s)"
    )
    if warnings and mode == "hard":
        summary = f"{counts} across {n_files} changed UI file(s): {top}"
        passed = False
    elif findings:
        # Only warning-severity findings ever fail (and only in hard
        # mode) — never promise a hard failure for advisory-only runs.
        escalation = (
            " — fails when governance.designSlop=hard" if warnings else ""
        )
        summary = (
            f"ADVISORY: {counts} across {n_files} changed UI "
            f"file(s){escalation}: {top}"
        )
        passed = True
    else:
        summary = f"0 findings across {n_files} changed UI file(s)"
        passed = True
    return CheckResult(
        check="design-slop", ran=True, passed=passed,
        command=command_str, exit_code=2 if findings else 0,
        summary=summary[:_MAX_SUMMARY_CHARS],
    )


def _check_design_slop(
    project_dir: Path, changed: list[str] | None,
    test_command: str | None, timeout: int,
) -> CheckResult:
    """Deterministic AI-design-slop detection over changed UI files.

    Composition: ``frontend_gate`` is the pre-edit nudge (PreToolUse),
    this check is the static deterministic half, ``ui-screenshot`` is
    the pixel-artifact half, and Francisca supplies judgment. Fail-open
    by design: a missing detector, an old node, a timeout or unreadable
    output SKIP with a note — the gate never blocks on tooling absence
    and never installs anything.
    """
    mode = _design_slop_mode()
    if mode == "off":
        return _skip("design-slop", "disabled by governance.designSlop flag")
    if not changed:
        return _skip("design-slop", "no changed files provided")
    try:
        from core.workflow.frontend_gate import is_ui_file
    except Exception:
        return _skip("design-slop", "frontend_gate unavailable")
    ui_changed = [
        f for f in changed
        if is_ui_file(f) and (project_dir / f).is_file()
    ]
    if not ui_changed:
        return _skip("design-slop", "no UI files changed")
    detector = _resolve_detector(project_dir)
    if detector is None:
        return _skip(
            "design-slop",
            "impeccable CLI not installed (npm i -D impeccable, or re-run "
            "the ArkaOS installer) — skipped",
        )
    if not _node_supports_detector():
        return _skip("design-slop", "node >= 22.12 required by the detector")
    argv = [*detector, "detect", *ui_changed, "--json"]
    command_str = shlex.join(argv)
    try:
        proc = subprocess.run(
            argv, cwd=project_dir, capture_output=True, text=True,
            timeout=min(timeout, DESIGN_SLOP_TIMEOUT),
        )
    except subprocess.TimeoutExpired:
        return CheckResult(
            check="design-slop", ran=True, passed=None,
            command=command_str, exit_code=None, summary="timeout",
        )
    except (OSError, FileNotFoundError):
        return _skip("design-slop", "detector could not be executed")
    if proc.returncode not in (0, 2):
        tail = (proc.stderr or proc.stdout or "").strip()[-200:]
        return _skip("design-slop", f"detector error (exit {proc.returncode}): {tail}")
    try:
        findings = json.loads(proc.stdout or "[]")
        assert isinstance(findings, list)
    except (json.JSONDecodeError, AssertionError):
        return _skip("design-slop", "unparseable detector output — skipped")
    result = _design_slop_verdict(findings, mode, len(ui_changed), command_str)
    _record_design_slop({
        "project_dir": str(project_dir), "mode": mode,
        "ui_files": len(ui_changed),
        "warnings": sum(1 for f in findings if f.get("severity") != "advisory"),
        "advisories": sum(1 for f in findings if f.get("severity") == "advisory"),
        "outcome": "fail" if result.passed is False else "pass",
    })
    return result


_CHECK_DISPATCH = {
    "lint": _check_lint,
    "typecheck": _check_typecheck,
    "tests": _check_tests,
    "coverage": _check_coverage,
    "security-grep": _check_security_grep,
    "spellcheck": _check_spellcheck,
    "ui-screenshot": _check_ui_screenshot,
    "design-slop": _check_design_slop,
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
    if value is None:
        return None
    # `--changed-files ""` is a KNOWN-empty diff and maps to [] so the
    # zero-diff skip fires; an omitted flag stays None (scope unknown).
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

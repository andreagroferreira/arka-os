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
import tomllib
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path, PurePosixPath
from xml.etree import ElementTree

import core
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


class ProvenanceError(RuntimeError):
    """The engine that would produce the report is not the code under review."""


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
    # The FULL record of findings that DO gate, path-qualified, for the
    # same reason: the summary is capped and truncated at both ends, and
    # a reviewer cannot certify a finding the formatting removed
    # (issue #493). Filled by spellcheck; empty for checks that do not
    # enumerate findings, and for pre-existing corpus records.
    findings: list[str] = field(default_factory=list)
    findings_count: int = 0


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
    return _run_capturing(check, cmd, project_dir, timeout)[0]


def _run_capturing(
    check: str, cmd: list[str], project_dir: Path, timeout: int,
) -> tuple[CheckResult, str]:
    """``_run`` plus the UNTRUNCATED output.

    A caller that must ATTRIBUTE individual findings cannot work from the
    800-char tail: every finding truncated away would read as absent, and
    "absent" is exactly what a gate must never infer from its own
    formatting. The tail stays the reported summary; the full text is for
    analysis only.
    """
    command_str = " ".join(cmd)
    try:
        proc = subprocess.run(
            cmd, cwd=project_dir, capture_output=True, text=True,
            timeout=timeout,
        )
    except FileNotFoundError:
        return _skip(check, f"tool not found: {cmd[0]}"), ""
    except OSError as exc:
        # Anything else exec can refuse — a directory, a non-executable
        # file, a broken symlink. The gate must report, never raise: an
        # uncaught error here produces no EvidenceReport at all, which is
        # worse than the silent skip this module works to avoid.
        return CheckResult(
            check=check, ran=True, passed=False, command=command_str,
            exit_code=None, summary=f"cannot execute {cmd[0]}: {exc.strerror}",
        ), ""
    except subprocess.TimeoutExpired:
        # subprocess.run kills the child on expiry before raising.
        return CheckResult(
            check=check, ran=True, passed=None, command=command_str,
            exit_code=None, summary="timeout",
        ), ""
    full = proc.stdout.strip() or proc.stderr.strip()
    return CheckResult(
        check=check, ran=True, passed=proc.returncode == 0,
        command=command_str, exit_code=proc.returncode, summary=_tail(full),
    ), full


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


def _mypy_declared_scope(project_dir: Path) -> list[str] | None:
    """The project's declared mypy ``files`` roots, or None if undeclared.

    mypy IGNORES the config's ``files`` the moment any path is passed on
    the command line, so a gate that unconditionally appends ``.``
    overrides the very scope the project declared. That is how ``mypy .``
    came to ABORT on this repo before checking a single line — two
    top-level ``server`` modules under mcps/, plus bare script names
    colliding between plugins/ and scripts/ (issue #452).

    The same override bites the SCOPED run, which also passes explicit
    paths: without this list the gate strict-typechecks files the project
    deliberately excludes (measured: a diff touching tests/ produced 351
    errors in a tree `files = ["core", "scripts"]` never covers).
    """
    for name, reader in (
        ("mypy.ini", _ini_declared_files),
        ("setup.cfg", _ini_declared_files),
        ("pyproject.toml", _pyproject_declared_files),
    ):
        declared = reader(project_dir / name)
        if declared:
            return declared
    return None


def _mypy_scope_configured(project_dir: Path) -> bool:
    """True when the project declares its own mypy file scope."""
    return _mypy_declared_scope(project_dir) is not None


def _ini_declared_files(path: Path) -> list[str]:
    """`files = a, b` under an ini-style ``[mypy]`` section."""
    if not path.is_file():
        return []
    parser = configparser.ConfigParser()
    try:
        parser.read(path, encoding="utf-8")
        raw = parser.get("mypy", "files", fallback="")
    except (OSError, configparser.Error):
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def _pyproject_declared_files(path: Path) -> list[str]:
    """`files = [...]` under ``[tool.mypy]`` in pyproject.toml."""
    if not path.is_file():
        return []
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError, UnicodeDecodeError):
        return []
    mypy_cfg = data.get("tool", {}).get("mypy", {})
    if not isinstance(mypy_cfg, dict):
        return []
    declared = mypy_cfg.get("files")
    if isinstance(declared, str):
        declared = [declared]
    if not isinstance(declared, list):
        return []
    return [str(item).strip() for item in declared if str(item).strip()]


def _within_declared_scope(rel: str, declared: list[str] | None) -> bool:
    """True when a project-relative path sits under a declared mypy root."""
    if declared is None:
        return True
    candidate = PurePosixPath(rel)
    for root in declared:
        prefix = PurePosixPath(root.rstrip("/") or ".")
        if prefix == PurePosixPath("."):
            return True
        if candidate == prefix or prefix in candidate.parents:
            return True
    return False


# ─── Individual checks ──────────────────────────────────────────────────

_LINTABLE_PY = frozenset({".py"})
_LINTABLE_JS = frozenset({".js", ".jsx", ".ts", ".tsx", ".vue", ".mjs", ".cjs"})
_LINTABLE_PHP = frozenset({".php"})

# What a configured typechecker could POSSIBLY report on. This answers
# "is the diff relevant to the check at all", NOT "which files does the
# scoped run name on the command line" (that stays `_LINTABLE_PY`).
# Deliberately supersets of the lintable sets — mypy also reads stubs,
# tsc also reads .mts/.cts: membership here only ever decides whether
# the check is SKIPPED, so a missing extension costs the gate its type
# signal while a spurious one costs at most one unnecessary run.
_TYPECHECKABLE_PY: frozenset[str] = _LINTABLE_PY | {".pyi"}
_TYPECHECKABLE_TS: frozenset[str] = _LINTABLE_JS | {".mts", ".cts", ".svelte"}

# Config and manifest files that CHANGE what a typechecker concludes
# without being source themselves. A @types bump in a lockfile-only PR
# is precisely the diff where the project-wide run is the only defence,
# and relevance-by-extension alone silenced it (QG cycle 3, A2).
# Matched against the BASENAME, case-sensitively: these names are
# canonical and lowercase, and a platform-dependent match would make the
# gate behave differently on macOS than on CI.
_MYPY_TRIGGERS: frozenset[str] = frozenset({
    "pyproject.toml", "mypy.ini", ".mypy.ini", "setup.cfg",
    "requirements*.txt", "constraints*.txt",
})
_TSC_TRIGGERS: frozenset[str] = frozenset({
    "tsconfig*.json", "package.json", "package-lock.json",
    "bun.lock", "bun.lockb", "yarn.lock", "pnpm-lock.yaml",
})

# Extensions NO test suite can execute and NO typechecker reads — the
# only ones whose presence alone may silence a check. A DENYLIST by
# construction, and the correction of a real fail-open: the allowlist
# this replaced silenced coverage for every language it had not
# enumerated, so a 42% artefact on a `main.go` diff reported no verdict
# at all instead of FAIL (QG cycle 3, A1). An unrecognised extension
# keeps the check RUNNING — being wrong that way costs one run, being
# wrong the other way manufactures green on a NON-NEGOTIABLE gate.
# Deliberately NOT here: .json/.yaml/.toml/.csv (fixtures and config a
# suite genuinely executes or reads) and every extensionless path
# (Makefile, Dockerfile), which all fail closed.
_INERT_EXTS: frozenset[str] = frozenset({
    ".md", ".markdown", ".rst", ".txt", ".adoc",
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico", ".pdf",
    ".lock",
})


def _diff_is_wholly_inert(changed: list[str] | None) -> bool:
    """True only when EVERY changed file is documentation or an asset.

    The question a coverage artefact must answer is "could the suite
    have executed anything in this diff", and the only defensible
    answer from a filename is "no" for a closed set of formats nothing
    executes. One unrecognised extension in the list — `.go`, `.rb`,
    `.java`, `.sh`, or a name with no suffix at all — makes the whole
    diff non-inert and the check runs.

    ``None`` (scope unknown) and ``[]`` are never inert: the first is a
    guess the gate must not make, the second has its own skip upstream
    with its own wording.
    """
    if not changed:
        return False
    return all(Path(raw).suffix.lower() in _INERT_EXTS for raw in changed)


def _diff_triggers(changed: list[str] | None, patterns: frozenset[str]) -> bool:
    """True when a changed file's basename matches a config/manifest pattern.

    ``fnmatchcase`` (not ``fnmatch``) because ``fnmatch`` normalises case
    per-platform, which would make the gate's verdict depend on the
    filesystem it runs on. A generic ``src/data.json`` is deliberately
    NOT a trigger — it is a fixture, not a manifest, and treating every
    .json as one would re-run the project-wide typechecker on ordinary
    data edits.
    """
    if not changed:
        return False
    return any(
        fnmatch.fnmatchcase(PurePosixPath(raw).name, pattern)
        for raw in changed
        for pattern in patterns
    )


def _diff_touches(changed: list[str] | None, exts: frozenset[str]) -> bool:
    """True when the changed list names at least one file with one of ``exts``.

    Reads the RAW list, never ``_scoped_files``' resolved one. An empty
    resolved list conflates two different facts: "the diff carries none
    of these files" and "it carries them but they did not resolve under
    project_dir" (deleted paths, a foreign checkout, a different cwd).
    Only the first may skip a check; the second must keep whatever
    fallback the caller has — the same distinction ``_check_lint``
    already draws for its own blind spot.

    ``None`` means the caller does not know the diff, and no check is
    ever skipped on a guess, so it answers True.
    """
    if changed is None:
        return True
    return bool({s.lower() for s in _suffixes(changed)} & exts)


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


def _eslint_root(project_dir: Path, rel: str) -> Path | None:
    """Nearest ancestor of ``rel``, up to project_dir, with a local eslint.

    A monorepo keeps its parser and plugins in the sub-package that owns
    the files, so resolving eslint only at ``project_dir`` lints the whole
    diff with the WRONG config. Reproduced on this repo: the root eslint
    over ``dashboard/app/composables/useApi.ts`` reports
    ``Parsing error: Unexpected token`` (no TypeScript parser) while
    ``dashboard``'s own eslint exits 0 over the same file (QG Fase 1).

    That is a permanent false FAIL today and a false GREEN tomorrow: a
    parser that cannot parse a file evaluates ZERO rules over it, so the
    day the root config gains one, a whole tree passes on nothing.
    """
    try:
        root = project_dir.resolve()
        current = (root / rel).resolve().parent
    except OSError:
        return None
    while True:
        if (current / "node_modules" / ".bin" / "eslint").is_file():
            return current
        if current == root or current.parent == current:
            return None
        current = current.parent


def _merge_scoped_lint(
    results: list[tuple[str, CheckResult]], total: int, orphans: list[str],
) -> CheckResult:
    """Fold per-root eslint runs into one honest CheckResult.

    FAILS if any root failed; stays non-conclusive when a root could not
    conclude and none failed. Files with no eslint anywhere above them are
    NAMED, last, so the note survives ``_tail`` truncation — a silently
    unlinted file is the same blind gate this fix exists to close.
    """
    if any(r.passed is False for _, r in results):
        passed: bool | None = False
    elif any(r.passed is None for _, r in results):
        passed = None
    else:
        passed = True
    exit_code = next(
        (r.exit_code for _, r in results if r.exit_code not in (None, 0)), 0,
    )
    sections = [
        f"[{label}] {r.summary or 'no output'}" for label, r in results
    ]
    if orphans:
        sections.append(
            f"NOT LINTED — no eslint above {len(orphans)} changed file(s): "
            + ", ".join(orphans[:5])
        )
    command = " && ".join(f"(cd {label} && {r.command})" for label, r in results)
    return CheckResult(
        check="lint", ran=any(r.ran for _, r in results), passed=passed,
        command=(
            f"lint(scoped: {total - len(orphans)} file(s) across "
            f"{len(results)} eslint root(s)) {command}"
        ),
        exit_code=exit_code, summary=_tail("\n".join(sections)),
    )


def _lint_eslint_grouped(
    project_dir: Path, changed: list[str], timeout: int,
) -> CheckResult | None:
    """One eslint run per OWNING package root, never one run for all.

    Returns None when no changed JS/TS file has an eslint above it, so
    the caller falls through to the project-wide path unchanged.
    """
    files = _scoped_files(project_dir, changed, _LINTABLE_JS)
    if not files:
        return None
    root = project_dir.resolve()
    groups: dict[Path, list[str]] = {}
    orphans: list[str] = []
    for rel in files:
        owner = _eslint_root(project_dir, rel)
        if owner is None:
            orphans.append(rel)
        else:
            groups.setdefault(owner, []).append(rel)
    if not groups:
        return None
    results: list[tuple[str, CheckResult]] = []
    for owner in sorted(groups):
        eslint = owner / "node_modules" / ".bin" / "eslint"
        # Paths are re-expressed against the owning root because that is
        # the cwd eslint runs in — its config resolution, ignore files and
        # plugin lookup all key off it.
        local = [
            PurePosixPath((root / rel).resolve().relative_to(owner)).as_posix()
            for rel in groups[owner]
        ]
        label = (
            "." if owner == root
            else PurePosixPath(owner.relative_to(root)).as_posix()
        )
        results.append(
            (label, _run("lint", [str(eslint), *local], owner, timeout))
        )
    return _merge_scoped_lint(results, len(files), orphans)


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
    grouped = _lint_eslint_grouped(project_dir, changed, timeout)
    if grouped is not None:
        return grouped
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


_MYPY_ABORT_MARKER = "errors prevented further checking"


def _mypy_verdict(result: CheckResult) -> CheckResult:
    """Never let a mypy ABORT read as an ordinary type-error failure.

    A blocking error (duplicate module names, an unparseable followed
    stub, a bad invocation) makes mypy stop after checking only PART of
    the tree, yet the exit code is indistinguishable from a completed run
    that found errors. Reporting that as a plain FAIL hides the real
    problem — the checker never finished — and a reviewer reading
    "N errors" reasonably assumes N is the whole truth. Stays
    ``ran=True, passed=False``; only the reason is made honest.
    """
    if result.exit_code in (None, 0):
        return result
    text = result.summary or ""
    if _MYPY_ABORT_MARKER not in text:
        return result
    blocking = [ln.strip() for ln in text.splitlines() if ": error:" in ln]
    prefix = (
        "mypy ABORTED before checking every file — the count below is a "
        "LOWER BOUND, not a complete typecheck"
    )
    if blocking:
        prefix += f"; blocking: {blocking[-1]}"
    return replace(result, passed=False, summary=f"{prefix}\n{text}")


_MYPY_FOUND_RE = re.compile(r"Found \d+ errors? in \d+ files?[^\n]*")


def _mypy_project_argv(project_dir: Path, mypy: list[str]) -> list[str]:
    """Project-wide invocation, honouring a config-declared ``files`` scope."""
    return list(mypy) if _mypy_scope_configured(project_dir) else [*mypy, "."]


def _project_wide_advisory(
    project_dir: Path, mypy: list[str], timeout: int,
) -> str:
    """Master's accumulated count, carried as an explicitly NON-GATING note.

    Scoping the verdict to the diff must not make the accumulated debt
    invisible: a number nobody sees is a number nobody ever cleans. It
    rides at the END of the summary because ``_tail`` keeps the tail.
    """
    result = _run(
        "typecheck", _mypy_project_argv(project_dir, mypy), project_dir, timeout,
    )
    prefix = (
        "typecheck (project-wide over the working tree, including this "
        "diff; advisory, NOT gating): "
    )
    if not result.ran:
        return ""
    if result.exit_code == 0:
        return prefix + "clean"
    if result.passed is None:
        return prefix + "did not finish (timeout)"
    found = _MYPY_FOUND_RE.search(result.summary or "")
    if found is None:
        return prefix + f"could not be summarised (exit {result.exit_code})"
    return f"{prefix}{found.group(0)} — master's debt, not this diff's"


_MYPY_ERROR_RE = re.compile(
    r"^(?P<path>[^\s:][^:]*):(?P<line>\d+):(?:\d+:)?\s*error:\s*(?P<msg>.*)$"
)


def _git_tracks(project_dir: Path, name: str) -> bool:
    """True when git has ``name`` in the index."""
    try:
        proc = subprocess.run(
            ["git", "ls-files", "--error-unmatch", "--", name],
            cwd=project_dir, capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return proc.returncode == 0


def _added_line_numbers(
    project_dir: Path, base: str, name: str,
) -> set[int] | None:
    """Line numbers this diff ADDED to ``name``; None when git cannot say.

    An UNTRACKED file is entirely new, so every line in it is added — but
    ``git diff`` reports nothing at all for such a path (exit 0, empty
    output). Reading that silence as "no added lines" would file every
    error in a brand-new module under master's debt, and a whole new
    type-broken file would gate GREEN. Caught by
    ``test_an_untrackable_file_fails_closed``.
    """
    if not _git_tracks(project_dir, name):
        return None
    added = _added_lines(project_dir, base, name)
    if added is None:
        return None
    return {lineno for lineno, _ in added}


def _attribute_hits(
    project_dir: Path, output: str, pattern: re.Pattern[str],
) -> tuple[list[str], list[str], list[str]] | None:
    """Split ``file:line:``-shaped tool output by provenance.

    Returns ``(gating, inherited, unattributable_paths)``. The third
    element exists so a caller can say WHY a finding gates: an
    unattributable one gates by fail-closed policy, not because git
    placed it on an added line, and a summary that claims the latter is
    asserting something no tool verified.

    THE attribution engine of this module, shared by every check whose
    findings arrive as another tool's stdout (mypy, codespell). The
    line-scanning checks (``security-grep``) reach the same contract from
    the other side, by scanning only the added lines to begin with.
    Keeping one implementation is what stops the fail-closed rule below
    from drifting between copies.

    ``pattern`` must expose ``path`` and ``line`` groups.

    Returns None when no merge-base exists — attribution is then
    impossible and the caller must gate on everything.
    """
    base = _diff_base(project_dir)
    if base is None:
        return None
    added_by_file: dict[str, set[int] | None] = {}
    gating: list[str] = []
    inherited: list[str] = []
    unattributable: list[str] = []
    for raw in output.splitlines():
        match = pattern.match(raw.strip())
        if match is None:
            continue
        path, lineno = match.group("path"), int(match.group("line"))
        if path not in added_by_file:
            added_by_file[path] = _added_line_numbers(project_dir, base, path)
            if added_by_file[path] is None:
                unattributable.append(path)
        added = added_by_file[path]
        # git could not describe this file (brand-new path, a rename, a
        # sparse checkout, a path outside this repo entirely) — fail
        # CLOSED: an unattributable finding gates.
        if added is None or lineno in added:
            gating.append(raw.strip())
        else:
            inherited.append(raw.strip())
    return gating, inherited, unattributable


def _attribute_mypy_errors(
    project_dir: Path, output: str,
) -> tuple[list[str], list[str]] | None:
    """Split mypy errors into (on ADDED lines, pre-existing in touched files).

    Same machinery and same contract as ``_check_security_grep``: only
    lines ADDED relative to the default-branch merge-base belong to this
    change; a finding elsewhere in a touched file is master's debt. File
    granularity was not enough — it rejected a branch whose measured type
    debt delta was exactly zero.

    KNOWN IMPRECISION, accepted deliberately: mypy reports the line of the
    ERROR, which is not always the added line that CAUSED it — change a
    signature and the error surfaces at an untouched caller. That
    mis-attribution (both ways) is the same one the security sweep has
    always accepted; resolving cause across lines would need dataflow the
    gate has no business doing. Only the three fail-closed paths (no
    merge-base, undiffable path, untracked file) bias deliberately toward
    the diff; elsewhere the direction is unknowable, and the
    not-on-added-lines count below keeps the remainder visible either way.

    Returns None when no merge-base exists — attribution is then
    impossible and the caller must gate on everything.
    """
    attribution = _attribute_hits(project_dir, output, _MYPY_ERROR_RE)
    # The (gating, inherited) contract this function has always published
    # is preserved verbatim; the engine's third element is for callers
    # that report WHY a finding gates.
    return None if attribution is None else attribution[:2]


def _attributed_verdict(
    result: CheckResult, gating: list[str], inherited: list[str],
) -> CheckResult:
    """Rebuild the verdict from errors this diff actually introduced."""
    if gating:
        shown = "\n".join(gating[:_MAX_GREP_HITS])
        if len(gating) > _MAX_GREP_HITS:
            shown += f"\n(+{len(gating) - _MAX_GREP_HITS} more on added lines)"
        summary = f"{len(gating)} type error(s) on lines this diff added:\n{shown}"
    else:
        summary = "no type errors on lines this diff added"
    if inherited:
        summary += (
            f"\n{len(inherited)} strict error(s) on lines this diff did "
            "not add — NOT gating; line position, not provenance"
        )
    return replace(result, passed=not gating, summary=summary)


def _typecheck_scoped(
    project_dir: Path, mypy: list[str], changed: list[str] | None, timeout: int,
) -> CheckResult | None:
    """Typecheck the DIFF, not the accumulated tree.

    The same principle ``_lint_scoped`` already applies: pre-existing
    project-wide debt is master's debt, not this change's. Measured on this
    repo, project-wide mypy reports 1246 errors in 192 files — a verdict
    that would REJECT every deliverable regardless of its own quality, and
    a permanently red gate is one reviewers learn to ignore.

    ``--follow-imports=silent`` keeps the full import graph for inference
    (so types resolve correctly) while reporting only on the named files.

    Returns None when scoping could not BUILD a file list — the diff's
    Python paths did not resolve under project_dir (deleted, renamed, a
    foreign checkout) — and the caller then falls back to the
    project-wide run, which is the only remaining signal. A diff with no
    Python in it at all never reaches here: ``_check_typecheck`` skips
    that case outright (issue #491).
    """
    # _TYPECHECKABLE_PY, not _LINTABLE_PY: a stub is mypy's own file
    # type, and scoping that excluded .pyi let a stub-only diff fall
    # through to the project-wide run it had just been cleared of
    # (QG cycle 3, M1). The relevance guard and the scoped run must
    # answer with the SAME set or the gap reopens between them.
    files = _scoped_files(project_dir, changed, _TYPECHECKABLE_PY)
    if not files:
        return None
    declared = _mypy_declared_scope(project_dir)
    in_scope = [f for f in files if _within_declared_scope(f, declared)]
    advisory = _project_wide_advisory(project_dir, mypy, timeout)
    excluded = len(files) - len(in_scope)
    if not in_scope:
        # Every changed .py sits outside the project's declared scope.
        # Falling through to the project-wide run would gate this diff on
        # master's whole accumulated debt, which is the opposite of the
        # point; the advisory still carries that number.
        return _skip(
            "typecheck",
            f"{excluded} changed Python file(s) all outside the project's "
            f"declared mypy scope ({', '.join(declared or [])})"
            + (f"\n{advisory}" if advisory else ""),
        )
    raw_result, full_output = _run_capturing(
        "typecheck", [*mypy, "--follow-imports=silent", *in_scope],
        project_dir, timeout,
    )
    result = _mypy_verdict(raw_result)
    notes = [advisory] if advisory else []
    # Attribute only a run that COMPLETED with type errors. An abort (or a
    # timeout, or a usage error) means the checker never finished, and an
    # empty gating list would then be an artefact of not looking.
    if result.exit_code == 1 and _MYPY_ABORT_MARKER not in full_output:
        attribution = _attribute_mypy_errors(project_dir, full_output)
        if attribution is None:
            notes.append(
                "no merge-base with the default branch — errors could not "
                "be attributed to added lines; ALL of them gate"
            )
        else:
            result = _attributed_verdict(result, *attribution)
    if excluded:
        notes.append(
            f"{excluded} changed Python file(s) skipped — outside the "
            f"project's declared mypy scope ({', '.join(declared or [])})"
        )
    if notes:
        result = replace(
            result, summary="\n".join([result.summary, *notes]).strip(),
        )
    return _labelled(result, f"typecheck(scoped: {len(in_scope)} file(s))")


def _typecheck_mypy(
    project_dir: Path, changed: list[str] | None, timeout: int,
) -> CheckResult:
    """Scoped mypy over the diff; project-wide only as a documented fallback.

    Reaching here means the diff DID carry Python (or its scope is
    unknown), so a None from ``_typecheck_scoped`` can only mean scoping
    failed to build the file list, and the project-wide run is the only
    remaining signal. The asymmetry with the zero-Python case — which
    skips instead — is deliberate: one is "we could not look here", the
    other is "there was never anything to look at".
    """
    # `shutil.which` alone read a venv-installed mypy as "no typecheck
    # configuration detected" — the generic skip, on a project that had
    # explicitly opted in. `_tool_cmd` is the same resolver ruff/pytest/
    # codespell already use, and its docstring names this exact class of
    # bug: a FALSE GREEN on a NON-NEGOTIABLE gate (issue #452).
    mypy = _tool_cmd("mypy")
    if mypy is None:
        return _skip(
            "typecheck",
            "mypy configured but not installed — install it "
            "(pip install mypy) or drop the mypy config; the gate has "
            "NO type signal for this run",
        )
    scoped = _typecheck_scoped(project_dir, mypy, changed, timeout)
    if scoped is not None:
        return scoped
    return _mypy_verdict(
        _run(
            "typecheck", _mypy_project_argv(project_dir, mypy),
            project_dir, timeout,
        )
    )


def _typecheck_tsc(project_dir: Path, timeout: int) -> CheckResult:
    """tsc over the project — it cannot be scoped to a file list.

    Naming files on the tsc command line DISCARDS the tsconfig ``include``
    that defines the compilation (the same override that bites mypy's
    ``files``), so the honest choice is the whole project or nothing.
    """
    local_tsc = project_dir / "node_modules" / ".bin" / "tsc"
    if local_tsc.is_file():
        return _run(
            "typecheck", [str(local_tsc), "--noEmit"], project_dir, timeout,
        )
    if shutil.which("tsc"):
        return _run("typecheck", ["tsc", "--noEmit"], project_dir, timeout)
    return _skip("typecheck", "tsconfig.json present but tsc not installed")


def _typecheck_relevant(
    changed: list[str] | None, exts: frozenset[str], triggers: frozenset[str],
) -> bool:
    """True when this diff could change what the typechecker concludes.

    Two independent ways in: the diff carries source the tool reads, OR
    it touches the config/manifest that defines the tool's world. The
    second was missing and cost the gate its only defence on
    lockfile-only PRs (QG cycle 3, A2).
    """
    return _diff_touches(changed, exts) or _diff_triggers(changed, triggers)


def _no_relevant_typechecker(mypy_on: bool, tsc_on: bool) -> str:
    """Skip reason that NAMES the tools, so 'no signal' never reads as 'clean'."""
    tools = " + ".join(
        name for name, on in (("mypy", mypy_on), ("tsc", tsc_on)) if on
    )
    return (
        "changed files contain no typecheckable sources for the "
        f"configured typechecker(s) ({tools})"
    )


def _check_typecheck(
    project_dir: Path, changed: list[str] | None,
    test_command: str | None, timeout: int,
) -> CheckResult:
    if changed is not None and not changed:
        # Same zero-diff contract as lint: mypy/tsc run project-wide and
        # never read the diff, so a known-empty diff would inherit
        # master's type debt the moment tooling is configured.
        return _skip("typecheck", "no changed files (empty diff)")
    mypy_on = _mypy_configured(project_dir)
    tsc_on = (project_dir / "tsconfig.json").is_file()
    # Relevance is decided per typechecker, BEFORE any tool runs. A diff
    # with no Python used to reach the project-wide mypy fallback: 1246
    # errors across 192 untouched files charged to a markdown-only
    # changeset, `overall: fail`, and the evidence floor then REJECTED
    # every docs-only deliverable in the campaign (issue #491). Lint has
    # skipped this case since QG 2026-07-12; typecheck did not, because
    # `_typecheck_scoped` returns None for BOTH "no Python in the diff"
    # and "the Python paths did not resolve" — only the first may skip.
    # Per-typechecker, not one global guard, so a TS-only diff in a
    # hybrid repo reaches tsc instead of being charged mypy's debt.
    if mypy_on and _typecheck_relevant(
        changed, _TYPECHECKABLE_PY, _MYPY_TRIGGERS
    ):
        return _typecheck_mypy(project_dir, changed, timeout)
    if tsc_on and _typecheck_relevant(
        changed, _TYPECHECKABLE_TS, _TSC_TRIGGERS
    ):
        return _typecheck_tsc(project_dir, timeout)
    if mypy_on or tsc_on:
        return _skip("typecheck", _no_relevant_typechecker(mypy_on, tsc_on))
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
    if changed is not None and not changed:
        # Its own fact and its own sentence: there are no changed files
        # at all, which is not the same as changed files nothing can
        # execute. The shared wording was factually wrong here
        # (QG cycle 3, M2) and matches lint/typecheck's zero-diff skip.
        return _skip("coverage", "no changed files (empty diff)")
    if _diff_is_wholly_inert(changed):
        # No test can execute a markdown file, so NO artefact — fresh or
        # six hours stale — describes this changeset. The engine reported
        # PASS 83.3% on a docs-only diff and the reviewer had to write
        # "carries no evidential weight" in prose beside it (issue #491,
        # QG cycle 2); a number that needs a human footnote to be read
        # correctly must not be emitted as evidence at all. Not a FAIL:
        # nothing is wrong with the change, there is nothing to measure.
        # Everything else — including languages this module cannot name —
        # falls through to the artefact, where the staleness and
        # module-presence checks give an honest PASS or FAIL.
        return _skip(
            "coverage",
            "every changed file is documentation or an asset — a coverage "
            "artefact cannot describe this diff",
        )
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


# codespell prints `path:line: wrong ==> right`, one finding per line.
_CODESPELL_HIT_RE = re.compile(
    r"^(?P<path>[^\s:][^:]*):(?P<line>\d+):\s*(?P<msg>.*)$"
)

def _hit_lines(output: str) -> list[str]:
    """Every codespell finding in ``output``, one stripped raw line each."""
    return [
        stripped for stripped in (line.strip() for line in output.splitlines())
        if _CODESPELL_HIT_RE.match(stripped)
    ]


@dataclass(frozen=True)
class _SpellHits:
    """Every codespell hit of one run, bucketed by what may gate on it.

    Correlated lists that are always built and read together; a
    parameter object keeps the verdict a function of ONE value rather
    than of four positional arguments nobody can order correctly twice.
    """

    gating: list[str]
    inherited: list[str]
    unattributable: list[str]
    attributed: bool = True


def _spellcheck_gating_note(hits: _SpellHits) -> str:
    """The headline verdict, capped but pointing at the complete record."""
    if not hits.gating:
        return "no misspellings on lines this diff added"
    shown = "\n".join(hits.gating[:_MAX_GREP_HITS])
    if len(hits.gating) > _MAX_GREP_HITS:
        shown += (
            f"\n(+{len(hits.gating) - _MAX_GREP_HITS} more; the complete "
            "path-qualified list is in CheckResult.findings)"
        )
    return f"{len(hits.gating)} gating misspelling(s):\n{shown}"


def _spellcheck_policy_notes(hits: _SpellHits) -> str:
    """Every non-gating outcome, each named for what it actually is.

    Three different things stop a hit from gating and only one of them
    is "this diff did not write it". Collapsing them into one line would
    launder policy decisions into findings, so each keeps its own
    sentence.
    """
    notes: list[str] = []
    if not hits.attributed:
        notes.append(
            "no merge-base with the default branch — hits could not be "
            "attributed to added lines; ALL of them gate"
        )
    if hits.unattributable:
        listed = ", ".join(sorted(hits.unattributable)[:3])
        notes.append(
            f"git could not describe {len(hits.unattributable)} of the changed "
            f"file(s) ({listed}) — untracked, renamed, or outside this "
            "repository. Their hits gate as UNATTRIBUTED, not as proven "
            "additions."
        )
    if hits.inherited:
        notes.append(
            f"{len(hits.inherited)} misspelling(s) on lines this diff did not "
            "add — NOT gating; pre-existing text in a touched file"
        )
    return "\n".join(notes)


def _spellcheck_verdict(result: CheckResult, hits: _SpellHits) -> CheckResult:
    """Rebuild the verdict from the misspellings that may actually gate.

    Two different reasons put a hit in ``gating`` — git placed it on an
    added line, or git could not describe the file at all — and only the
    first is a statement about this diff. Reporting both as "on lines
    this diff added" would make the gate assert a provenance nothing
    verified, so the fail-closed share is named separately.

    The complete gating list is filled into the structured ``findings``
    field rather than left to the summary string: the string is capped
    at ``_MAX_GREP_HITS`` and truncated at both ends downstream
    (``_tail`` cuts the head, ``stop_lint`` cuts the tail), and a
    reviewer cannot certify a finding the formatting removed.
    """
    summary = "\n".join(
        part for part in
        (_spellcheck_gating_note(hits), _spellcheck_policy_notes(hits))
        if part
    )
    return replace(
        result, passed=not hits.gating, summary=summary,
        findings=list(hits.gating), findings_count=len(hits.gating),
    )


def _spellcheck_attributed(
    project_dir: Path, result: CheckResult, output: str,
) -> CheckResult:
    """Scope a codespell run to the lines this diff ADDED.

    The third check in this module to need the same contract, and the
    reason it is a shared engine rather than a third implementation: a
    hit on an untouched line of a touched file is master's text, not
    this change's. Measured cost of the whole-file scan: a docs
    deliverable whose own generated output was clean was gated by 5
    hits, all outside the edited regions and all present verbatim in the
    pre-5.10.0 baseline (issue #498).

    Only a run that CONCLUDED with findings is attributed, and only
    findings this parser recognised are re-adjudicated. A clean run, a
    timeout, or output whose shape the hit pattern does not describe
    keeps codespell's own verdict — an empty gating list must never be
    an artefact of our failure to parse.
    """
    if result.exit_code in (None, 0):
        return result
    parsed = _hit_lines(output)
    if not parsed:
        return result
    attribution = _attribute_hits(project_dir, output, _CODESPELL_HIT_RE)
    if attribution is None:
        return _spellcheck_verdict(result, _SpellHits(
            gating=parsed, inherited=[], unattributable=[], attributed=False,
        ))
    gating, inherited, unattributable = attribution
    return _spellcheck_verdict(
        result, _SpellHits(gating, inherited, unattributable),
    )


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
    # UNTRUNCATED output, for the same reason the typecheck path takes it:
    # a hit truncated away by `_tail` would read as absent, and "absent" is
    # what a gate must never infer from its own formatting.
    raw_result, full_output = _run_capturing(
        "spellcheck", [*cmd, *md_files], project_dir, timeout,
    )
    result = _spellcheck_attributed(project_dir, raw_result, full_output)
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


def _assert_provenance(project_dir: Path) -> None:
    """Refuse to gate an ArkaOS checkout with a DIFFERENT copy of the engine.

    The ArkaOS venv carries an editable ``.pth`` that points at the npx
    install cache, so ``import core`` resolves by CWD: run the gate from
    anywhere but the repo and it loads the PUBLISHED copy while reporting
    on the working tree (issue #453 — reproduced: v5.11.0 from
    ``~/.npm/_npx/.../arkaos/core`` against a v5.13.0 checkout). A verdict
    derived from code the reviewer never saw is a provenance break on a
    NON-NEGOTIABLE gate, not a warning — so it kills the whole run rather
    than emitting a report that looks exactly like a trustworthy one.

    Fires ONLY when ``project_dir`` is itself an engine checkout. Gating a
    CLIENT project legitimately runs ArkaOS's core from somewhere else,
    and refusing that would break every cross-project QG.
    """
    try:
        target = Path(project_dir).resolve()
        engine = Path(core.__file__).resolve().parent
    except (OSError, TypeError, ValueError):
        return
    if not (target / "core" / "governance" / "evidence_checks.py").is_file():
        return  # foreign project — the engine is expected to live elsewhere
    try:
        expected = (target / "core").resolve()
    except OSError:
        return
    if engine == expected:
        return
    raise ProvenanceError(
        "evidence gate provenance mismatch — the report would describe "
        f"code that was never loaded.\n  project under review: {target}\n"
        f"  engine actually imported: {engine}\n"
        f"Re-run from {target} (or with PYTHONPATH={target}) so the gate "
        "and the diff are the same code."
    )


def run_evidence_checks(
    project_dir: Path,
    changed_files: list[str] | None = None,
    checks: list[str] | None = None,
    test_command: str | None = None,
    timeout: int = TIMEOUT_SECONDS,
) -> EvidenceReport:
    """Run the selected checks and derive the overall evidence status.

    Raises ``ProvenanceError`` before running anything when the imported
    engine is not the checkout being gated (see ``_assert_provenance``).
    """
    _assert_provenance(project_dir)
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
    try:
        report = run_evidence_checks(
            project_dir=args.project_dir,
            changed_files=_csv(args.changed_files),
            checks=_csv(args.checks),
            test_command=args.test_command,
        )
    except ProvenanceError as exc:
        # Loud and unmissable, on stderr, with NO report on stdout: a
        # caller that pipes --json must get nothing to interpret rather
        # than a plausible-looking verdict from the wrong engine.
        print(f"[PROVENANCE-FAIL] {exc}", file=sys.stderr)
        return 3
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

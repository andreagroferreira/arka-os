"""Workflow enforcement rules registry — disk-verifiable rules only.

Only rules whose state CAN be read from disk (or from the operation
being evaluated) live here; behavioral rules (human-writing,
squad-routing, full-visibility, context-verification, ...) are enforced
by hooks/telemetry, not by this in-process registry.

History (structural honesty PR-2): this registry once narrated 14
NON-NEGOTIABLE rules, but every check trusted caller-supplied booleans
(`tests_run`, `spec_status`, `claude_md_read`, ...) — self-reported
state that made enforcement theater, not enforcement. Rules that could
not be verified from disk were deleted, not stubbed. The three rules
that remain read real state:

  - branch-isolation: reads the current branch from git (read-only)
  - spec-driven:      checks an approved spec file exists on disk
  - mandatory-qa:     checks test evidence (coverage/junit) on disk

Each rule has:
  - id: unique identifier
  - name: human-readable name
  - trigger_patterns: what causes a violation
  - check_fn: function evaluating the violation against real state
  - severity: BLOCK | ESCALATE | WARN
"""

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional


@dataclass
class RuleDefinition:
    """Definition of a single enforcement rule."""

    id: str
    name: str
    description: str
    trigger_patterns: list[str]
    check_fn: Callable[[dict], tuple[bool, str]]
    recovery_fn: Optional[Callable[[dict], str]] = None
    severity: str = "BLOCK"
    auto_recoverable: bool = True


_PROTECTED_BRANCHES: tuple[str, ...] = ("main", "master", "dev")
_CODE_EXTENSIONS: tuple[str, ...] = (".py", ".js", ".ts", ".vue", ".php", ".jsx", ".tsx")
_ACTIVE_SPEC_STATUSES: tuple[str, ...] = ("approved", "in_progress", "completed")
_TEST_EVIDENCE_FILES: tuple[str, ...] = ("coverage.xml", ".coverage", "junit.xml")
_SPEC_STATUS_RE = re.compile(r"^status:\s*['\"]?(\w+)", re.MULTILINE)
_COVERAGE_LINE_RATE_RE = re.compile(r'<coverage[^>]*\bline-rate="([\d.]+)"')


def _context_cwd(context: dict) -> Path:
    """Working directory the operation runs in (defaults to process cwd)."""
    return Path(context.get("cwd") or ".")


# ---------------------------------------------------------------------------
# branch-isolation — real branch read from git, never a supplied string
# ---------------------------------------------------------------------------

def _read_current_branch(cwd: Path) -> Optional[str]:
    """Read the current branch from git (read-only). None when unavailable."""
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            timeout=2,
            cwd=str(cwd),
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def _check_branch_isolation(context: dict) -> tuple[bool, str]:
    """Block `git commit` on protected branches — branch read from disk."""
    tool = context.get("tool_name", "")
    command = context.get("command", "")
    if tool != "Bash" or "git commit" not in command:
        return False, ""
    branch = _read_current_branch(_context_cwd(context))
    if branch in _PROTECTED_BRANCHES:
        return (
            True,
            f"VIOLATION [branch-isolation]: Commit on {branch}. Use a feature branch.",
        )
    return False, ""


# ---------------------------------------------------------------------------
# spec-driven — an approved spec file must exist on disk
# ---------------------------------------------------------------------------

def _spec_dir(context: dict) -> Path:
    """Resolve the spec directory for the current operation.

    Path contract: approved Living Specs are YAML files saved via
    ``core.specs.manager.SpecManager.save_to_yaml`` under
    ``<project>/.arkaos/specs/``. ``context['specs_dir']`` overrides the
    default for callers that persist specs elsewhere.
    """
    override = context.get("specs_dir", "")
    if override:
        return Path(override)
    return _context_cwd(context) / ".arkaos" / "specs"


def _spec_file_is_active(path: Path) -> bool:
    """True when the spec YAML carries status approved/in_progress/completed."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return False
    match = _SPEC_STATUS_RE.search(text)
    return bool(match and match.group(1).lower() in _ACTIVE_SPEC_STATUSES)


def _has_approved_spec_on_disk(context: dict) -> bool:
    spec_dir = _spec_dir(context)
    if not spec_dir.is_dir():
        return False
    return any(
        _spec_file_is_active(path)
        for pattern in ("*.yaml", "*.yml")
        for path in spec_dir.glob(pattern)
    )


def _check_spec_driven(context: dict) -> tuple[bool, str]:
    """Block code modification when no approved spec exists on disk."""
    tool = context.get("tool_name", "")
    file_path = context.get("file_path", "")
    if tool not in ("Write", "Edit") or not file_path.endswith(_CODE_EXTENSIONS):
        return False, ""
    if _has_approved_spec_on_disk(context):
        return False, ""
    return (
        True,
        f"VIOLATION [spec-driven]: {file_path} modified without an approved "
        f"spec on disk (looked in {_spec_dir(context)}).",
    )


# ---------------------------------------------------------------------------
# mandatory-qa — test evidence must exist on disk, booleans are not trusted
# ---------------------------------------------------------------------------

def _find_test_evidence(cwd: Path) -> Optional[Path]:
    """Locate a test-evidence artifact (coverage/junit report or pytest cache)."""
    for name in _TEST_EVIDENCE_FILES:
        candidate = cwd / name
        if candidate.is_file():
            return candidate
    cache = cwd / ".pytest_cache"
    return cache if cache.is_dir() else None


def _coverage_percent_from_xml(path: Path) -> Optional[float]:
    """Parse total line-rate from a coverage.xml report as a percentage."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    match = _COVERAGE_LINE_RATE_RE.search(text)
    return float(match.group(1)) * 100 if match else None


def _check_mandatory_qa(context: dict) -> tuple[bool, str]:
    """Block delivery without test evidence on disk (or coverage < 80%)."""
    if context.get("workflow_phase", "") != "delivery":
        return False, ""
    cwd = _context_cwd(context)
    evidence = _find_test_evidence(cwd)
    if evidence is None:
        return (
            True,
            "VIOLATION [mandatory-qa]: no test evidence on disk "
            "(expected coverage.xml, .coverage, junit.xml or .pytest_cache/).",
        )
    coverage_xml = cwd / "coverage.xml"
    coverage = _coverage_percent_from_xml(coverage_xml) if coverage_xml.is_file() else None
    if coverage is not None and coverage < 80:
        return (
            True,
            f"VIOLATION [mandatory-qa]: coverage {coverage:.1f}% below 80% "
            "threshold (coverage.xml).",
        )
    return False, ""


RULES_REGISTRY: dict[str, RuleDefinition] = {
    "branch-isolation": RuleDefinition(
        id="branch-isolation",
        name="Branch Isolation",
        description="All code-modifying work runs on dedicated feature branches",
        trigger_patterns=["git commit on main/master/dev"],
        check_fn=_check_branch_isolation,
        recovery_fn=None,
        severity="BLOCK",
        auto_recoverable=False,
    ),
    "spec-driven": RuleDefinition(
        id="spec-driven",
        name="Spec Driven",
        description="No code is written until an approved spec exists on disk",
        trigger_patterns=["code modification without approved spec on disk"],
        check_fn=_check_spec_driven,
        recovery_fn=None,
        severity="BLOCK",
        auto_recoverable=False,
    ),
    "mandatory-qa": RuleDefinition(
        id="mandatory-qa",
        name="Mandatory QA",
        description="Delivery requires test evidence on disk with coverage >= 80%",
        trigger_patterns=["delivery without test evidence or coverage < 80%"],
        check_fn=_check_mandatory_qa,
        recovery_fn=None,
        severity="BLOCK",
        auto_recoverable=False,
    ),
}


def get_all_rules() -> dict[str, RuleDefinition]:
    """Get all registered rules."""
    return RULES_REGISTRY


def get_rule(rule_id: str) -> RuleDefinition | None:
    """Get a specific rule by ID."""
    return RULES_REGISTRY.get(rule_id)


def get_rules_by_severity(severity: str) -> list[RuleDefinition]:
    """Get all rules with a specific severity."""
    return [r for r in RULES_REGISTRY.values() if r.severity == severity]

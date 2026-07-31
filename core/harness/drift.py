"""Spec-vs-disk drift detection for the Claude Code harness (PR-C1).

``scan()`` reads the operator's ``settings.json`` and reports where it
diverges from ``core.harness.spec``. Read-only by contract — the same
rule ``harness_scanner`` holds: a scan never mutates what it measures,
prints nothing, exits nothing, and NEVER raises on hostile input (a
truncated or binary settings file is a finding, not a traceback).

Drift vocabulary, aligned with the ownership policies:

- ``missing``  — an ArkaOS-managed entry is absent: an owned entry
  (own / own-subset), a seed surface that was never seeded, or the
  settings file itself.
- ``diverged`` — an ArkaOS-owned entry is present but altered.
- ``adopted``  — a ``seed`` surface the operator changed; the operator
  won, drift REPORTS it and C2's assert, once it ships, must never
  revert it.
- ``unreadable`` — the settings file could not be used, or the scan
  itself could not run (unknown runtime, internal failure).

Operator additions — extra hook entries, extra deny rules, unknown
settings keys — are NOT drift. Under own-subset the operator's material
is legitimate content, and flagging it would teach the operator to
ignore the report (the harness_scanner noise lesson).
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

from core.harness import json_store, paths
from core.harness.spec import HookRegistration, RuntimeSpec, spec_for


class DriftStatus(StrEnum):
    """Kind of divergence between spec and disk."""

    MISSING = "missing"
    DIVERGED = "diverged"
    ADOPTED = "adopted"
    UNREADABLE = "unreadable"


@dataclass(frozen=True)
class DriftFinding:
    """One divergence, with enough detail to act on."""

    surface: str
    status: DriftStatus
    where: str
    detail: str

    def to_dict(self) -> dict:
        return {
            "surface": self.surface,
            "status": self.status.value,
            "where": self.where,
            "detail": self.detail,
        }


@dataclass
class DriftReport:
    """Result of one drift scan against one settings file."""

    settings_path: Path
    runtime: str
    findings: list[DriftFinding] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """True when nothing ArkaOS-owned is missing, diverged or unreadable.

        ``adopted`` findings do not fail the report — the operator
        winning a seed surface is recorded state, not a defect.
        """
        return not [
            f
            for f in self.findings
            if f.status is not DriftStatus.ADOPTED
        ]

    def to_dict(self) -> dict:
        return {
            "settings_path": str(self.settings_path),
            "runtime": self.runtime,
            "ok": self.ok,
            "findings": [f.to_dict() for f in self.findings],
        }


def scan(
    home: Path | None = None,
    runtime: str = "claude-code",
    platform: str | None = None,
    hooks_root: str | None = None,
) -> DriftReport:
    """Compare the harness on disk to the runtime spec. Never raises.

    ``platform`` defaults to ``sys.platform`` (``win32`` skips
    posix-only registrations); ``hooks_root`` overrides the ArkaOS root
    used to evaluate ``conditional`` registrations.
    """
    settings_path = paths.claude_settings_path(home)
    report = DriftReport(settings_path=settings_path, runtime=runtime)
    spec = _spec_or_finding(report, runtime)
    if spec is None:
        return report
    try:
        _scan_into(report, spec, platform, hooks_root)
    except Exception as exc:  # never-raises boundary
        report.findings.append(
            DriftFinding(
                "settings", DriftStatus.UNREADABLE, str(settings_path),
                f"scan aborted: {type(exc).__name__}: {exc}",
            )
        )
    return report


def _spec_or_finding(report: DriftReport, runtime: str) -> RuntimeSpec | None:
    """Resolve the runtime spec, or record why the scan cannot run.

    An unknown runtime is a caller problem, not a settings problem —
    naming the settings file would send the operator to debug the
    wrong thing.
    """
    try:
        return spec_for(runtime)
    except ValueError as exc:
        report.findings.append(
            DriftFinding("runtime", DriftStatus.UNREADABLE, runtime, str(exc))
        )
        return None


# Operator-facing phrasing per load error; the installer remediation is
# only true for the missing case — re-running it does not repair a
# corrupted or oversized file.
_LOAD_ERROR_DETAIL = {
    "missing": "settings file missing; run the installer to seed it",
    "invalid-json": "settings file is not valid JSON",
    "not-an-object": "settings file is not a JSON object",
    "unreadable": "settings file could not be read",
    "oversized": "settings file exceeds the 2 MiB read ceiling",
}


def _scan_into(
    report: DriftReport,
    spec: RuntimeSpec,
    platform: str | None,
    hooks_root: str | None,
) -> None:
    loaded = json_store.load_json(report.settings_path)
    if not loaded.ok:
        status = (
            DriftStatus.MISSING
            if loaded.error == "missing"
            else DriftStatus.UNREADABLE
        )
        detail = _LOAD_ERROR_DETAIL.get(
            loaded.error or "", f"settings file unusable: {loaded.error}"
        )
        report.findings.append(
            DriftFinding("settings", status, str(report.settings_path), detail)
        )
        return
    settings = loaded.data or {}
    _check_hooks(report, spec, settings, platform, hooks_root)
    _check_hard_deny(report, spec, settings)
    _check_status_line(report, settings)
    _check_worktree(report, settings)


def _check_hooks(
    report: DriftReport,
    spec: RuntimeSpec,
    settings: dict[str, Any],
    platform: str | None,
    hooks_root: str | None,
) -> None:
    hooks = settings.get("hooks")
    hooks = hooks if isinstance(hooks, dict) else {}
    is_windows = (platform or sys.platform) == "win32"
    for reg in spec.hook_registrations:
        if reg.posix_only and is_windows:
            continue
        if reg.conditional and not _script_deployed(reg, hooks_root):
            continue
        _check_registration(report, reg, hooks.get(reg.event))


def _check_registration(
    report: DriftReport, reg: HookRegistration, entries: Any
) -> None:
    where = f"hooks.{reg.event}" + (
        f"[matcher={reg.matcher}]" if reg.matcher else ""
    )
    entry = _find_entry(reg, entries)
    if entry is None:
        report.findings.append(
            DriftFinding(
                "settings:hooks", DriftStatus.MISSING, where,
                f"no {reg.script} entry registered for this event",
            )
        )
        return
    timeout = entry.get("timeout")
    if timeout != reg.timeout:
        report.findings.append(
            DriftFinding(
                "settings:hooks", DriftStatus.DIVERGED, where,
                f"timeout is {timeout!r}, spec says {reg.timeout}",
            )
        )


def _find_entry(reg: HookRegistration, entries: Any) -> dict | None:
    """The ArkaOS inner hook entry for ``reg``, or None."""
    if not isinstance(entries, list):
        return None
    wanted = {f"{reg.script}.sh", f"{reg.script}.ps1", f"{reg.script}.cjs"}
    for group in entries:
        if not isinstance(group, dict):
            continue
        if (group.get("matcher") or None) != reg.matcher:
            continue
        for inner in group.get("hooks") or []:
            if not isinstance(inner, dict):
                continue
            command = str(inner.get("command", ""))
            if command and Path(command).name in wanted:
                return inner
    return None


def _script_deployed(reg: HookRegistration, hooks_root: str | None) -> bool:
    try:
        hooks = paths.hooks_dir(hooks_root)
        return any(
            (hooks / f"{reg.script}{ext}").is_file()
            for ext in (".sh", ".ps1", ".cjs")
        )
    except OSError:
        return False


def _check_hard_deny(
    report: DriftReport, spec: RuntimeSpec, settings: dict[str, Any]
) -> None:
    auto_mode = settings.get("autoMode")
    auto_mode = auto_mode if isinstance(auto_mode, dict) else {}
    rules = auto_mode.get("hard_deny")
    rules = rules if isinstance(rules, list) else []
    present = {r for r in rules if isinstance(r, str)}
    absent = [r for r in spec.hard_deny_rules if r not in present]
    if not absent:
        return
    examples = ", ".join(absent[:3])
    report.findings.append(
        DriftFinding(
            "settings:autoMode.hard_deny", DriftStatus.MISSING,
            "autoMode.hard_deny",
            f"{len(absent)} of {len(spec.hard_deny_rules)} curated deny "
            f"rules absent (e.g. {examples})",
        )
    )


def _check_status_line(report: DriftReport, settings: dict[str, Any]) -> None:
    status_line = settings.get("statusLine")
    if status_line is None:
        report.findings.append(
            DriftFinding(
                "settings:statusLine", DriftStatus.MISSING, "statusLine",
                "status line not seeded",
            )
        )
    elif not _is_arkaos_statusline(status_line):
        report.findings.append(
            DriftFinding(
                "settings:statusLine", DriftStatus.ADOPTED, "statusLine",
                "operator-configured status line; seed policy adopts it",
            )
        )


def _check_worktree(report: DriftReport, settings: dict[str, Any]) -> None:
    worktree = settings.get("worktree")
    if worktree is None:
        report.findings.append(
            DriftFinding(
                "settings:worktree", DriftStatus.MISSING, "worktree",
                "worktree.baseRef default not seeded",
            )
        )
    elif not (
        isinstance(worktree, dict) and worktree.get("baseRef") == "head"
    ):
        report.findings.append(
            DriftFinding(
                "settings:worktree", DriftStatus.ADOPTED, "worktree",
                "operator-configured worktree; seed policy adopts it",
            )
        )


def _is_arkaos_statusline(status_line: Any) -> bool:
    if not isinstance(status_line, dict):
        return False
    command = str(status_line.get("command", ""))
    return Path(command.strip('"')).name in ("statusline.sh", "statusline.ps1")

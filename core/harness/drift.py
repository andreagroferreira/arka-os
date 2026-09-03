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

import os
import re
import shlex
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
    _check_fallback_model(report, settings)


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
    accepted = _accepted_hook_dirs(report.settings_path, hooks_root)
    for reg in spec.hook_registrations:
        if reg.posix_only and is_windows:
            continue
        if reg.conditional and not _script_deployed(reg, hooks_root):
            continue
        _check_registration(report, reg, hooks.get(reg.event), accepted)


def _accepted_hook_dirs(
    settings_path: Path, hooks_root: str | None
) -> frozenset[str] | None:
    """Directories an ArkaOS hook command may legitimately live in.

    Three: what the installer writes (``~/.arkaos/config/hooks`` —
    adapters/claude-code.js joins installDir with config/hooks;
    omitting it read every healthy install as stale and repointed it
    at the purgeable npx cache, QG C2 r1 Francisca B1), the
    ``~/.arkaos/lib`` snapshot, and the current resolved root.
    Anything else with an ArkaOS basename is a STALE root — the
    split-root failure mode basename matching hid (#439 M6).

    None when the root cannot be resolved: without a reference point
    staleness cannot be judged, and flagging everything is noise.
    """
    home = settings_path.parent.parent  # <home>/.claude/settings.json
    try:
        arkaos = paths.arkaos_home(home)
        return frozenset(
            _normalised(candidate)
            for candidate in (
                arkaos / "config" / "hooks",
                arkaos / "lib" / "config" / "hooks",
                paths.hooks_dir(hooks_root),
            )
        )
    except OSError:
        return None


def _normalised(path: Path) -> str:
    """Comparable form of a directory path.

    Case-folded and lexically normalised: a case variant or a ``..``
    segment names the same directory on the operator's filesystem and
    must not read as a different root (QG C2 r1 M2). ``resolve()`` is
    deliberately not used — it hits the filesystem and would make a
    read-only scan depend on what happens to exist.
    """
    return os.path.normcase(os.path.normpath(str(path)))


def hook_command_path(command: object) -> Path:
    """The script path inside a hook ``command`` string.

    Operators write commands with surrounding quotes and with
    interpreter prefixes (``bash /path/hook.sh``); matching on the raw
    string appended a DUPLICATE registration and stripped the prefix
    (QG C2 r1, Francisca B7). One normaliser, used by every consumer.
    """
    text = str(command or "").strip()
    if not text:
        return Path("")
    parts = shlex.split(text) if _splittable(text) else [text]
    parts = _before_shell_operator(parts)
    for token in reversed(parts):
        if token.endswith(_HOOK_SUFFIXES):
            return Path(token)
    for token in reversed(parts):
        if "/" in token or "\\" in token:
            return Path(token)
    return Path(parts[-1]) if parts else Path("")


_SHELL_OPERATOR_RE = re.compile(r"[|;&>]")
_HOOK_SUFFIXES = (".sh", ".ps1", ".cjs")


def _before_shell_operator(parts: list[str]) -> list[str]:
    """Tokens up to the first shell operator.

    Load-bearing whenever the SECOND command or the redirect target
    would win the scan: ``stop.sh 2>/tmp/hook-debug.sh`` ends in a
    hook suffix, ``stop.sh && /usr/local/bin/notify.sh`` chains a
    second script, and ``bash <dir>/stop 2>/dev/null`` has no suffix
    at all — in each case the wrong token is read as the script, the
    ArkaOS entry goes unrecognised, and assert appends a SECOND
    registration that fires the hook twice (QG C2 r2 Francisca B2;
    the ``2>/dev/null`` example first documented here was already
    handled by the suffix scan, QG C2 r3 Eduardo).

    Operators attach to the previous token as often as they stand
    alone (``stop.sh;`` vs ``stop.sh ;``), so both forms cut.
    """
    kept: list[str] = []
    for token in parts:
        head = _operator_head(token)
        if head is None:
            kept.append(token)
            continue
        if head:
            kept.append(head)
        break
    return kept or parts


def _operator_head(token: str) -> str | None:
    """Text before a genuine shell operator in ``token``, else None.

    An operator CHARACTER is not an operator POSITION: a directory
    named ``R&D`` or ``a;b`` is an ordinary path, and cutting there
    made the manager stop recognising the entry it had just written —
    assert went non-idempotent, appending a Stop group per run
    (QG C2 r4, Francisca B2; the regression came from the r3 fix for
    the duplication bug, not from the original code). A cut is
    genuine only where a shell would see one: at the start of the
    token, right after a hook script, or after a file-descriptor
    number.
    """
    match = _SHELL_OPERATOR_RE.search(token)
    if match is None:
        return None
    head = token[: match.start()]
    if not head or head.isdigit() or head.endswith(_HOOK_SUFFIXES):
        return head
    return None


def _splittable(text: str) -> bool:
    try:
        shlex.split(text)
        return True
    except ValueError:
        return False


def _check_registration(
    report: DriftReport,
    reg: HookRegistration,
    entries: Any,
    accepted: frozenset[str] | None,
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
    for detail in entry_divergences(entry, reg, accepted):
        report.findings.append(
            DriftFinding("settings:hooks", DriftStatus.DIVERGED, where, detail)
        )


def entry_divergences(
    entry: dict, reg: HookRegistration, accepted: frozenset[str] | None
) -> list[str]:
    """Why an existing ArkaOS entry diverges from spec — [] when clean.

    Shared with the C2 manager so drift and repair can never disagree
    about what counts as divergent.
    """
    divergences = []
    timeout = entry.get("timeout")
    if timeout != reg.timeout:
        divergences.append(f"timeout is {timeout!r}, spec says {reg.timeout}")
    command_dir = hook_command_path(entry.get("command")).parent
    if accepted is not None and _normalised(command_dir) not in accepted:
        divergences.append(
            f"stale-root: {reg.script} points at {command_dir}, not "
            f"the current ArkaOS hooks dir"
        )
    return divergences


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
            name = hook_command_path(inner.get("command")).name
            if name and name in wanted:
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


def _check_fallback_model(report: DriftReport, settings: dict[str, Any]) -> None:
    from core.runtime.claude_code import DEFAULT_FALLBACK_MODELS

    chain = settings.get("fallbackModel")
    if chain is None:
        report.findings.append(
            DriftFinding(
                "settings:fallbackModel", DriftStatus.MISSING, "fallbackModel",
                "fallbackModel chain default not seeded",
            )
        )
    elif chain != list(DEFAULT_FALLBACK_MODELS):
        report.findings.append(
            DriftFinding(
                "settings:fallbackModel", DriftStatus.ADOPTED, "fallbackModel",
                "operator-configured fallback chain; seed policy adopts it",
            )
        )


def _is_arkaos_statusline(status_line: Any) -> bool:
    if not isinstance(status_line, dict):
        return False
    command = str(status_line.get("command", ""))
    return Path(command.strip('"')).name in ("statusline.sh", "statusline.ps1")

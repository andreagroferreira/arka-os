"""Apply the fixes the harness scanner already names (PR-C3).

The scanner grades the harness and puts a ``fix`` on every finding, but
nothing applies them — the operator reads grade F and edits JSON by
hand. This module closes that loop for the findings that can be fixed
MECHANICALLY and SAFELY, and reports every finding it did not touch
with the reason it is not mechanically fixable.

The design rule that matters: **a remediator that skips silently is
worse than none**, because it turns an unfixed vulnerability into a
clean-looking run. Every scanner rule is classified here. A rule this
module has never heard of is reported as ``unknown-rule`` — loudly —
rather than dropped, so adding a scanner rule can never quietly widen
the set of things nobody fixes.

Scope is deliberately narrow: settings allow/deny lists, the one place
where a fix is unambiguous and strictly privilege-reducing. Secrets,
hook findings, unusable config files and the patterns only the operator
can choose are named ``needs-human``; MCP manifests and instruction
files are named ``out-of-scope``. The two are different promises and
this module never collapses them.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from core.governance.harness_scanner import (
    _DANGEROUS_COMMANDS,
    SETTINGS_FILES,
    Finding,
    ScanReport,
    _bash_command_word,
    _dangerous_allow_finding,
    scan,
)
from core.harness import json_store
from core.harness.spec import HARD_DENY_RULES

# ─── Classification ─────────────────────────────────────────────────────

# Rules this module can fix, and how.
#   drop-allow  — remove the offending rule from permissions.allow
#   seed-deny   — add the ArkaOS hard-deny defaults to permissions.deny
FIXABLE: dict[str, str] = {
    "settings-dangerous-allow": "drop-allow",
    "settings-no-deny": "seed-deny",
    "settings-bypass-mode": "seed-deny",
}

# Why every other rule is NOT mechanically fixable. The taxonomy is the
# point: "needs-human" and "out-of-scope" are different promises to the
# operator, and collapsing them into one bucket hides which findings
# will still be there tomorrow.
NON_FIXABLE: dict[str, tuple[str, str]] = {
    # The scanner's own fix for this one is "scope it", and only you know
    # the pattern. Dropping the rule instead would be a DIFFERENT fix
    # from the one named — and for a read-only tool like Read(*) it
    # costs real UX for no execution risk. So: named, never guessed.
    "settings-unscoped-allow": (
        "needs-human",
        "the fix is to narrow the rule to a pattern, and only you know "
        "which one — dropping it outright is a different decision",
    ),
    "settings-secret-in-env": (
        "needs-human",
        "only you know whether the value is a real credential and where "
        "it should live instead",
    ),
    "config-unparseable": (
        "needs-human",
        "the file must be valid JSON before anything can edit it safely",
    ),
    "config-unreadable": (
        "needs-human",
        "the file cannot be read — check its size (2 MB cap) and its "
        "permissions",
    ),
    "hook-command-injection": (
        "needs-human",
        "rewriting a hook command changes what it does; the safe form "
        "depends on intent",
    ),
    "hook-silences-errors": (
        "needs-human",
        "removing the silencer may make a hook fail loudly, which is the "
        "point but not a decision to take for you",
    ),
    "hook-script-missing": (
        "needs-human",
        "the script has to be restored or the registration removed — "
        "which one depends on whether you still want the hook",
    ),
    "hook-world-writable": (
        "needs-human",
        "chmod on a file this tool does not own; run it yourself once "
        "you have checked who else writes there",
    ),
    "hook-script-unreadable": (
        "needs-human",
        "the hook target could not be read, so its permissions and its "
        "contents are unaudited — only you can say whether that path is "
        "meant to be private or is simply wrong",
    ),
    "mcp-secret-in-env": ("out-of-scope", "MCP manifests are not edited here"),
    "mcp-unpinned-package": (
        "out-of-scope", "MCP manifests are not edited here"
    ),
    "mcp-auto-install": ("out-of-scope", "MCP manifests are not edited here"),
    "mcp-shell-command": ("out-of-scope", "MCP manifests are not edited here"),
    "instructions-injection": (
        "out-of-scope", "instruction files are prose, not configuration"
    ),
    "instructions-secret": (
        "out-of-scope", "instruction files are prose, not configuration"
    ),
    "instructions-invisible-characters": (
        "out-of-scope", "instruction files are prose, not configuration"
    ),
    "scanner-error": (
        "needs-human", "the scanner itself failed on this path"
    ),
}


@dataclass
class Skipped:
    """A finding this module did not fix, and why."""

    rule: str
    where: str
    reason: str      # needs-human | out-of-scope | unknown-rule
    detail: str

    def to_dict(self) -> dict:
        return {
            "rule": self.rule, "where": self.where,
            "reason": self.reason, "detail": self.detail,
        }


@dataclass
class FixReport:
    """What a --fix run did, would do, or refused to do."""

    applied: bool
    removed_allow: list[str] = field(default_factory=list)
    seeded_deny: list[str] = field(default_factory=list)
    skipped: list[Skipped] = field(default_factory=list)
    backups: list[Path] = field(default_factory=list)
    refused: str | None = None
    settings_paths: list[Path] = field(default_factory=list)
    # Per-file outcome. A single `applied` bool cannot describe a run
    # that wrote one file and failed the next, and reporting that state
    # as "nothing was written" is a lie about the operator's disk.
    written: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    # The staged files themselves, so the render can attribute every
    # removal, seed and backup to the file it belongs to.
    states: list[_FileState] = field(default_factory=list)

    @property
    def partial(self) -> bool:
        """Some files were written and some were not."""
        return bool(self.written and self.failed)

    @property
    def changed(self) -> bool:
        return bool(self.removed_allow or self.seeded_deny)

    @property
    def backup(self) -> Path | None:
        """The first backup taken, for single-file callers."""
        return self.backups[0] if self.backups else None

    def absorb(self, states: list[_FileState]) -> None:
        """Roll the per-file outcomes up, in the SAME units.

        `written` and `failed` both name settings files: mixing a
        resolved target into one and a file name into the other put two
        units in one sentence (QG C3 r3, Francisca M2).
        """
        for state in states:
            if state.written:
                self.written.append(state.name)
            else:
                self.failed.append(state.name)
            if state.backup is not None:
                self.backups.append(state.backup)
        failures = [s.failure for s in states if s.failure]
        self.refused = "; ".join(failures) if failures else None
        self.applied = bool(self.written) and not self.failed

    def to_dict(self) -> dict:
        return {
            "applied": self.applied,
            "changed": self.changed,
            # Which files reached disk. A consumer that only sees
            # `applied: false` concludes nothing was written, while a
            # partial run has already replaced one of them.
            "written": list(self.written),
            "failed": list(self.failed),
            "partial": self.partial,
            "settings_paths": [str(p) for p in self.settings_paths],
            "backups": [str(p) for p in self.backups],
            "refused": self.refused,
            "removed_allow": list(self.removed_allow),
            "seeded_deny": list(self.seeded_deny),
            # Per file, so a consumer can tell WHICH rules survived a
            # partial apply — the run-level lists above are the PLAN.
            "files": [
                {"name": s.name, "written": s.written,
                 "removed": list(s.removed), "seeded": list(s.seeded),
                 "backup": str(s.backup) if s.backup else None,
                 "failure": s.failure}
                for s in self.states
            ],
            "skipped": [s.to_dict() for s in self.skipped],
        }


def classify(finding: Finding) -> tuple[str, str]:
    """Return ``(kind, reason)`` for one finding.

    ``kind`` is the FIXABLE action, or one of the non-fixable reasons.
    An unrecognised rule is ``unknown-rule`` — never silently dropped.
    """
    action = FIXABLE.get(finding.rule)
    if action:
        return action, ""
    known = NON_FIXABLE.get(finding.rule)
    if known:
        return known[0], known[1]
    return (
        "unknown-rule",
        "this remediator has no classification for that scanner rule — "
        "report it so it gets one",
    )


# ─── Planning ───────────────────────────────────────────────────────────


def is_dangerous_allow(rule: object) -> bool:
    """True when ``rule`` grants a dangerous COMMAND.

    Only the scanner's command-word branch counts here. Its second
    branch matches free text against the whole rule string with no tool
    guard, so ``Read(core/eval/**)`` and ``Edit(docs/sudo-setup.md)``
    trip it on their PATHS. Under the scanner that was a cosmetic false
    positive; a remediator would convert it into deletion of a benign,
    correctly-scoped read grant (QG C3 r1, Francisca B4 — reproduced).
    Free-text-only matches are classified needs-human instead.
    """
    if not isinstance(rule, str):
        return False
    return _bash_command_word(rule) in _DANGEROUS_COMMANDS


def dangerous_rules(allow: list) -> list[str]:
    """The dangerous-command allow rules in a LIVE allow list.

    Asked of the scanner's own predicate against the live list, never
    parsed back out of the finding's prose: a rule containing quotes
    cannot be sliced back out of the sentence that embedded its repr(),
    and deriving a fact from prose instead of from code is how a
    remediator ends up deleting the wrong line.
    """
    return [rule for rule in allow if is_dangerous_allow(rule)]


def _free_text_danger(rule: object) -> bool:
    """Flagged dangerous by the scanner, but not by its command word."""
    return (
        isinstance(rule, str)
        and not is_dangerous_allow(rule)
        and _dangerous_allow_finding(rule, "x") is not None
    )


def _skip_for(
    finding: Finding, kind: str, reason: str, scanner_detail: str = ""
) -> Skipped:
    """Carry the scanner's own detail alongside our reason.

    Without it, two unscoped findings in one file render as identical
    lines and the operator cannot tell WHICH rules they are (QG C3 r1,
    Francisca M2).
    """
    detail = f"{scanner_detail} — {reason}" if scanner_detail else reason
    return Skipped(finding.rule, finding.where, kind, detail)


def _free_text_skips(allow: list, where: str) -> list[Skipped]:
    """One Skipped per RULE the scanner flags only by wording.

    Derived from the live allow list, not from the findings: a finding
    does not name its rule in a machine-readable way, and emitting one
    skip per finding when any rule matches inflates the count — the
    accounting has to be exact for the anti-silence invariant to mean
    anything.
    """
    skips = []
    for rule in allow:
        if not _free_text_danger(rule):
            continue
        # Carry the scanner's OWN label. Without it a rule like
        # `--dangerously-skip-permissions`, whose label is "permission
        # bypass", was described to the operator as probably benign —
        # the tool nudging them to keep a genuine critical (QG C3 r2,
        # Francisca M1).
        finding = _dangerous_allow_finding(rule, where)
        detail = finding.detail if finding else ""
        skips.append(Skipped(
            "settings-dangerous-allow", where, "needs-human",
            f"{detail} This remediator will not drop it: the scanner "
            f"matched the wording, not the command word, so the "
            f"decision is yours.",
        ))
    return skips


# ─── Applying ───────────────────────────────────────────────────────────


def _backup(path: Path) -> Path:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    dest = path.with_name(f"{path.name}.arkaos-backup-{stamp}")
    shutil.copy2(path, dest)
    return dest


def _resolve_target(path: Path) -> Path:
    """The file a write must land on.

    A symlinked settings.json is the standard dotfiles/stow/chezmoi
    layout. ``os.replace`` would replace the LINK, leaving the
    authoritative file still carrying the dangerous rule while the tool
    reported success (QG C3 r1, Francisca B3 — reproduced). Writing
    through to the target is the only write that tells the truth.
    """
    return path.resolve() if path.is_symlink() else path


@dataclass
class _FileState:
    """One settings file this run considered.

    Removals, seeds and the backup are recorded HERE, per file. A
    run-level union cannot say which file a rule was removed from, so a
    partial apply printed rules under "removed" that were still live in
    the file that failed (QG C3 r3, both reviewers, reproduced).
    """

    name: str
    path: Path
    target: Path
    settings: dict | None = None
    perms: dict | None = None
    allow: list = field(default_factory=list)
    refusal: str | None = None
    removed: list[str] = field(default_factory=list)
    seeded: list[str] = field(default_factory=list)
    backup: Path | None = None
    written: bool = False
    failure: str | None = None


def _read_file(root: Path, name: str) -> _FileState:
    path = root / name
    state = _FileState(name=name, path=path, target=_resolve_target(path))
    if not path.exists():
        return state
    loaded = json_store.load_json(state.target)
    if not loaded.ok or not isinstance(loaded.data, dict):
        state.refusal = f"{name} not usable ({loaded.error})"
        return state
    state.settings = loaded.data
    perms = loaded.data.get("permissions")
    if perms is not None and not isinstance(perms, dict):
        state.refusal = f"{name}: permissions is not an object"
        return state
    state.perms = perms if isinstance(perms, dict) else None
    allow = state.perms.get("allow") if state.perms else None
    state.allow = allow if isinstance(allow, list) else []
    return state


def _findings_for(report: ScanReport, name: str) -> list[Finding]:
    """Findings whose ``where`` names this settings file.

    The scanner qualifies ``where`` with the file name; a finding from
    another file must never drive a write here.
    """
    return [f for f in report.findings if name in f.where]


def plan_file(
    report: ScanReport, state: _FileState
) -> tuple[list[str], bool, list[Skipped]]:
    """(rules to drop, seed deny?, skipped) for ONE settings file."""
    to_drop = dangerous_rules(state.allow)
    seed_deny = False
    # One skip per free-text-only rule, from the live list. The
    # drop-allow findings themselves are accounted for by
    # to_drop + these, so they are not re-counted below.
    skipped: list[Skipped] = _free_text_skips(state.allow, state.name)
    for finding in _findings_for(report, state.name):
        kind, reason = classify(finding)
        if kind == "drop-allow":
            continue
        if kind == "seed-deny":
            seed_deny = True
        else:
            skipped.append(_skip_for(finding, kind, reason, finding.detail))
    return to_drop, seed_deny, skipped


def _unaccounted(report: ScanReport, seen: set[str]) -> list[Skipped]:
    """Findings from files this run never opened.

    The anti-silence invariant lives here: a finding the remediator did
    not consider is reported, never dropped on the floor.
    """
    return [
        _skip_for(
            f, "out-of-scope",
            f"{f.where} is not a settings file this remediator opens",
            f.detail,
        )
        for f in report.findings
        if not any(name in f.where for name in seen)
    ]


# ─── Applying ───────────────────────────────────────────────────────────


def _commit(state: _FileState) -> bool:
    """Back up and write ONE file. False when either step failed.

    The backup is recorded on the state only when it actually exists:
    when ``_backup`` is itself what raised, the file has no backup and
    the report must not promise one (QG C3 r3, both reviewers).
    """
    try:
        state.backup = _backup(state.target)
        json_store.write_json_atomic(state.target, state.settings)
    except OSError as exc:
        state.failure = f"{state.name}: {exc}"
        return False
    state.written = True
    return True


def fix(root: Path, apply: bool = False) -> FixReport:
    """Plan (and optionally apply) the mechanical fixes under ``root``.

    Every settings file the scanner reads is considered, and every
    finding is either acted on or named. Never raises: an unreadable or
    corrupt file is a refusal with a reason, not a traceback.
    """
    report = FixReport(applied=False)
    try:
        scan_report = scan(root)
    except Exception as exc:  # a scan failure is a refusal, not a crash
        report.refused = f"scan failed: {type(exc).__name__}"
        return report

    seen, pending = _stage_all(Path(root).expanduser(), scan_report, report)
    report.skipped.extend(_unaccounted(scan_report, seen))
    report.states = pending
    if not report.changed or not apply:
        return report
    for state in pending:
        _commit(state)
    report.absorb(pending)
    return report


def _stage_all(
    root: Path, scan_report: ScanReport, report: FixReport
) -> tuple[set[str], list[_FileState]]:
    """Read, plan and stage every settings file. Nothing is written."""
    seen: set[str] = set()
    pending: list[_FileState] = []
    for name in SETTINGS_FILES:
        state = _read_file(root, name)
        if not state.path.exists():
            continue
        seen.add(name)
        report.settings_paths.append(state.target)
        # The findings of an unusable file are classified BEFORE the
        # refusal short-circuits it: skipping straight past them is the
        # same anti-silence hole this module exists to close, one file
        # over (test_corrupt_settings_never_mutates_and_is_named).
        to_drop, seed_deny, skipped = plan_file(scan_report, state)
        report.skipped.extend(skipped)
        if state.refusal:
            report.skipped.append(
                Skipped("config-unusable", name, "needs-human", state.refusal)
            )
        elif _stage(state, to_drop, seed_deny, report):
            pending.append(state)
    return seen, pending


def _stage(
    state: _FileState, to_drop: list[str], seed_deny: bool, report: FixReport
) -> bool:
    """Apply the plan to the in-memory settings. True when it changed."""
    if not (to_drop or seed_deny):
        return False
    if state.perms is None:
        report.skipped.append(Skipped(
            "config-unusable", state.name, "needs-human",
            f"{state.name} has fixable findings but no permissions object",
        ))
        return False
    _plan_removals(state, to_drop)
    if seed_deny:
        _plan_deny(state)
    if state.removed or state.seeded:
        state.settings["permissions"] = state.perms
        report.removed_allow.extend(state.removed)
        report.seeded_deny.extend(state.seeded)
        return True
    return False


def _plan_removals(state: _FileState, to_drop: list[str]) -> None:
    allow = state.perms.get("allow")
    if not isinstance(allow, list) or not to_drop:
        return
    drop = set(to_drop)
    state.removed = [r for r in allow if isinstance(r, str) and r in drop]
    state.perms["allow"] = [
        r for r in allow if not (isinstance(r, str) and r in drop)
    ]


def _plan_deny(state: _FileState) -> None:
    existing = state.perms.get("deny")
    existing = existing if isinstance(existing, list) else []
    merged = json_store.merge_unique(
        [r for r in existing if isinstance(r, str)], HARD_DENY_RULES
    )
    added = [r for r in merged if r not in existing]
    if added:
        state.seeded = added
        state.perms["deny"] = merged


# ─── Rendering ──────────────────────────────────────────────────────────


def _file_lines(state: _FileState, applied: bool) -> list[str]:
    """One file's removals and seeds, in the tense that file earned.

    A run-level verb cannot speak for N files: a partial apply printed
    the failed file's rules under "removed" while they were still live
    on disk, which ends the operator's attention on a CRITICAL grant
    (QG C3 r3, both reviewers, reproduced).
    """
    if not (state.removed or state.seeded):
        return []
    wrote = applied and state.written
    lines = [f"{state.name}:"]
    if state.removed:
        verb = "removed" if wrote else "would remove"
        lines.append(f"  {verb} {len(state.removed)} allow rule(s):")
        lines += [f"    - {r}" for r in state.removed]
    if state.seeded:
        verb = "seeded" if wrote else "would seed"
        lines.append(f"  {verb} {len(state.seeded)} hard-deny rule(s)")
    if wrote and state.backup:
        lines.append(f"  backup: {state.backup}")
    elif state.failure:
        lines.append(f"  NOT WRITTEN — {state.failure}")
        lines.append(
            f"  backup: {state.backup} (the untouched original)"
            if state.backup
            else "  no backup was taken; the file is unchanged on disk"
        )
    return lines


def _render_actions(report: FixReport) -> list[str]:
    """One block per file, then the run-level line: a refusal, or
    which files reached disk on a partial apply, or that nothing did."""
    lines: list[str] = []
    for state in report.states:
        lines += _file_lines(state, bool(report.written))
    if report.refused and not report.failed:
        # A run-level refusal (a scan that raised) has no states to
        # render, so without this line the whole report is the empty
        # string — the one failure meaning "I examined nothing at all"
        # printing nothing at all (QG C3 r4, Francisca B1, reproduced).
        # The guard keeps it from duplicating the per-file NOT WRITTEN
        # text, which already names each failure.
        lines.append(f"REFUSED: {report.refused}")
    if not report.changed and not report.refused:
        lines.append("nothing mechanically fixable found")
    if report.partial:
        lines.append(
            "PARTIAL APPLY — written: " + ", ".join(report.written)
            + " | NOT written: " + ", ".join(report.failed)
            + ". Only the rules listed under a written file are gone; the "
            "rest are still live on disk."
        )
    elif report.failed and not report.written:
        lines.append(
            "nothing was written — every file is unchanged on disk."
        )
    return lines


def _render_skipped(report: FixReport) -> list[str]:
    if not report.skipped:
        return []
    lines = ["", f"NOT fixed automatically ({len(report.skipped)}):"]
    for s in report.skipped:
        lines.append(f"  [{s.reason}] {s.rule} @ {s.where}")
        lines.append(f"      {s.detail}")
    return lines


def render(report: FixReport, rescan: ScanReport | None = None) -> str:
    """Operator-facing text. Every skipped finding is printed."""
    lines = _render_actions(report) + _render_skipped(report)
    if rescan is not None:
        if report.partial:
            label = "grade after a PARTIAL apply"
        elif report.written:
            label = "grade after fix"
        else:
            label = "grade now (unchanged — nothing applied)"
        lines += ["", f"{label}: {rescan.grade} ({rescan.score}/100)"]
    if not report.written and report.changed and not report.failed:
        lines += ["", "DRY RUN — re-run with --apply to write these changes."]
    return "\n".join(lines)

"""ClaudeConfigManager — the write side of harness ownership (PR-C2).

C1 gave the vocabulary (spec → manifest → drift); this module closes
the loop: ``assert_ownership`` makes the operator's ``settings.json``
match the runtime spec UNDER THE POLICIES, and nothing else.

- ``own-subset`` (hooks, ``autoMode.hard_deny``): ArkaOS entries are
  ensured — created, timeout-repaired, stale-root-repaired — and
  operator entries on the same surface are preserved verbatim.
- ``seed`` (statusLine, worktree): written only when absent. An
  operator-adopted surface is never reverted by ``assert``; only the
  explicitly named ``restore`` re-seeds it.
- ``operator``: never touched.

REFUSAL IS THE DEFAULT ON ANYTHING UNEXPECTED. A settings file that
cannot be READ is never overwritten, and an operator value whose TYPE
is wrong is left exactly as it is with a ``refused`` action on the
report — coercing either one destroyed configuration silently (QG C2
r1).

Every mutation lands in the audit trail
(``~/.arkaos/audit/harness-mutations.jsonl``) as surface, action, and
either the surface digest or a type name. Settings values and env
values never appear. The manifest (``~/.arkaos/ownership.json``)
records what was asserted and when, per surface, and leaves surfaces
this run deliberately did not assert unstamped: the manifest is
rebuilt from the spec each run, so an earlier timestamp on those
surfaces is not carried over. Writes go through the C1 atomic writer:
a crash mid-assert leaves the previous settings intact.
"""

from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from core.harness import drift, json_store, paths
from core.harness.manifest import OwnershipManifest
from core.harness.spec import HookRegistration, spec_for


@dataclass
class SurfaceAction:
    """One thing assert did (or deliberately did not do) to a surface."""

    surface: str
    # created | repaired | unrepaired | reseeded | adopted-skip
    # | refused | noop
    action: str
    detail: str = ""


@dataclass
class AssertReport:
    """Outcome of one assert/restore/harden run."""

    verb: str
    settings_path: Path
    changed: bool
    actions: list[SurfaceAction] = field(default_factory=list)
    refused: str | None = None  # why nothing was written at all

    def to_dict(self) -> dict:
        return {
            "verb": self.verb,
            "settings_path": str(self.settings_path),
            "changed": self.changed,
            "refused": self.refused,
            "actions": [
                {"surface": a.surface, "action": a.action, "detail": a.detail}
                for a in self.actions
            ],
        }


class ClaudeConfigManager:
    """Asserts and reports ArkaOS ownership of the Claude Code harness."""

    def __init__(
        self,
        home: Path | None = None,
        runtime: str = "claude-code",
        hooks_root: str | None = None,
        platform: str | None = None,
    ):
        self.home = home
        self.runtime = runtime
        self.hooks_root = hooks_root
        self.platform = platform or sys.platform
        self.spec = spec_for(runtime)

    # ── read side ────────────────────────────────────────────────────

    def status(self) -> dict:
        """Drift report + manifest state. Read-only by contract."""
        report = drift.scan(
            home=self.home, runtime=self.runtime,
            platform=self.platform, hooks_root=self.hooks_root,
        )
        manifest, error = _load_manifest(self.home)
        return {
            "drift": report.to_dict(),
            "manifest": manifest.model_dump() if manifest else None,
            "manifest_error": error,
        }

    # ── write side ───────────────────────────────────────────────────

    def assert_ownership(
        self, reseed_adopted: bool = False, verb: str | None = None
    ) -> AssertReport:
        """Make settings.json match the spec under the policies."""
        verb = verb or ("restore" if reseed_adopted else "assert")
        settings_path = paths.claude_settings_path(self.home)
        loaded = json_store.load_json(settings_path)
        report = AssertReport(
            verb=verb, settings_path=settings_path, changed=False
        )
        if loaded.error not in (None, "missing"):
            # A settings file we cannot READ is one we must not
            # OVERWRITE: treating it as a fresh install destroyed env,
            # permissions and plugins with no backup (QG C2 r1,
            # Francisca B2). Refusing is the whole contract.
            report.refused = drift._LOAD_ERROR_DETAIL.get(
                loaded.error or "", f"settings file unusable: {loaded.error}"
            )
            return report
        settings = loaded.data or {}
        before = json.dumps(settings, sort_keys=True)
        self._assert_hooks(settings, report)
        self._assert_hard_deny(settings, report)
        self._assert_seed(settings, report, reseed_adopted)
        report.changed = json.dumps(settings, sort_keys=True) != before
        if report.changed:
            json_store.write_json_atomic(settings_path, settings)
        self._record(report, settings)
        return report

    def restore(self) -> AssertReport:
        """Assert PLUS re-seeding adopted seed surfaces — the
        explicitly named operator override."""
        return self.assert_ownership(reseed_adopted=True)

    def harden(self) -> tuple[AssertReport, str]:
        """Assert, then grade the result with the harness scanner.

        Returns ``(report, grade)``; callers treat a grade below B (or
        any CRITICAL) as failure — no silent half-hardened state.
        """
        from core.governance.harness_scanner import scan

        report = self.assert_ownership(verb="harden")
        scan_report = scan(paths.claude_home(self.home))
        return report, scan_report.grade

    # ── flags ────────────────────────────────────────────────────────

    def read_flags(self) -> dict:
        result = json_store.load_json(paths.arkaos_config_path(self.home))
        hooks = (result.data or {}).get("hooks", {})
        hooks = hooks if isinstance(hooks, dict) else {}
        return {name: hooks.get(name) for name in FLAG_NAMES}

    def set_flag(self, name: str, value: object) -> dict:
        """Set one enforcement flag by explicit name AND value.

        Both are validated: the gates read hardEnforcement and
        specialistEnforcement with ``bool()``, so an unvalidated
        ``"warn"`` turned enforcement ON while the operator asked for
        warn (QG C2 r1, Eduardo B2).
        """
        _validate_flag(name, value)
        config_path = paths.arkaos_config_path(self.home)
        config, hooks = _load_flag_config(config_path)
        hooks[name] = value
        json_store.write_json_atomic(config_path, config)
        _audit_line(
            self.home,
            {"verb": "flags", "surface": f"config:hooks.{name}",
             "action": "set", "detail": type(value).__name__},
        )
        return self.read_flags()

    # ── internals ────────────────────────────────────────────────────

    def _assert_hooks(self, settings: dict, report: AssertReport) -> None:
        hooks = settings.setdefault("hooks", {})
        if not isinstance(hooks, dict):
            report.actions.append(_refusal("settings:hooks", "hooks", hooks))
            return
        accepted = drift._accepted_hook_dirs(
            report.settings_path, self.hooks_root
        )
        for reg in self.spec.hook_registrations:
            if reg.posix_only and self.platform == "win32":
                continue
            if reg.conditional and not drift._script_deployed(
                reg, self.hooks_root
            ):
                continue
            self._ensure_registration(hooks, reg, accepted, report)

    def _ensure_registration(
        self,
        hooks: dict,
        reg: HookRegistration,
        accepted: frozenset[str] | None,
        report: AssertReport,
    ) -> None:
        where = f"hooks.{reg.event}" + (
            f"[matcher={reg.matcher}]" if reg.matcher else ""
        )
        groups = hooks.setdefault(reg.event, [])
        if not isinstance(groups, list):
            report.actions.append(
                _refusal(f"hooks.{reg.event}", reg.event, groups)
            )
            return
        entry = drift._find_entry(reg, groups)
        if entry is None:
            groups.append(self._group_for(reg))
            report.actions.append(SurfaceAction(where, "created"))
            return
        repaired = self._repair_entry(entry, reg, accepted)
        report.actions.append(
            SurfaceAction(where, _repair_action(repaired), ",".join(repaired))
        )

    def _repair_entry(
        self,
        entry: dict,
        reg: HookRegistration,
        accepted: frozenset[str] | None,
    ) -> list[str]:
        """Repairs the divergences drift reports, keyed by the same
        vocabulary as ``drift.entry_divergences``.

        Only timeout and stale-root are repairable today; a new
        divergence kind is recorded as ``unrepairable:<kind>`` rather
        than silently read as a noop.
        """
        repaired = []
        for divergence in drift.entry_divergences(entry, reg, accepted):
            if divergence.startswith("timeout"):
                entry["timeout"] = reg.timeout
                repaired.append("timeout")
            elif divergence.startswith("stale-root"):
                entry["command"] = self._command_for(
                    reg, entry.get("command")
                )
                repaired.append("stale-root")
            else:
                repaired.append(f"unrepairable:{_divergence_kind(divergence)}")
        return repaired

    def _group_for(self, reg: HookRegistration) -> dict:
        inner = {
            "type": "command",
            "command": self._command_for(reg),
            "timeout": reg.timeout,
        }
        if self.platform == "win32":
            inner["shell"] = "powershell"
        group: dict = {"hooks": [inner]}
        if reg.matcher:
            group["matcher"] = reg.matcher
        return group

    def _command_for(self, reg: HookRegistration, current: object = "") -> str:
        """Path to ``reg``'s script in the INSTALLED hooks dir.

        The suffix of an existing entry wins when there is one:
        rewriting a deployed ``.cjs`` to ``.sh`` silently dropped the
        Node fastpath (QG C2 r1 B1).
        """
        existing = drift.hook_command_path(current).suffix
        default = ".ps1" if self.platform == "win32" else ".sh"
        ext = existing if existing in (".sh", ".ps1", ".cjs") else default
        return str(self._hooks_dir() / f"{reg.script}{ext}")

    def _hooks_dir(self) -> Path:
        """Where a written command must point.

        The INSTALLED tree (``~/.arkaos/config/hooks``) whenever it
        holds the deployment, because the resolved root is routinely an
        npx cache that ``npm cache clean`` purges — pointing entries at
        the resolved root left every created and repaired command
        naming a directory that can vanish (QG C2 r2, Francisca B1).
        The resolved root is the fallback for a source checkout with
        no install.
        """
        installed = paths.arkaos_home(self.home) / "config" / "hooks"
        try:
            if installed.is_dir():
                return installed
        except OSError:
            pass
        return paths.hooks_dir(self.hooks_root)

    def _assert_hard_deny(self, settings: dict, report: AssertReport) -> None:
        auto_mode = settings.setdefault("autoMode", {})
        if not isinstance(auto_mode, dict):
            report.actions.append(
                _refusal("settings:autoMode.hard_deny", "autoMode", auto_mode)
            )
            return
        existing = auto_mode.get("hard_deny")
        if existing is not None and not isinstance(existing, list):
            report.actions.append(
                _refusal(
                    "settings:autoMode.hard_deny", "hard_deny", existing
                )
            )
            return
        existing = existing or []
        merged = self._merged_deny_rules(existing)
        if merged != existing:
            auto_mode["hard_deny"] = merged
            report.actions.append(
                SurfaceAction(
                    "settings:autoMode.hard_deny", "repaired",
                    f"{len(merged) - len(existing)} rule(s) added",
                )
            )
        else:
            report.actions.append(
                SurfaceAction("settings:autoMode.hard_deny", "noop")
            )

    def _merged_deny_rules(self, existing: list) -> list:
        """Spec rules + operator extensions merged into ``existing``.

        Non-string members are excluded from the MERGE and appended
        back untouched: ``merge_unique`` hashes its inputs, so a dict
        member raised TypeError out of a never-raises path (QG C2 r1,
        Francisca B3), and dropping it would delete operator data.
        """
        strings = [r for r in existing if isinstance(r, str)]
        others = [r for r in existing if not isinstance(r, str)]
        # Operator entries first — first occurrence wins, so operator
        # order is preserved (the installer mergeUnique contract).
        merged = json_store.merge_unique(
            strings, list(self.spec.hard_deny_rules),
            _user_deny_extensions(self.home),
        )
        return merged + others if others else merged

    def _assert_seed(
        self, settings: dict, report: AssertReport, reseed: bool
    ) -> None:
        for surface, key, default, is_ours in _seed_surfaces(self):
            current = settings.get(key)
            if current is None:
                settings[key] = default
                report.actions.append(SurfaceAction(surface, "created"))
            elif is_ours(current):
                report.actions.append(SurfaceAction(surface, "noop"))
            elif reseed:
                settings[key] = default
                report.actions.append(SurfaceAction(surface, "reseeded"))
            else:
                report.actions.append(
                    SurfaceAction(
                        surface, "adopted-skip",
                        "operator-configured; assert never reverts seed",
                    )
                )

    def _record(self, report: AssertReport, settings: dict) -> None:
        stamp = datetime.now(UTC).isoformat()
        skipped = {
            a.surface for a in report.actions
            if a.action in ("adopted-skip", "refused")
        }
        manifest = OwnershipManifest.default(self.runtime)
        for record in manifest.surfaces:
            # A surface ArkaOS deliberately did NOT assert must not be
            # stamped as asserted — the manifest contradicted the audit
            # trail for adopted seeds (QG C2 r1, Eduardo B3).
            if record.surface in skipped:
                continue
            record.last_asserted = stamp
            record.content_sha256 = _surface_digest(settings, record.surface)
        json_store.write_json_atomic(
            paths.ownership_manifest_path(self.home), manifest.model_dump()
        )
        for action in report.actions:
            if action.action in ("noop", "adopted-skip"):
                continue
            _audit_line(
                self.home,
                {"verb": report.verb, "surface": action.surface,
                 "action": action.action, "detail": action.detail,
                 "content_sha256": _surface_digest(settings, action.surface)},
            )


FLAG_NAMES: tuple[str, ...] = (
    "hardEnforcement", "frontendGate", "specialistEnforcement",
)

# Each flag's OWN vocabulary. hardEnforcement and specialistEnforcement
# are read with bool() by their gates, so a stray string like "warn"
# silently means ON — the operator asked for warn and got hard (QG C2
# r1, Eduardo B2). frontendGate is the tri-state one.
FLAG_VALUES: dict[str, tuple] = {
    "hardEnforcement": (True, False),
    "specialistEnforcement": (True, False),
    "frontendGate": ("off", "warn", "hard"),
}


def _divergence_kind(divergence: str) -> str:
    """The KIND word of a divergence drift reports.

    First word only: a divergence written without a ``kind: detail``
    colon would otherwise copy its whole message — which can embed an
    operator value — into the audit detail (QG C2 r3, Eduardo).
    """
    return divergence.split(":")[0].split()[0]


def _repair_action(repaired: list[str]) -> str:
    """``repaired`` only when something actually was.

    An entry whose every divergence is unhandled was labelled
    ``repaired`` with detail ``unrepairable:<kind>`` — the CLI printed
    "repaired: hooks.Stop (unrepairable:shell)" and the audit trail
    said repaired for a surface nothing repaired. That is the
    silent-success pattern this module exists to kill (QG C2 r3,
    Eduardo). A MIXED entry keeps ``repaired`` and carries the
    unrepairable kind in detail.
    """
    if not repaired:
        return "noop"
    if all(item.startswith("unrepairable:") for item in repaired):
        return "unrepaired"
    return "repaired"


def _validate_flag(name: str, value: object) -> None:
    if name not in FLAG_NAMES:
        raise ValueError(
            f"unknown flag {name!r}; known: {', '.join(FLAG_NAMES)}"
        )
    allowed = FLAG_VALUES[name]
    if value not in allowed:
        raise ValueError(
            f"invalid value {value!r} for {name}; allowed: "
            f"{', '.join(str(a).lower() for a in allowed)}"
        )


def _load_flag_config(config_path: Path) -> tuple[dict, dict]:
    """``(config, hooks)`` — refuses rather than replacing either."""
    result = json_store.load_json(config_path)
    if result.error not in (None, "missing"):
        raise ValueError(
            f"~/.arkaos/config.json is {result.error} — refusing to "
            f"overwrite it"
        )
    config = result.data or {}
    hooks = config.get("hooks")
    if hooks is None:
        hooks = config["hooks"] = {}
    elif not isinstance(hooks, dict):
        raise ValueError(
            f"config.hooks is {type(hooks).__name__}, expected object — "
            f"refusing to replace it"
        )
    return config, hooks


def _surface_digest(settings: dict, surface: str) -> str:
    """Digest of the content on ``surface``.

    Per-surface by construction: a whole-file digest moved whenever the
    operator touched anything at all (QG C2 r1, Francisca B5 / Eduardo
    B3). On own-subset surfaces the digest still covers the operator
    entries preserved alongside the ArkaOS ones — that is the surface,
    and separating them is not something this field claims to do.
    """
    owned: object
    if surface == "settings:hooks":
        owned = settings.get("hooks")
    elif surface == "settings:autoMode.hard_deny":
        auto = settings.get("autoMode")
        owned = auto.get("hard_deny") if isinstance(auto, dict) else None
    elif surface.startswith("hooks."):
        owned = (settings.get("hooks") or {}).get(
            surface.split("[", 1)[0].removeprefix("hooks.")
        )
    else:
        owned = settings.get(surface.removeprefix("settings:"))
    return hashlib.sha256(
        json.dumps(owned, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


def _refusal(surface: str, key: str, value: object) -> SurfaceAction:
    """Recorded when an operator value has an unexpected TYPE.

    Coercing it to an empty container deleted operator hooks and deny
    rules silently (QG C2 r1, Francisca B4). A type mismatch is a
    refusal to touch the surface, never a repair.
    """
    return SurfaceAction(
        surface, "refused",
        f"{key} is {type(value).__name__}, expected "
        f"{'list' if key not in ('hooks', 'autoMode') else 'object'} — "
        f"left untouched",
    )


def _load_manifest(home: Path | None):
    from core.harness.manifest import load_manifest

    return load_manifest(paths.ownership_manifest_path(home))


def _user_deny_extensions(home: Path | None) -> list[str]:
    result = json_store.load_json(paths.hard_deny_extension_path(home))
    raw = (result.data or {}).get("hard_deny", [])
    if not isinstance(raw, list):
        return []
    return [r for r in raw if isinstance(r, str) and r]


def _seed_surfaces(manager: ClaudeConfigManager):
    statusline = _statusline_default(manager)
    return (
        (
            "settings:statusLine", "statusLine", statusline,
            drift._is_arkaos_statusline,
        ),
        (
            "settings:worktree", "worktree", {"baseRef": "head"},
            lambda v: isinstance(v, dict) and v.get("baseRef") == "head",
        ),
    )


def _statusline_default(manager: ClaudeConfigManager) -> dict:
    name = "statusline.ps1" if manager.platform == "win32" else "statusline.sh"
    script = manager._hooks_dir().parent / name
    command = (
        f'powershell -NoProfile -NonInteractive -ExecutionPolicy Bypass '
        f'-File "{script}"'
        if manager.platform == "win32"
        else str(script)
    )
    return {"type": "command", "command": command, "padding": 2}


def _audit_line(home: Path | None, entry: dict) -> None:
    """Append one mutation line: surface, action, and either the
    owned-content digest or a type name. Settings values and env values
    never appear.

    Best-effort by design: the mutation itself already happened
    atomically, and a failed audit write must not corrupt or roll back
    the settings — unlike egress, nothing leaves the machine here.
    """
    path = paths.harness_audit_log_path(home)
    line = json.dumps(
        {"ts": datetime.now(UTC).isoformat(), **entry}, sort_keys=True
    )
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    except OSError:
        pass

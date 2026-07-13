"""Authority brief — the write rules a session must know BEFORE it writes.

The 2026-07-12 incident: a session was blocked writing a Laravel
controller and, never having been told the rule existed, invented a
"documented bug" to justify a bypass. Grep confirms the gap: ownership
and ``specialist-bypass`` appear NOWHERE in CLAUDE.md, arka/SKILL.md,
flow/SKILL.md or constitution.yaml. The deny message was the first and
only place a session ever learned any of it.

This module renders the ``[ARKA:AUTHORITY]`` block the SessionStart hook
injects. Everything is GENERATED from ``config/agent-ownership.yaml`` +
``config/agent-roster.json`` + the agents actually deployed on THIS
machine — never hand-typed.

Two rules this file learned the hard way (QG, redo 1):

1. **Relevance is decided by the FULL literal spine, never its first
   segment.** The first cut matched ``**/app/Http/Controllers/**`` in
   this repo because a directory called ``dashboard/app`` exists — so it
   taught a session five Laravel rules that govern nothing here.
2. **Never truncate in silence.** The same cut capped the list at 8 and
   dropped ``core/workflow/**/*.py`` and ``core/agents/**/*.py`` — the
   rules that own the very files that PR was editing — under a heading
   that claims "Owned paths in THIS project". A brief that hides the
   rules that apply is the incident, re-delivered as its own fix.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
OWNERSHIP_YAML = REPO_ROOT / "config" / "agent-ownership.yaml"
ROSTER_JSON = REPO_ROOT / "config" / "agent-roster.json"

# Enough to state every rule that really applies to a project this size
# (arka-os itself renders 14). Anything beyond is COUNTED, never dropped.
_MAX_RULES = 16
_MAX_FIELD = 120
_GLOB_CHARS = ("*", "?", "[")
# The brief lands in a system prompt. A pattern is operator-editable YAML
# (agent-ownership.yaml is `lead_allowed`), so a newline in it could forge
# an authority line — OWASP LLM01. Control bytes never reach the prompt.
_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")


def _load(path: Path) -> dict:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    try:
        data = (
            json.loads(text) if path.suffix == ".json" else yaml.safe_load(text)
        )
    except (json.JSONDecodeError, yaml.YAMLError):
        return {}
    return data if isinstance(data, dict) else {}


def _clean(value: str) -> str:
    """Strip control bytes and bound the length — prompt-injection guard."""
    return _CONTROL_RE.sub("", str(value))[:_MAX_FIELD]


def deployed_agents(agents_dirs: list[Path] | None = None) -> set[str]:
    """Slugs the Task tool can actually dispatch on this machine."""
    dirs = agents_dirs or [
        Path.home() / ".claude" / "agents",
        Path.cwd() / ".claude" / "agents",
    ]
    found: set[str] = set()
    for base in dirs:
        try:
            for md in base.glob("*.md"):
                found.add(md.stem.removeprefix("arka-"))
        except OSError:
            continue
    return found


def _spine(pattern: str) -> list[str]:
    """The literal path segments of a glob: `**/app/Http/Controllers/**`
    -> ['app', 'Http', 'Controllers']; `**/*.vue` -> []."""
    return [
        part for part in pattern.split("/")
        if part and not any(ch in part for ch in _GLOB_CHARS)
    ]


def rule_applies(pattern: str, root: Path) -> bool:
    """Does this rule govern anything in `root`?

    The FULL spine must exist — checking only its first segment is what
    made `**/app/Http/Controllers/**` look relevant here (a `dashboard/app`
    directory exists) while the rules that actually govern the repo were
    pushed out of the list. Extension-only rules always apply: they cost
    one line and are honest ("write a .vue and frontend-dev owns it").
    """
    spine = _spine(pattern)
    if not spine:
        return True
    joined = Path(*spine)
    try:
        if (root / joined).exists():
            return True
        # One level down covers monorepo layouts (dashboard/app/…).
        return any(
            (child / joined).exists()
            for child in root.iterdir()
            if child.is_dir() and not child.name.startswith(".")
        )
    except OSError:
        return False


def applicable_rules(rules: list[dict], root: Path) -> list[dict]:
    return [
        rule for rule in rules
        if isinstance(rule, dict)
        and rule.get("pattern")
        and rule.get("owners")
        and "*" not in rule["owners"]
        and rule_applies(str(rule["pattern"]), root)
    ]


def _dispatch_status(named: set[str], owners_meta: dict,
                     dispatchable: set[str]) -> list[str]:
    status: list[str] = []
    for slug in sorted(named):
        human = str(owners_meta.get(slug, {}).get("human_name", ""))
        label = f"{slug} ({human.split()[0]})" if human else slug
        status.append(
            f"{label} ok" if slug in dispatchable else f"{label} MISSING"
        )
    return status


def render(cwd: str | Path | None = None,
           agents_dirs: list[Path] | None = None) -> str:
    """The [ARKA:AUTHORITY] block, or "" when there is nothing to say."""
    ownership = _load(OWNERSHIP_YAML)
    roster = _load(ROSTER_JSON)
    rules = ownership.get("ownership") or []
    owners_meta = roster.get("gate_owners") or {}
    if not isinstance(rules, list) or not owners_meta:
        return ""

    root = Path(cwd) if cwd else Path.cwd()
    relevant = applicable_rules(rules, root)
    if not relevant:
        return ""
    shown, overflow = relevant[:_MAX_RULES], len(relevant) - _MAX_RULES

    lines = [
        "[ARKA:AUTHORITY] Write permissions (enforced by a PreToolUse gate)",
        "1. Your last [arka:routing] / [arka:dispatch] marker is an "
        "AUTHORIZATION TOKEN a gate reads before every Write/Edit. It is "
        "not narration.",
        "2. Owned paths in THIS project (first match wins):",
    ]
    named: set[str] = set()
    for rule in shown:
        owners = [_clean(o) for o in rule["owners"]]
        named.update(owners)
        lines.append(
            f"     {_clean(rule['pattern']):<26s} -> {', '.join(owners)}"
        )
    if overflow > 0:
        lines.append(
            f"     (+{overflow} more — see config/agent-ownership.yaml)"
        )

    status = _dispatch_status(named, owners_meta, deployed_agents(agents_dirs))
    lines.append(
        f"3. Dispatchable here (Task subagent_type): {', '.join(status)}"
    )
    if any(entry.endswith("MISSING") for entry in status):
        lines.append("   MISSING -> run `npx arkaos update` (never bypass).")
    lines.append(
        "4. The dispatched specialist writes with NO block. Retrying a "
        "blocked Write never works — dispatch instead."
    )
    return "\n".join(lines)


def main() -> int:
    brief = render()
    print(brief or "(no ownership rules apply to this directory)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

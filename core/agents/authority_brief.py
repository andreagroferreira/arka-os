"""Authority brief — the write rules a session must know BEFORE it writes.

The 2026-07-12 incident: a session was blocked writing a Laravel
controller, and — never having been told the rule existed — invented a
"documented bug" to justify a bypass. Grep confirms the gap: ownership
and ``specialist-bypass`` appear NOWHERE in CLAUDE.md, arka/SKILL.md,
flow/SKILL.md or constitution.yaml. The deny message was the first and
only place a session ever learned any of it, and it taught the bypass
in the same breath as the dispatch.

This module renders the ``[ARKA:AUTHORITY]`` block the SessionStart hook
injects. Everything in it is GENERATED (docs_stats/gate_manifest
precedent) from ``config/agent-ownership.yaml`` +
``config/agent-roster.json`` + the agents actually deployed on THIS
machine — never hand-typed, so it cannot drift into a lie.

Scoped to the project: rules whose glob cannot match anything in ``cwd``
are dropped, so a Nuxt repo never reads Laravel rules. Typical cost is
6-10 lines.
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
OWNERSHIP_YAML = REPO_ROOT / "config" / "agent-ownership.yaml"
ROSTER_JSON = REPO_ROOT / "config" / "agent-roster.json"
_MAX_RULES = 8


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


def _rule_applies(pattern: str, cwd: Path) -> bool:
    """Cheap relevance test: does the pattern's literal spine exist here?

    ``**/app/Http/Controllers/**`` -> looks for ``app/Http/Controllers``.
    Extension-only patterns (``**/*.vue``) always apply — checking every
    file would cost more than the block itself.
    """
    spine = [
        part for part in pattern.split("/")
        if part and "*" not in part and "?" not in part and "." not in part
    ]
    if not spine:
        return True
    try:
        return any(
            (cwd / spine[0]).exists()
            or any(cwd.glob(f"*/{spine[0]}"))
            for _ in (0,)
        )
    except OSError:
        return True


def render(cwd: str | Path | None = None, agents_dirs=None) -> str:
    """The [ARKA:AUTHORITY] block, or "" when there is nothing to say."""
    ownership = _load(OWNERSHIP_YAML)
    roster = _load(ROSTER_JSON)
    rules = ownership.get("ownership") or []
    owners_meta = roster.get("gate_owners") or {}
    if not rules or not owners_meta:
        return ""

    root = Path(cwd) if cwd else Path.cwd()
    dispatchable = deployed_agents(agents_dirs)
    relevant = [
        rule for rule in rules
        if rule.get("owners") and "*" not in rule["owners"]
        and _rule_applies(str(rule.get("pattern", "")), root)
    ][:_MAX_RULES]
    if not relevant:
        return ""

    lines = [
        "[ARKA:AUTHORITY] Write permissions (enforced by a PreToolUse gate)",
        "1. Your last [arka:routing] / [arka:dispatch] marker is an "
        "AUTHORIZATION TOKEN a gate reads before every Write/Edit. It is "
        "not narration.",
        "2. Owned paths in THIS project (first match wins):",
    ]
    named: set[str] = set()
    for rule in relevant:
        owners = ", ".join(rule["owners"])
        named.update(rule["owners"])
        lines.append(f"     {rule['pattern']:<42s} -> {owners}")

    status = []
    for slug in sorted(named):
        human = owners_meta.get(slug, {}).get("human_name", "")
        label = f"{slug} ({human.split()[0]})" if human else slug
        status.append(
            f"{label} ok" if slug in dispatchable else f"{label} MISSING"
        )
    lines.append(f"3. Dispatchable here (Task subagent_type): "
                 f"{', '.join(status)}")
    if any("MISSING" in s for s in status):
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

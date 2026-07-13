"""Agent roster manifest — every gate owner must be dispatchable.

Root cause this kills (operator incident, 2026-07-12): the specialist
gate blocked a lead from writing ``app/Http/Controllers/`` and told it
to dispatch ``senior-dev`` or ``backend-dev`` — but 4 of the 7 owners
named in ``config/agent-ownership.yaml`` (backend-dev, dba, devops-eng,
security-eng) were NOT dispatchable on real machines: they exist only
as department YAML, and the installer's agent deploy only ships ``.md``
files. A gate that demands an owner nobody can invoke is a dead end,
and dead ends teach sessions to rationalize bypasses.

This module is the single writer of ``config/agent-roster.json``:

    python -m core.agents.roster_manifest

For every owner the ownership rules name, it resolves a dispatchable
source — a hand-authored ``departments/*/agents/<slug>.md`` (legacy,
wins because it may be hand-tuned) or the compiled
``config/claude-agents/<slug>.md`` (generated from the agent YAML by
the behavioral compiler) — and REFUSES to emit when neither exists:
a missing source is a build-time failure, never a runtime dead end.
``installer/skill-deploy.js`` reads the manifest and deploys every
gate owner; ``tests/python/test_agent_roster.py`` drift-gates it.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
OWNERSHIP_YAML = REPO_ROOT / "config" / "agent-ownership.yaml"
COMPILED_DIR = REPO_ROOT / "config" / "claude-agents"
DEPARTMENTS_DIR = REPO_ROOT / "departments"
ROSTER_JSON = REPO_ROOT / "config" / "agent-roster.json"

_NAME_RE = re.compile(r"^name:\s*(\S+)\s*$", re.MULTILINE)


def gate_owners() -> list[str]:
    """Every owner slug the ownership rules can demand (never ``*``)."""
    config = yaml.safe_load(OWNERSHIP_YAML.read_text(encoding="utf-8"))
    return sorted({
        owner
        for rule in config["ownership"]
        for owner in (rule.get("owners") or [])
        if owner != "*"
    })


def _frontmatter_name(md_path: Path) -> str | None:
    match = _NAME_RE.search(md_path.read_text(encoding="utf-8")[:2000])
    return match.group(1) if match else None


def _resolve_source(slug: str) -> Path | None:
    """Dispatchable source for a slug: hand-authored dept .md wins,
    compiled claude-agents .md is the generated fallback."""
    for candidate in sorted(DEPARTMENTS_DIR.glob(f"*/agents/{slug}.md")):
        if _frontmatter_name(candidate) == slug:
            return candidate
    compiled = COMPILED_DIR / f"{slug}.md"
    if compiled.is_file() and _frontmatter_name(compiled) == slug:
        return compiled
    return None


def _agent_yaml(slug: str) -> Path | None:
    matches = sorted(DEPARTMENTS_DIR.glob(f"*/agents/**/{slug}.yaml"))
    return matches[0] if matches else None


def _human_name(slug: str) -> str:
    source = _agent_yaml(slug)
    if source is None:
        return ""
    try:
        data = yaml.safe_load(source.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        return ""
    return str(data.get("name") or "") if isinstance(data, dict) else ""


def _first_name(human: str) -> str:
    """'Andre — Backend Core Lead' -> 'andre'."""
    return human.split()[0].split("—")[0].strip().lower() if human else ""


def build_aliases(entries: dict[str, dict]) -> dict[str, str]:
    """First-name -> owner slug, resolved WITHIN the gate-owner set.

    Sessions route by human name (``[arka:dispatch] paulo -> diana``) but
    ownership rules name slugs (``frontend-dev``). Unresolved, that
    mismatch blocked the RIGHT specialist from her own files: 22 of 189
    measured blocks. (The 22 `senior-dev` blocks are a separate, still
    open class: there the slug IS the persona, so no alias helps.)

    Scoping to gate owners is what makes this safe. Globally, ``diana``
    is ambiguous (frontend-dev AND hr-specialist) and so is ``andre``
    (backend-dev AND growth-engineer) — a naive first-name alias would
    trade one bug for a worse one. Among the owners the gate can
    actually demand, both are unique. Anything still ambiguous here is
    REFUSED, never guessed.
    """
    by_first: dict[str, set[str]] = {}
    for slug in entries:
        first = _first_name(_human_name(slug))
        if first:
            by_first.setdefault(first, set()).add(slug)
    return {
        first: next(iter(slugs))
        for first, slugs in sorted(by_first.items())
        if len(slugs) == 1
    }


def build_roster() -> dict:
    owners = gate_owners()
    entries: dict[str, dict] = {}
    ghosts: list[str] = []
    for slug in owners:
        source = _resolve_source(slug)
        if source is None:
            ghosts.append(slug)
            continue
        entries[slug] = {
            "source": str(source.relative_to(REPO_ROOT)),
            "compiled": source.parent == COMPILED_DIR,
            "human_name": _human_name(slug),
        }
    if ghosts:
        raise ValueError(
            f"ownership rules demand owners with NO dispatchable source: "
            f"{ghosts} — author the agent (YAML + compiler run) or fix "
            f"config/agent-ownership.yaml; a gate must never demand an "
            f"owner nobody can invoke"
        )
    aliases = build_aliases(entries)
    ambiguous = sorted(
        first
        for first in {
            _first_name(e["human_name"]) for e in entries.values()
        }
        if first and first not in aliases
    )
    return {
        "_meta": {
            "generator": "core/agents/roster_manifest.py",
            "purpose": (
                "every specialist-gate owner resolves to a dispatchable "
                "agent source; installer/skill-deploy.js deploys these"
            ),
        },
        "gate_owners": entries,
        "aliases": aliases,
        "ambiguous_first_names": ambiguous,
    }


def render() -> str:
    return json.dumps(build_roster(), indent=2, sort_keys=True) + "\n"


def main() -> int:
    ROSTER_JSON.write_text(render(), encoding="utf-8")
    print(f"agent roster written: {ROSTER_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

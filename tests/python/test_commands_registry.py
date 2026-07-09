"""Drift lock for knowledge/commands-registry.json (M2 consolidation).

The registry sat 30+ releases stale (135 commands from the 190-skill
era) because nothing locked it; the follow-up promised in the regen PR
landed 2026-07-09: the generator is now the deterministic python
``core/registry/generator.py`` (repo sources only, no machine-local
skills, UTC timestamp isolated in ``_meta.generated``), so this file
carries a REAL committed-vs-regen drift gate plus the sanity checks.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from core.registry.generator import generate_commands_registry

_ROOT = Path(__file__).resolve().parents[2]
_REGISTRY = _ROOT / "knowledge" / "commands-registry.json"

_ANCHORS = ("dev-feature", "dev-spec-validate", "dev-spec-list", "arka-costs")
_KEBAB = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def _load() -> dict:
    return json.loads(_REGISTRY.read_text(encoding="utf-8"))


def test_registry_parses_with_meta():
    data = _load()
    assert data["_meta"]["generator"] == "core/registry/generator.py"
    assert data["_meta"]["version"] == "3.0.0"
    assert data["_meta"]["total_commands"] == len(data["commands"])


def test_committed_registry_matches_fresh_regen(tmp_path):
    """Content equality with a fresh regen (only _meta.generated differs).

    Same drift gate as the agents registry — regenerate with
    `arka-py -m core.registry.generator` after editing any SKILL.md
    command table.
    """
    committed = _load()
    fresh = generate_commands_registry(_ROOT, tmp_path / "regen.json")
    fresh = json.loads(json.dumps(fresh))

    committed_meta = {
        k: v for k, v in committed["_meta"].items() if k != "generated"
    }
    fresh_meta = {k: v for k, v in fresh["_meta"].items() if k != "generated"}
    assert committed_meta == fresh_meta, (
        "commands-registry.json _meta drifted — regenerate with "
        "`arka-py -m core.registry.generator`."
    )
    assert committed["commands"] == fresh["commands"], (
        "commands-registry.json content drifted from the SKILL.md tables — "
        "regenerate with `arka-py -m core.registry.generator`."
    )


def test_legacy_artifacts_do_not_resurrect():
    """v2 file and bash generator were retired in the M2 consolidation."""
    assert not (_ROOT / "knowledge" / "commands-registry-v2.json").exists(), (
        "commands-registry-v2.json resurfaced — the canonical registry is "
        "commands-registry.json (core/registry/generator.py)."
    )
    assert not (_ROOT / "bin" / "arka-registry-gen").exists(), (
        "bin/arka-registry-gen resurfaced — the generator is "
        "core/registry/generator.py (bin/arka commands rebuild wraps it)."
    )


def test_registry_is_not_stale():
    # 135 was the v2.39.0-era count; today's surface generates 262.
    # Growth-safe floor: a regen below this means the generator broke,
    # not that the surface shrank.
    assert len(_load()["commands"]) >= 200


def test_no_duplicate_ids():
    ids = [c["id"] for c in _load()["commands"]]
    assert len(ids) == len(set(ids))


def test_anchor_commands_present():
    ids = {c["id"] for c in _load()["commands"]}
    for anchor in _ANCHORS:
        assert anchor in ids, anchor


def test_command_shape():
    for cmd in _load()["commands"]:
        assert cmd["command"].startswith("/"), cmd["id"]
        assert _KEBAB.match(cmd["id"]), cmd["id"]
        desc = cmd["description"].strip()
        assert desc, cmd["id"]
        # QG blocker lock (2026-07-09): descriptions are user-facing
        # prose — a wrong-column extraction ships git URLs, TBD
        # placeholders, or table fragments as command help.
        assert not desc.startswith("`"), (cmd["id"], desc)
        assert "http://" not in desc and "https://" not in desc, cmd["id"]
        assert "TBD" not in desc, (cmd["id"], desc)


def test_every_department_is_represented():
    ids = {c["department"] for c in _load()["commands"]}
    expected = {
        "arka", "dev", "mkt", "brand", "fin", "strat", "ecom", "kb",
        "ops", "pm", "saas", "landing", "content", "community", "sales",
    }
    missing = expected - ids
    assert not missing, f"departments absent from registry: {missing}"

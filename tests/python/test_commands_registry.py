"""Sanity lock for knowledge/commands-registry.json (regen PR, 2026-07-09).

The v1 registry sat 30+ releases stale (135 commands from the 190-skill
era) because nothing locked it. This is a SANITY lock, not a byte lock —
the generator (bin/arka-registry-gen) stamps a timestamp and may include
machine-local arka-ext-*/arka-pro-* skills, so byte equality is not
CI-reproducible. A deterministic python port of the generator is the
follow-up that would enable a real drift gate.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_REGISTRY = _ROOT / "knowledge" / "commands-registry.json"

_ANCHORS = ("dev-feature", "dev-spec-validate", "dev-spec-list", "arka-costs")
_KEBAB = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def _load() -> dict:
    return json.loads(_REGISTRY.read_text(encoding="utf-8"))


def test_registry_parses_with_meta():
    data = _load()
    assert data["_meta"]["generator"] == "bin/arka-registry-gen"
    assert data["_meta"]["total_commands"] == len(data["commands"])


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

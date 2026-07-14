"""Agent provenance — supply-chain lineage for every agent YAML.

The skill tree got provenance in v4.17.0; agents did not, and the ECC
teardown puts ~15 derived agents on the roadmap. An ECC agent ported
today would land with exactly the hole skill provenance closes: no
origin, no licence trail, indistinguishable from an ArkaOS original.
This is the agent-side mirror, and it must land before the first agent
port.

An agent YAML may carry a top-level ``provenance`` block:

    id: silent-failure-hunter
    name: ...
    provenance:
      origin: ecc-derived
      source: https://github.com/affaan-m/ecc
      license: MIT

Absent means first-party. The validation rules are the shared
``core.provenance`` core (https source, licence required for derived,
no trail on ``arkaos``). This module only reads the YAML.

As with skills, no parser can see the omission vector — a port that
never writes the block reads as first-party. ``config/agents-provenance.yaml``
classifies every agent as baseline, derived, or self-declaring, and
``tests/python/test_agent_provenance.py`` fails CI on any agent that is
none of the three.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from core.provenance import (
    FIRST_PARTY,
    Provenance,
    ProvenanceError,
    provenance_from_block,
)

__all__ = [
    "FIRST_PARTY",
    "Provenance",
    "ProvenanceError",
    "agent_provenance",
    "declares_provenance",
    "provenance_from_yaml",
    "provenance_issues_from_yaml",
]


def _provenance_block(data: dict) -> dict | None:
    """The ``provenance`` mapping from a loaded agent YAML.

    Present-but-not-a-mapping is an error, never a silent first-party
    fallback — the same fail-closed rule the skill parser uses.
    """
    if "provenance" not in data:
        return None
    block = data["provenance"]
    if not isinstance(block, dict):
        raise ProvenanceError(
            "provenance must be a mapping of origin/source/license"
        )
    return block


def provenance_from_yaml(data: dict) -> Provenance:
    """Parse the provenance of a loaded agent YAML mapping.

    Raises ``ProvenanceError``/``ValidationError`` when the block is
    present but incoherent.
    """
    if not isinstance(data, dict):
        raise ProvenanceError("agent YAML is not a mapping")
    return provenance_from_block(_provenance_block(data))


def declares_provenance(data: dict) -> bool:
    """Did the author WRITE a provenance block? (vs the first-party
    default). The classification control needs this distinction, which
    ``provenance_from_yaml`` collapses."""
    if not isinstance(data, dict):
        return False
    try:
        return _provenance_block(data) is not None
    except ProvenanceError:
        return True  # broken but attempted


def _load_yaml(path: Path) -> dict:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ProvenanceError(f"{path}: cannot read agent YAML — {exc}") from exc
    return data if isinstance(data, dict) else {}


def agent_provenance(path: str | Path) -> Provenance:
    """Provenance of an agent YAML file. Raises on an incoherent block."""
    return provenance_from_yaml(_load_yaml(Path(path)))


def provenance_issues_from_yaml(data: dict) -> list[str]:
    """Non-raising validation of a loaded agent YAML. Empty = clean."""
    from pydantic import ValidationError
    try:
        provenance_from_yaml(data)
    except ProvenanceError as exc:
        return [str(exc)]
    except ValidationError as exc:
        return [
            err["msg"].removeprefix("Value error, ") for err in exc.errors()
        ]
    return []

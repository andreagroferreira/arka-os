"""Skill provenance — supply-chain lineage for every SKILL.md.

A skill either originates in ArkaOS or it is derived from someone
else's work. Third-party lineage is a security property, not trivia: a
skill tree with no origin field cannot be audited after the fact, and
"which licence is this under?" becomes unanswerable the moment the
author who ported it moves on.

Contract (opt-in, absence means first-party):

    ---
    name: dev/example-skill
    description: ...
    allowed-tools: [Read, Grep, Glob]
    metadata:
      origin: vendor-derived
      source: https://example.com/upstream
      license: MIT
    ---

``origin`` is a lowercase slug (``^[a-z][a-z0-9-]*$``). ``arkaos`` — or
no metadata block at all — is first-party and needs nothing else. ANY
other origin MUST declare ``source`` (an https URL) and ``license``.

**Fail closed.** A block that is present but unusable — unparseable
YAML, a tab-indented body, ``metadata`` bound to a scalar, a misspelt
key (``metadatas:``, ``orgin:``) — is an ERROR, never a silent fall
back to first-party. Laundering a derived skill into ``arkaos`` by
typo is the one failure this module exists to prevent.

No parser can see the last vector: a port that simply never writes the
block reads as first-party, and a typo net will always have a hole
(``metdata:``, ``provenance:``, ``metadata: {}``). Omission is closed
somewhere else — ``config/skills-provenance.yaml`` classifies every
skill in the tree as baseline, derived, or self-declaring, and
``tests/python/test_skill_provenance.py`` fails CI on any skill that is
none of the three. A new skill must therefore say what it is. This
module cannot enforce that and does not claim to.

Consumed by ``scripts/skill_validator.py`` (per-skill score) and
``scripts/marketplace_gen.py`` (``knowledge/skills-manifest.json``,
which carries the full origin/source/licence triple, not just origin).

The artifact-agnostic core — the model, the constants, the block
validator — lives in ``core/provenance.py`` and is shared with agent
provenance (``core/agents/provenance.py``). This module is only the
SKILL.md-frontmatter reader. ``SkillProvenance`` is re-exported as an
alias of the generic ``Provenance`` so existing imports keep working.
"""

from __future__ import annotations

import re

import yaml
from pydantic import ValidationError

from core.provenance import (
    FIRST_PARTY,
    METADATA_FIELDS,
    Provenance,
    ProvenanceError,
    provenance_from_block,
)

# Back-compat alias: a skill's provenance is just Provenance.
SkillProvenance = Provenance

__all__ = [
    "FIRST_PARTY",
    "METADATA_FIELDS",
    "Provenance",
    "ProvenanceError",
    "SkillProvenance",
    "declares_provenance",
    "parse_provenance",
    "provenance_issues",
]

_FRONTMATTER = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)
# Near-misses for `metadata` — a typo must not read as "no block".
_METADATA_TYPO = re.compile(r"^meta[-_ ]?datas?$", re.IGNORECASE)


def _frontmatter(content: str) -> dict:
    """The YAML frontmatter mapping. Raises when present but broken."""
    match = _FRONTMATTER.match(content)
    if not match:
        return {}
    try:
        data = yaml.safe_load(match.group(1))
    except yaml.YAMLError as exc:
        detail = str(exc).replace("\n", " ")[:120]
        raise ProvenanceError(
            f"frontmatter YAML does not parse: {detail}"
        ) from exc
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ProvenanceError("frontmatter is not a mapping")
    return data


def _metadata_block(frontmatter: dict) -> dict | None:
    """The `metadata` mapping, or None when genuinely absent."""
    if "metadata" in frontmatter:
        block = frontmatter["metadata"]
        if not isinstance(block, dict):
            raise ProvenanceError(
                "metadata must be a mapping of origin/source/license"
            )
        return block
    typos = [
        key for key in frontmatter
        if isinstance(key, str) and _METADATA_TYPO.match(key)
    ]
    if typos:
        raise ProvenanceError(
            f"key {typos[0]!r} is not read — did you mean 'metadata'?"
        )
    return None


def parse_provenance(content: str) -> SkillProvenance:
    """Read a SKILL.md body. Absent metadata means first-party.

    Raises ``ProvenanceError``/``ValidationError`` when the block is
    present but incoherent — callers that must not raise use
    ``provenance_issues`` instead.
    """
    return provenance_from_block(_metadata_block(_frontmatter(content)))


def declares_provenance(content: str) -> bool:
    """Did the author WRITE a block, or is this the default?

    ``parse_provenance`` collapses "declared arkaos" and "said nothing"
    into the same value — correct for reading, useless for the one
    question the classification control has to answer.
    """
    try:
        return _metadata_block(_frontmatter(content)) is not None
    except ProvenanceError:
        return True  # broken but attempted; provenance_issues owns it


def provenance_issues(content: str) -> list[str]:
    """Non-raising validation. Empty list means the skill is clean."""
    try:
        parse_provenance(content)
    except ProvenanceError as exc:
        return [str(exc)]
    except ValidationError as exc:
        return [
            err["msg"].removeprefix("Value error, ") for err in exc.errors()
        ]
    return []

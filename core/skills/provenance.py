"""Skill provenance — supply-chain lineage for every SKILL.md.

A skill either originates in ArkaOS or it is derived from someone
else's work. Third-party lineage is a security property, not trivia: a
skill tree with no origin field cannot be audited after the fact, and
"which licence is this under?" becomes unanswerable the moment the
author who ported it moves on.

Contract (opt-in, absence means first-party):

    ---
    name: dev/silent-failure-hunter
    description: ...
    allowed-tools: [Read, Grep, Glob]
    metadata:
      origin: ecc-derived
      source: https://github.com/affaan-m/ecc
      license: MIT
    ---

``origin`` is a lowercase slug (``^[a-z][a-z0-9-]*$``). ``arkaos`` — or
no metadata block at all — is first-party and needs nothing else. ANY
other origin MUST declare ``source`` (an http(s) URL) and ``license``.

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
"""

from __future__ import annotations

import re

import yaml
from pydantic import BaseModel, Field, ValidationError, model_validator

FIRST_PARTY = "arkaos"
METADATA_FIELDS = ("origin", "source", "license")

_FRONTMATTER = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)
_ORIGIN_SLUG = re.compile(r"^[a-z][a-z0-9-]*$")
# https only: a licence trail that can be MITM'd is not a trail.
_URL = re.compile(r"^https://\S+$")
# Near-misses for `metadata` — a typo must not read as "no block".
_METADATA_TYPO = re.compile(r"^meta[-_ ]?datas?$", re.IGNORECASE)


class ProvenanceError(ValueError):
    """The provenance block is present but cannot be trusted."""


class SkillProvenance(BaseModel):
    """Where a skill came from, and under what licence."""

    origin: str = Field(default=FIRST_PARTY)
    source: str | None = None
    license: str | None = None

    @model_validator(mode="after")
    def _derived_needs_a_trail(self) -> SkillProvenance:
        if not _ORIGIN_SLUG.match(self.origin):
            raise ValueError(
                f"origin {self.origin!r} is not a lowercase slug "
                f"(^[a-z][a-z0-9-]*$)"
            )
        if self.origin == FIRST_PARTY:
            return self._first_party_carries_no_trail()
        missing = [f for f in ("source", "license") if not getattr(self, f)]
        if missing:
            raise ValueError(
                f"origin {self.origin!r} is third-party — "
                f"{', '.join(missing)} required"
            )
        if not _URL.match(self.source or ""):
            raise ValueError(f"source {self.source!r} is not an https URL")
        return self

    def _first_party_carries_no_trail(self) -> SkillProvenance:
        """`arkaos` plus a source/licence is an unresolved contradiction.

        Either the skill is ours and there is nothing to attribute, or
        it is not and the origin is wrong. Silence would let a bad port
        keep its upstream URL while claiming to be first-party.
        """
        declared = [f for f in ("source", "license") if getattr(self, f)]
        if declared:
            raise ValueError(
                f"origin {FIRST_PARTY!r} is first-party but declares "
                f"{', '.join(declared)} — set a third-party origin or "
                f"drop the field"
            )
        return self

    @property
    def is_first_party(self) -> bool:
        return self.origin == FIRST_PARTY


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
    block = _metadata_block(_frontmatter(content))
    if block is None:
        return SkillProvenance()
    unknown = sorted(str(k) for k in block if k not in METADATA_FIELDS)
    if unknown:
        raise ProvenanceError(
            f"unknown metadata keys: {', '.join(unknown)} "
            f"(expected {', '.join(METADATA_FIELDS)})"
        )
    return SkillProvenance(**block)


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

"""Provenance — supply-chain lineage for any ArkaOS artifact.

A skill, an agent, or anything else in the tree either originates in
ArkaOS or is derived from someone else's work. Third-party lineage is a
security property, not trivia: a tree with no origin field cannot be
audited after the fact, and "which licence is this under?" becomes
unanswerable the moment the author who ported it moves on.

This module owns the artifact-agnostic core — the ``Provenance`` model
and the block validator. The file-format parsers live with the artifact
that uses them: ``core/skills/provenance.py`` reads a SKILL.md
frontmatter block, ``core/agents/provenance.py`` reads an agent YAML
key. Both funnel through ``provenance_from_block`` so the validation
rules are defined once.

Rules:

- ``origin`` is a lowercase slug (``^[a-z][a-z0-9-]*$``). ``arkaos`` — or
  no block at all — is first-party and needs nothing else.
- Any other origin MUST declare ``source`` (an https URL) and
  ``license``. https only: a licence trail that can be MITM'd is not a
  trail.
- ``arkaos`` carrying a source/licence is an unresolved contradiction and
  is rejected — silence would let a bad port keep its upstream URL while
  claiming to be ours.
- A block present but incoherent (unknown keys, non-mapping) is an
  ERROR, never a silent fallback to first-party.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field, model_validator

FIRST_PARTY = "arkaos"
METADATA_FIELDS = ("origin", "source", "license")

_ORIGIN_SLUG = re.compile(r"^[a-z][a-z0-9-]*$")
_URL = re.compile(r"^https://\S+$")


class ProvenanceError(ValueError):
    """The provenance block is present but cannot be trusted."""


class Provenance(BaseModel):
    """Where an artifact came from, and under what licence."""

    origin: str = Field(default=FIRST_PARTY)
    source: str | None = None
    license: str | None = None

    @model_validator(mode="after")
    def _derived_needs_a_trail(self) -> Provenance:
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

    def _first_party_carries_no_trail(self) -> Provenance:
        """`arkaos` plus a source/licence is a contradiction.

        Either the artifact is ours and there is nothing to attribute, or
        it is not and the origin is wrong.
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


def provenance_from_block(block: dict | None) -> Provenance:
    """Validate a metadata mapping into a ``Provenance``.

    ``None`` (no block) is first-party. A block with keys outside
    origin/source/license is an error — a misspelt field must not be
    silently dropped into a first-party default.
    """
    if block is None:
        return Provenance()
    unknown = sorted(str(k) for k in block if k not in METADATA_FIELDS)
    if unknown:
        raise ProvenanceError(
            f"unknown metadata keys: {', '.join(unknown)} "
            f"(expected {', '.join(METADATA_FIELDS)})"
        )
    return Provenance(**block)

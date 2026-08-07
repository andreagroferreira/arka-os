"""Ownership manifest schema for ``~/.arkaos/ownership.json`` (PR-C1).

The manifest is the C2 manager's record of WHICH harness surfaces
ArkaOS claims and UNDER WHICH policy. C1 ships only the schema and a
tolerant loader — nothing here writes the file, and the default
manifest is DERIVED from ``core.harness.spec`` so the two can never
disagree about which surfaces exist.

Policy vocabulary (decided in the 2026-07-26 campaign plan, C2):

- ``own``        — ArkaOS replaces the surface wholesale on assert.
- ``own-subset`` — ArkaOS guarantees its own entries exist; operator
  entries on the same surface are never removed.
- ``seed``       — written only when absent; an operator edit is
  ADOPTED (drift reports it, assert never reverts it).
- ``operator``   — ArkaOS never touches the surface.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError

from core.harness import json_store
from core.harness import spec as harness_spec


class OwnershipPolicy(StrEnum):
    """How ArkaOS treats one harness surface."""

    OWN = "own"
    OWN_SUBSET = "own-subset"
    SEED = "seed"
    OPERATOR = "operator"


class SurfaceRecord(BaseModel):
    """One claimed surface and the policy it is held under."""

    surface: str = Field(description="Stable surface id, e.g. settings:hooks")
    policy: OwnershipPolicy
    last_asserted: str | None = Field(
        default=None,
        description="ISO-8601 timestamp of the last C2 assert; C1 never sets it",
    )
    content_sha256: str | None = Field(
        default=None,
        description=(
            "Digest of the surface content at last assert; on "
            "own-subset surfaces this includes the operator entries "
            "preserved alongside the ArkaOS ones"
        ),
    )


class OwnershipManifest(BaseModel):
    """The full ownership manifest for one runtime."""

    version: int = 1
    runtime: str = "claude-code"
    surfaces: list[SurfaceRecord] = Field(default_factory=list)

    @classmethod
    def default(cls, runtime: str = "claude-code") -> OwnershipManifest:
        """Manifest derived from the runtime spec's surface table."""
        runtime_spec = harness_spec.spec_for(runtime)
        return cls(
            runtime=runtime,
            surfaces=[
                SurfaceRecord(surface=s.surface, policy=OwnershipPolicy(s.policy))
                for s in runtime_spec.surfaces
            ],
        )


def load_manifest(path: Path) -> tuple[OwnershipManifest | None, str | None]:
    """Tolerant manifest load: ``(manifest, None)`` or ``(None, error)``.

    Error vocabulary extends ``json_store.LoadResult`` with
    ``invalid-schema`` — a file that parses as JSON but does not
    validate is reported, never raised.
    """
    result = json_store.load_json(path)
    if not result.ok:
        return None, result.error
    try:
        return OwnershipManifest.model_validate(result.data), None
    except ValidationError:
        return None, "invalid-schema"

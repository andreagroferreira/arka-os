"""Definition of Done gate for ArkaOS deliveries (PR14 v2.36.0).

Implements the `definition-of-done-per-domain` NON-NEGOTIABLE rule from
PR10 constitution. Loads the per-domain checklists from
``config/constitution.yaml`` (`definition_of_done` section) and evaluates
an agent-supplied status report against them.

The gate does NOT execute the underlying checks itself (e.g. it does not
run Playwright or lint). It validates that the agent has reported a
status for each item in the relevant domain — passed, skipped, failed,
or not-applicable — and produces a verdict.

Hard items: ALL must be ``passed`` for the verdict to be APPROVED.
Soft items: may be ``skipped`` without rejection, but a ``failed``
soft item is still recorded.

This mirrors the audit pattern used by Marta in QG: the agent presents
its work + status claims, and the gate verifies completeness against
the canonical checklist. False reporting is a different problem (the
sycophancy detector + critic pass in QG catch that).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

import yaml

ItemStatus = Literal["passed", "skipped", "failed", "not-applicable"]

_CONSTITUTION_PATH = (
    Path(__file__).resolve().parents[2] / "config" / "constitution.yaml"
)

_VALID_STATUSES: frozenset[str] = frozenset({
    "passed", "skipped", "failed", "not-applicable",
})


@dataclass(frozen=True)
class DODItem:
    """One Definition-of-Done checklist item from the constitution."""

    id: str
    rule: str
    hard: bool
    conditional: str | None = None


@dataclass
class DODVerdict:
    """Structured outcome of a DOD evaluation."""

    domain: str
    approved: bool
    failed_hard_items: list[str] = field(default_factory=list)
    failed_soft_items: list[str] = field(default_factory=list)
    skipped_hard_items: list[str] = field(default_factory=list)
    skipped_soft_items: list[str] = field(default_factory=list)
    unreported_hard_items: list[str] = field(default_factory=list)
    unreported_soft_items: list[str] = field(default_factory=list)
    not_applicable: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    def summary(self) -> str:
        parts: list[str] = []
        if self.approved:
            parts.append("APPROVED")
        else:
            parts.append("REJECTED")
        if self.failed_hard_items:
            parts.append(f"failed-hard={','.join(self.failed_hard_items)}")
        if self.unreported_hard_items:
            parts.append(f"unreported-hard={','.join(self.unreported_hard_items)}")
        if self.skipped_hard_items:
            parts.append(f"skipped-hard={','.join(self.skipped_hard_items)}")
        return " | ".join(parts)


def load_definition_of_done(
    domain: str, constitution_path: Path | None = None
) -> list[DODItem]:
    """Return the DOD items for *domain* (universal items + domain-specific).

    ``domain`` is one of: ``frontend``, ``backend``, ``content``. Other
    names raise ``ValueError`` (no implicit fallback — agents must opt
    in to a known domain). Universal items are always merged in front
    of the domain-specific items.
    """
    path = constitution_path or _CONSTITUTION_PATH
    with open(path, encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    dod = data.get("definition_of_done") or {}
    if domain not in dod or domain == "description" or domain == "universal":
        valid = [
            k for k in dod.keys()
            if k not in {"description", "universal"}
        ]
        raise ValueError(
            f"unknown DOD domain {domain!r}; choose from {sorted(valid)}"
        )

    items: list[DODItem] = []
    for raw in (dod.get("universal", {}).get("items") or []):
        items.append(_to_item(raw))
    for raw in (dod[domain].get("items") or []):
        items.append(_to_item(raw))
    return items


def evaluate_dod(
    domain: str,
    item_statuses: dict[str, str],
    constitution_path: Path | None = None,
) -> DODVerdict:
    """Validate *item_statuses* against the DOD checklist for *domain*.

    Inputs:
      domain         — one of "frontend", "backend", "content"
      item_statuses  — mapping {item_id: "passed"|"skipped"|"failed"|
                      "not-applicable"} reported by the agent
      constitution_path — optional override (test injection)

    Returns a :class:`DODVerdict`. Verdict is APPROVED iff:
      - every hard item is reported AND status == "passed"
        (or "not-applicable" with explicit justification — recorded
        but does not block)

    Soft items: never block. Their statuses are recorded for telemetry.
    Unknown status values raise ValueError.
    """
    items = load_definition_of_done(domain, constitution_path)
    for status in item_statuses.values():
        if status not in _VALID_STATUSES:
            raise ValueError(
                f"invalid status {status!r}; must be one of {sorted(_VALID_STATUSES)}"
            )

    verdict = DODVerdict(domain=domain, approved=True)
    for item in items:
        reported = item_statuses.get(item.id)
        if reported is None:
            if item.hard:
                verdict.unreported_hard_items.append(item.id)
                verdict.approved = False
            else:
                verdict.unreported_soft_items.append(item.id)
            continue
        if reported == "passed":
            continue
        if reported == "not-applicable":
            verdict.not_applicable.append(item.id)
            continue
        if reported == "skipped":
            if item.hard:
                verdict.skipped_hard_items.append(item.id)
                verdict.approved = False
            else:
                verdict.skipped_soft_items.append(item.id)
            continue
        if reported == "failed":
            if item.hard:
                verdict.failed_hard_items.append(item.id)
                verdict.approved = False
            else:
                verdict.failed_soft_items.append(item.id)
    return verdict


def list_supported_domains(constitution_path: Path | None = None) -> list[str]:
    """Enumerate the domains the constitution defines DOD checklists for."""
    path = constitution_path or _CONSTITUTION_PATH
    with open(path, encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    dod = data.get("definition_of_done") or {}
    return sorted(
        k for k in dod.keys()
        if k not in {"description", "universal"}
    )


def _to_item(raw: dict) -> DODItem:
    return DODItem(
        id=str(raw["id"]),
        rule=str(raw["rule"]),
        hard=bool(raw.get("hard", True)),
        conditional=raw.get("conditional"),
    )

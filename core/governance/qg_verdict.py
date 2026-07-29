"""Structured Quality Gate verdict schema (PR-4 evidence Quality Gate).

``QGVerdict`` is the contract every QG reviewer subagent must return.
The verdict is INTERPRETATION of an ``EvidenceReport`` from
``core.governance.evidence_checks`` — never narrative alone:

  - ``evidence_report.overall == "fail"`` forces ``verdict=REJECTED``;
    a persona cannot override failing evidence with prose.
  - ``APPROVED`` requires ``overall == "pass"``, or
    ``insufficient-evidence`` with an explicit justification in notes.

``QG_VERDICT_JSON_SCHEMA`` is the dict to pass as the structured-output
schema when dispatching reviewers via the Agent tool.
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, model_validator

_SHA256_HEX_RE = re.compile(r"[0-9a-f]{64}")


class QGBlocker(BaseModel):
    """One concrete issue that blocks approval."""

    check: str = Field(description="Evidence check or rubric area that failed")
    detail: str = Field(description="What exactly is wrong, with evidence")
    file: str | None = Field(
        default=None, description="File (and line if known) of the issue"
    )
    # Constitution 2.0 (PR-5, 2026-07-08): claim-level verdict vocabulary
    # imported from the frontier review pattern — findings are judged
    # individually, not only the deliverable as a whole.
    verdict: Literal["CONFIRMED", "PLAUSIBLE", "REFUTED"] | None = Field(
        default=None,
        description=(
            "Claim-level verdict after attempting reproduction: CONFIRMED "
            "(reproduced from the code/output), PLAUSIBLE (credible but not "
            "reproduced), REFUTED (disproven — recorded for telemetry, must "
            "NOT count toward rejection)"
        ),
    )


class QGEvidenceSummary(BaseModel):
    """Embedded summary of the EvidenceReport the reviewer interpreted."""

    overall: Literal["pass", "fail", "insufficient-evidence"]
    checks_ran: list[str] = Field(default_factory=list)
    checks_failed: list[str] = Field(default_factory=list)
    checks_skipped: list[str] = Field(default_factory=list)


class QGVerdict(BaseModel):
    """Binary Quality Gate verdict derived from executable evidence."""

    verdict: Literal["APPROVED", "REJECTED"]
    evidence_report: QGEvidenceSummary
    blockers: list[QGBlocker] = Field(default_factory=list)
    reviewer: str = Field(description="Reviewer id, e.g. tech-director-francisca")
    model_used: str = Field(description="Model tier the review ran on")
    notes: str = Field(
        default="",
        description=(
            "Interpretation notes; MUST justify approval explicitly when "
            "evidence is insufficient"
        ),
    )
    # PR-B2 integrity digests — optional so the pre-B2 verdict corpus
    # stays valid. evidence_digest and reviewer_output_sha256 must be
    # real sha256 hex when present; tree_digest is RESERVED and
    # rejects ANY value (see its description and the validator).
    evidence_digest: str = Field(
        default="",
        description=(
            "sha256 of the EvidenceReport the reviewer interpreted "
            "(report_digest from the --json output); empty when the "
            "report carried none"
        ),
    )
    tree_digest: str = Field(
        default="",
        description=(
            "RESERVED — must be empty. The producing primitive will "
            "ship in its own PR (acceptance spec: "
            "docs/adr/2026-07-29-tree-digest-corpus.md); until it "
            "exists, a non-empty value is rejected so no unverifiable "
            "digest can enter the corpus."
        ),
    )
    reviewer_output_sha256: str = Field(
        default="",
        description=(
            "sha256 of the reviewer's own raw output, as captured by the "
            "ledger (raw_sha256); empty when not yet ledgered"
        ),
    )

    @model_validator(mode="after")
    def digests_are_sha256_hex_or_empty(self) -> QGVerdict:
        for name in ("evidence_digest", "reviewer_output_sha256"):
            value = getattr(self, name)
            if value and not _SHA256_HEX_RE.fullmatch(value):
                raise ValueError(
                    f"{name} must be 64 lowercase hex chars or empty, "
                    f"got {value!r}"
                )
        if self.tree_digest:
            raise ValueError(
                "tree_digest is RESERVED and must be empty until the "
                "tree-digest primitive ships in its own PR — an "
                "unverifiable digest must not enter the corpus"
            )
        return self

    @model_validator(mode="after")
    def enforce_evidence_floor(self) -> QGVerdict:
        """APPROVED cannot coexist with failing evidence (evidence floor)."""
        if self.verdict == "APPROVED" and self.evidence_report.overall == "fail":
            raise ValueError(
                "APPROVED verdict with evidence overall='fail' — a persona "
                "cannot override failing evidence with narrative"
            )
        if (
            self.verdict == "APPROVED"
            and self.evidence_report.overall == "insufficient-evidence"
            and not self.notes.strip()
        ):
            raise ValueError(
                "APPROVED on insufficient-evidence requires explicit "
                "justification in notes"
            )
        return self


QG_VERDICT_JSON_SCHEMA: dict = QGVerdict.model_json_schema()

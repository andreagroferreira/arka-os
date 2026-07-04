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

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class QGBlocker(BaseModel):
    """One concrete issue that blocks approval."""

    check: str = Field(description="Evidence check or rubric area that failed")
    detail: str = Field(description="What exactly is wrong, with evidence")
    file: str | None = Field(
        default=None, description="File (and line if known) of the issue"
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

    @model_validator(mode="after")
    def enforce_evidence_floor(self) -> "QGVerdict":
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

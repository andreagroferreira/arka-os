"""Structured Quality Gate verdict schema (PR-4 evidence Quality Gate).

``QGVerdict`` is the contract every QG reviewer subagent must return.
The verdict is INTERPRETATION of an ``EvidenceReport`` from
``core.governance.evidence_checks`` — never narrative alone:

  - ``evidence_report.overall == "fail"`` forces ``verdict=REJECTED``;
    a persona cannot override failing evidence with prose.
  - ``APPROVED`` requires ``overall == "pass"``, or
    ``insufficient-evidence`` with an explicit justification in notes.

``QG_VERDICT_JSON_SCHEMA`` is the field contract to name INSIDE the
dispatch prompt — the Agent tool has no structured-output parameter
(PR-B4 dispatch shape; see the Reviewer Dispatch Contract in
departments/quality/SKILL.md).
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
    # Gate Economy (2026-08-09, operator-approved): severity vocabulary
    # mirrored from JudgeFinding — findings gate by weight, not by count.
    severity: Literal["blocker", "major", "minor"] | None = Field(
        default=None,
        description=(
            "Gate severity: blocker/major findings gate the verdict; "
            "minor findings (typos, cosmetic style) fix forward in the "
            "same turn and never reopen a review round on their own. "
            "None = pre-severity corpus, treated as gating."
        ),
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


class QGDigestCarry(BaseModel):
    """One justified digest carry on an AGGREGATE verdict (PR-B4).

    Per-reviewer digest equality would force a re-dispatch of every
    reviewer whenever the evidence report changes at all. When the
    aggregator judges an earlier review still valid against the final
    report — a message-only amend, a doc-only delta — it declares the
    carry HERE, naming the reviewer, the digest that reviewer actually
    reviewed, and the reason. The guard accepts the mismatch only when
    the declared digest matches the reviewer's own artifact and the
    reason is substantive; anything less refuses an APPROVED aggregate.
    """

    reviewer: str = Field(description="Reviewer id whose review is carried")
    evidence_digest: str = Field(
        description=(
            "sha256 of the report that reviewer actually reviewed — "
            "must equal the evidence_digest in their ledger artifact"
        )
    )
    reason: str = Field(
        description=(
            "Why the earlier review still stands against the final "
            "report (>= 40 chars — same bar as a REFUTED drop)"
        )
    )

    @model_validator(mode="after")
    def digest_is_sha256_hex(self) -> QGDigestCarry:
        if not _SHA256_HEX_RE.fullmatch(self.evidence_digest):
            raise ValueError(
                "a digest carry must name the exact report digest the "
                f"reviewer reviewed (64 hex chars), got "
                f"{self.evidence_digest!r}"
            )
        return self


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
    # PR-B4: aggregate-only, optional so the existing corpus stays
    # valid. Reviewer verdicts have no use for it (the guard reads it
    # from the aggregate side only).
    digest_carries: list[QGDigestCarry] = Field(
        default_factory=list,
        description=(
            "AGGREGATE only: justified carries for reviewers whose "
            "review the aggregator judges still valid against the "
            "final report — typically an earlier report revision; the "
            "guard verifies the declared digest against the reviewer's "
            "own artifact, never digest precedence (digests are "
            "unordered — see QGDigestCarry)"
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

    @model_validator(mode="after")
    def enforce_severity_policy(self) -> QGVerdict:
        """Gate Economy: findings gate by weight, minors fix forward.

        A rejection needs at least one live (CONFIRMED/PLAUSIBLE)
        blocker of gating severity — or failing evidence. An approval
        carries no live gating blocker, and any live minor it carries
        must have its fix-forward recorded in notes.
        """
        live = [
            b for b in self.blockers if b.verdict in ("CONFIRMED", "PLAUSIBLE")
        ]
        gating = [b for b in live if b.severity in (None, "blocker", "major")]
        if (
            self.verdict == "REJECTED"
            and self.evidence_report.overall != "fail"
            and self.blockers
            and not gating
        ):
            raise ValueError(
                "REJECTED over passing evidence with only minor-severity "
                "findings — minors fix forward in the same turn; a "
                "rejection needs a blocker/major finding or failing "
                "evidence"
            )
        if self.verdict == "APPROVED" and gating:
            raise ValueError(
                "APPROVED verdict carrying a live CONFIRMED/PLAUSIBLE "
                "blocker of gating severity — fix it, refute it on the "
                "record, or reject"
            )
        if (
            self.verdict == "APPROVED"
            and any(b.severity == "minor" for b in live)
            and not self.notes.strip()
        ):
            raise ValueError(
                "APPROVED with minor findings requires notes recording "
                "the fix-forward (what was corrected, verified how)"
            )
        return self


QG_VERDICT_JSON_SCHEMA: dict = QGVerdict.model_json_schema()

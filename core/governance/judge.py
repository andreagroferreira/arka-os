"""Unified gate-judge schema (Interaction Reform PR2).

``JudgeVerdict`` is the contract every gate judge returns: the
plan-judge at Gate 2 (judges the planning summary BEFORE it is shown to
the user) and the output-judge at Gate 4 (judges the deliverable BEFORE
the Quality Gate personas). Judges close the fragmentation gap — the
Forge critic only judged plans inside Forge runs, adversarial-review
only judged dev diffs, and Gate 4's excellence check was prose
instruction with no structured output.

Like ``qg_verdict.QGVerdict``, this module is schema + validation only:
the runtime never invokes models from Python. The orchestrator
dispatches the judge via the Agent tool with
``JUDGE_VERDICT_JSON_SCHEMA`` as the structured-output schema (see
``arka/skills/flow/SKILL.md`` Gates 2 and 4) and records the verdict via
``core.evals.record_cli --kind judge``.

The judge applies the ``arkaos-not-yes-man`` standard in BOTH
directions: findings judge the AGENT's work adversarially, and
``user_challenge`` carries the pushback when the USER's request itself
is technically wrong — the orchestrator must surface it, never swallow
it.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class JudgeFinding(BaseModel):
    """One concrete defect or risk the judge found."""

    area: str = Field(
        description=(
            "Rubric area: scope, verification, assumptions, excellence, "
            "consistency, risk…"
        )
    )
    detail: str = Field(description="What exactly is wrong, with evidence")
    severity: Literal["blocker", "major", "minor"]
    verdict: Literal["CONFIRMED", "PLAUSIBLE", "REFUTED"] | None = Field(
        default=None,
        description=(
            "Claim-level verdict after attempting reproduction; REFUTED is "
            "recorded for telemetry and must NOT count toward REVISE"
        ),
    )


class JudgeVerdict(BaseModel):
    """Binary gate-judge verdict. REVISE loops the work, max 2 times."""

    gate: Literal["G2", "G4"]
    role: Literal["plan-judge", "output-judge"]
    verdict: Literal["PASS", "REVISE"]
    findings: list[JudgeFinding] = Field(default_factory=list)
    user_challenge: str = Field(
        default="",
        description=(
            "Non-empty when the USER's request is technically wrong or "
            "would ship a worse product — the orchestrator presents this "
            "alongside the plan (pushback protocol, arkaos-not-yes-man)"
        ),
    )
    judged_digest: str = Field(
        default="",
        max_length=120,
        description="Opening excerpt of the judged artifact (auditability)",
    )
    reviewer: str = Field(description="Judge id, e.g. plan-judge-g2")
    model_used: str = Field(description="Model tier the judgment ran on")
    notes: str = ""

    @model_validator(mode="after")
    def revise_requires_actionable_findings(self) -> "JudgeVerdict":
        """REVISE must cite at least one blocker/major finding —
        a judge cannot loop work back on narrative alone."""
        if self.verdict == "REVISE":
            actionable = [
                f
                for f in self.findings
                if f.severity in ("blocker", "major") and f.verdict != "REFUTED"
            ]
            if not actionable:
                raise ValueError(
                    "REVISE verdict without an actionable (blocker/major, "
                    "non-REFUTED) finding — judges loop work on evidence, "
                    "never on narrative"
                )
        return self


JUDGE_VERDICT_JSON_SCHEMA: dict = JudgeVerdict.model_json_schema()

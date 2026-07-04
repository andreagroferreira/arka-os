"""Tests for core/governance/qg_verdict.py — structured QG verdict schema."""

import pytest
from pydantic import ValidationError

from core.governance.qg_verdict import (
    QG_VERDICT_JSON_SCHEMA,
    QGBlocker,
    QGEvidenceSummary,
    QGVerdict,
)


def _summary(overall: str) -> QGEvidenceSummary:
    return QGEvidenceSummary(
        overall=overall,
        checks_ran=["lint", "tests"],
        checks_failed=["tests"] if overall == "fail" else [],
        checks_skipped=["spellcheck"],
    )


def test_approved_on_passing_evidence_is_valid():
    verdict = QGVerdict(
        verdict="APPROVED",
        evidence_report=_summary("pass"),
        reviewer="tech-director-francisca",
        model_used="sonnet",
    )
    assert verdict.verdict == "APPROVED"
    assert verdict.blockers == []


def test_approved_over_failing_evidence_is_rejected_at_validation():
    with pytest.raises(ValidationError, match="cannot override failing evidence"):
        QGVerdict(
            verdict="APPROVED",
            evidence_report=_summary("fail"),
            reviewer="cqo-marta",
            model_used="opus",
        )


def test_rejected_on_failing_evidence_is_valid():
    verdict = QGVerdict(
        verdict="REJECTED",
        evidence_report=_summary("fail"),
        blockers=[
            QGBlocker(
                check="tests",
                detail="pytest exit 1: 3 failed",
                file="tests/test_orders.py",
            )
        ],
        reviewer="tech-director-francisca",
        model_used="sonnet",
    )
    assert verdict.blockers[0].check == "tests"


def test_approved_on_insufficient_evidence_requires_notes():
    with pytest.raises(ValidationError, match="explicit"):
        QGVerdict(
            verdict="APPROVED",
            evidence_report=_summary("insufficient-evidence"),
            reviewer="copy-director-eduardo",
            model_used="sonnet",
        )


def test_approved_on_insufficient_evidence_with_justification_is_valid():
    verdict = QGVerdict(
        verdict="APPROVED",
        evidence_report=_summary("insufficient-evidence"),
        reviewer="copy-director-eduardo",
        model_used="sonnet",
        notes="Docs-only diff; no executable surface. Manual prose review clean.",
    )
    assert verdict.verdict == "APPROVED"


def test_invalid_verdict_literal_rejected():
    with pytest.raises(ValidationError):
        QGVerdict(
            verdict="APPROVED_WITH_CAVEATS",
            evidence_report=_summary("pass"),
            reviewer="cqo-marta",
            model_used="opus",
        )


def test_json_schema_export_shape():
    assert isinstance(QG_VERDICT_JSON_SCHEMA, dict)
    properties = QG_VERDICT_JSON_SCHEMA["properties"]
    for key in ("verdict", "evidence_report", "blockers", "reviewer",
                "model_used", "notes"):
        assert key in properties
    assert QG_VERDICT_JSON_SCHEMA["properties"]["verdict"]["enum"] == [
        "APPROVED", "REJECTED",
    ]


def test_round_trip_serialization():
    verdict = QGVerdict(
        verdict="REJECTED",
        evidence_report=_summary("fail"),
        blockers=[QGBlocker(check="security-grep", detail="AKIA key", file="a.py")],
        reviewer="tech-director-francisca",
        model_used="sonnet",
    )
    reloaded = QGVerdict.model_validate_json(verdict.model_dump_json())
    assert reloaded == verdict

"""Tests for core.governance.judge (Interaction Reform PR2)."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from core.evals.verdict_labels import load_judge_labels, record_judge_label
from core.governance.judge import (
    JUDGE_VERDICT_JSON_SCHEMA,
    JudgeFinding,
    JudgeVerdict,
)


def _finding(severity: str = "major", verdict: str | None = None) -> JudgeFinding:
    return JudgeFinding(
        area="verification",
        detail="plan names no verify command for the schema change",
        severity=severity,
        verdict=verdict,
    )


def _verdict(**overrides) -> JudgeVerdict:
    payload = {
        "gate": "G2",
        "role": "plan-judge",
        "verdict": "PASS",
        "reviewer": "plan-judge-g2",
        "model_used": "opus",
    }
    payload.update(overrides)
    return JudgeVerdict.model_validate(payload)


class TestJudgeVerdict:
    def test_pass_without_findings_is_valid(self):
        assert _verdict().verdict == "PASS"

    def test_revise_requires_actionable_finding(self):
        with pytest.raises(ValidationError, match="actionable"):
            _verdict(verdict="REVISE")

    def test_revise_with_only_minor_findings_rejected(self):
        with pytest.raises(ValidationError, match="actionable"):
            _verdict(verdict="REVISE", findings=[_finding(severity="minor")])

    def test_revise_with_only_refuted_findings_rejected(self):
        # REFUTED findings are telemetry, never grounds to loop work.
        with pytest.raises(ValidationError, match="actionable"):
            _verdict(
                verdict="REVISE",
                findings=[_finding(severity="blocker", verdict="REFUTED")],
            )

    def test_revise_with_confirmed_major_finding_is_valid(self):
        verdict = _verdict(
            verdict="REVISE",
            findings=[_finding(severity="major", verdict="CONFIRMED")],
        )
        assert verdict.findings[0].severity == "major"

    def test_user_challenge_travels_with_pass(self):
        verdict = _verdict(
            user_challenge="O pedido assume 1000 req/s num SQLite local — "
            "matematicamente impossível com writes concorrentes.",
        )
        assert verdict.user_challenge

    def test_digest_is_capped(self):
        with pytest.raises(ValidationError):
            _verdict(judged_digest="x" * 121)

    def test_schema_exports_for_agent_dispatch(self):
        assert JUDGE_VERDICT_JSON_SCHEMA["title"] == "JudgeVerdict"
        assert "user_challenge" in JUDGE_VERDICT_JSON_SCHEMA["properties"]


class TestJudgeLabels:
    @pytest.fixture(autouse=True)
    def _tmp_labels(self, tmp_path, monkeypatch):
        self.path = tmp_path / "judge-verdicts.jsonl"
        monkeypatch.setenv("ARKA_JUDGE_LABELS_PATH", str(self.path))

    def test_record_and_load_roundtrip(self):
        record_judge_label(
            _verdict(
                verdict="REVISE",
                findings=[_finding(severity="blocker")],
            ),
            deliverable="plano feature X",
            department="dev",
            session_id="sess-1",
        )
        labels = load_judge_labels()
        assert len(labels) == 1
        assert labels[0]["verdict"] == "REVISE"
        assert labels[0]["gate"] == "G2"
        assert labels[0]["department"] == "dev"

    def test_never_raises_on_bad_path(self, monkeypatch):
        monkeypatch.setenv(
            "ARKA_JUDGE_LABELS_PATH", "/proc/1/forbidden/judge.jsonl"
        )
        record_judge_label(_verdict())  # must not raise

    def test_judge_corpus_is_separate_from_qg_corpus(
        self, tmp_path, monkeypatch
    ):
        qg_path = tmp_path / "qg-verdicts.jsonl"
        monkeypatch.setenv("ARKA_QG_LABELS_PATH", str(qg_path))
        record_judge_label(_verdict())
        assert self.path.exists()
        assert not qg_path.exists()

"""core.decisions.models — the typed contract of the Decisions endpoint."""

from __future__ import annotations

import json

import pytest
from _decisions_helpers import response_body
from pydantic import ValidationError

from core.decisions.models import (
    Answer,
    DecisionRequest,
    DecisionResponse,
    Question,
    QuestionType,
)


def _q(kind: str, criteria: object = None) -> Question:
    return Question(type=kind, instructions="judge it", criteria=criteria)


class TestQuestion:
    def test_noul_takes_no_criteria(self):
        assert _q("noul").to_payload() == {"type": "noul", "instructions": "judge it"}
        with pytest.raises(ValidationError):
            _q("noul", {"a": "b"})

    @pytest.mark.parametrize("size", [1, 255])
    def test_choice_accepts_1_to_255_options(self, size):
        q = _q("choice", {f"o{i}": "x" for i in range(size)})
        assert len(q.to_payload()["criteria"]) == size

    @pytest.mark.parametrize("criteria", [{}, {f"o{i}": "x" for i in range(256)}, ["a", "b"], None])
    def test_choice_rejects_bad_criteria(self, criteria):
        with pytest.raises(ValidationError):
            _q("choice", criteria)

    @pytest.mark.parametrize("levels", [2, 10])
    def test_score_accepts_2_to_10_levels(self, levels):
        assert _q("score", [str(i) for i in range(levels)]).type is QuestionType.SCORE

    @pytest.mark.parametrize("criteria", [["only"], [str(i) for i in range(11)], {"a": "b"}, None])
    def test_score_rejects_bad_levels(self, criteria):
        with pytest.raises(ValidationError):
            _q("score", criteria)

    def test_empty_instructions_rejected(self):
        with pytest.raises(ValidationError):
            Question(type="noul", instructions="")

    def test_unknown_field_rejected(self):
        with pytest.raises(ValidationError):
            Question(type="noul", instructions="x", weight=2)


class TestDecisionRequest:
    def test_payload_shape(self):
        req = DecisionRequest(
            model="typesafe/jev-1.13",
            state={"prompt": "olá"},
            questions={"a__b": _q("noul")},
        )
        assert req.to_payload() == {
            "model": "typesafe/jev-1.13",
            "state": {"prompt": "olá"},
            "questions": {"a__b": {"type": "noul", "instructions": "judge it"}},
        }

    def test_needs_at_least_one_question(self):
        with pytest.raises(ValidationError):
            DecisionRequest(model="m", state="s", questions={})


class TestResponse:
    def test_real_smoke_shape_parses_with_extras_ignored(self):
        body = json.loads(response_body({
            "topic_drift__topic_shift": {"type": "noul", "noul": 0.96},
            "route__department": {
                "type": "choice", "choice": "marketing", "confidence": 0.80,
                "probabilities": {"marketing": 0.8, "dev": 0.2},
            },
            "refine__level": {
                "type": "score", "score": 2.85,
                "legend": {"0": "clear", "1": "a", "2": "b", "3": "vague"},
                "probabilities": {"0": 0.01, "1": 0.04, "2": 0.05, "3": 0.9},
                "confidence": 0.95, "surprise": "ignored",
            },
        }))
        resp = DecisionResponse.model_validate(body)
        assert resp.model == "typesafe/jev-1.13-20260917"
        assert resp.answers["topic_drift__topic_shift"].noul == 0.96
        assert resp.answers["refine__level"].score == 2.85
        assert resp.answers["refine__level"].legend["3"] == "vague"
        assert resp.usage.output_tokens == 118 and resp.usage.cost == pytest.approx(3.1458e-05)

    def test_noul_outside_unit_interval_rejected(self):
        with pytest.raises(ValidationError):
            Answer(noul=1.5)

    def test_answers_required(self):
        with pytest.raises(ValidationError):
            DecisionResponse.model_validate({"model": "m"})

"""Tests for core.synapse.routing_feedback_layer (F1-B2)."""

from __future__ import annotations

import json

import pytest

from core.governance.routing_feedback import RoutingScore, RoutingScores
from core.synapse.layers import PromptContext
from core.synapse.routing_feedback_layer import RoutingFeedbackLayer


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv(
        "ARKA_ROUTING_SCORES_PATH", str(tmp_path / "routing-scores.json")
    )
    monkeypatch.delenv("ARKA_BYPASS_L55", raising=False)
    from core.synapse import routing_feedback_layer as rfl

    monkeypatch.setattr(rfl, "_CONFIG_PATH", tmp_path / ".arkaos" / "config.json")
    return tmp_path


def _write_scores(tmp_path, scores: list[RoutingScore]) -> None:
    payload = RoutingScores(
        computed_at="2026-07-11T12:00:00+00:00",
        sources=["qg-verdicts.jsonl", "judge-verdicts.jsonl"],
        scores=scores,
    )
    (tmp_path / "routing-scores.json").write_text(payload.model_dump_json(), encoding="utf-8")


def _risky(department: str = "dev") -> RoutingScore:
    return RoutingScore(
        department=department, approvals=3, rejections=6, samples=9,
        smoothed_approval=0.36,
        top_blocker_patterns=["function-length", "missing-tests"],
    )


def _ctx(prompt: str) -> PromptContext:
    return PromptContext(user_input=prompt, extra={"session_id": "s"})


DEV_PROMPT = "implementa a nova API endpoint com testes"


def test_warns_with_citable_counts(tmp_path):
    _write_scores(tmp_path, [_risky("dev")])
    result = RoutingFeedbackLayer().compute(_ctx(DEV_PROMPT))
    assert "[arka:redo-risk] dev: 3/9 approved" in result.content
    assert "smoothed 0.36" in result.content
    assert "function-length, missing-tests" in result.content


def test_silent_below_sample_floor(tmp_path):
    score = _risky("dev")
    score.samples = 4  # below _MIN_SAMPLES
    _write_scores(tmp_path, [score])
    result = RoutingFeedbackLayer().compute(_ctx(DEV_PROMPT))
    assert result.content == ""  # noise is not signal


def test_silent_when_healthy(tmp_path):
    score = _risky("dev")
    score.smoothed_approval = 0.82
    _write_scores(tmp_path, [score])
    result = RoutingFeedbackLayer().compute(_ctx(DEV_PROMPT))
    assert result.content == ""  # the layer only warns, never praises


def test_silent_without_scores_file():
    result = RoutingFeedbackLayer().compute(_ctx(DEV_PROMPT))
    assert result.content == ""


def test_silent_when_department_not_detected(tmp_path):
    _write_scores(tmp_path, [_risky("dev")])
    result = RoutingFeedbackLayer().compute(_ctx("olá bom dia"))
    assert result.content == ""


def test_silent_for_other_department(tmp_path):
    _write_scores(tmp_path, [_risky("marketing")])
    result = RoutingFeedbackLayer().compute(_ctx(DEV_PROMPT))
    assert result.content == ""


def test_env_bypass(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKA_BYPASS_L55", "1")
    _write_scores(tmp_path, [_risky("dev")])
    result = RoutingFeedbackLayer().compute(_ctx(DEV_PROMPT))
    assert result.content == ""


def test_config_flag_off(tmp_path):
    cfg = tmp_path / ".arkaos" / "config.json"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(json.dumps({"synapse": {"l55RoutingFeedback": False}}), encoding="utf-8")
    _write_scores(tmp_path, [_risky("dev")])
    result = RoutingFeedbackLayer().compute(_ctx(DEV_PROMPT))
    assert result.content == ""


def test_corrupt_scores_file_inert(tmp_path):
    (tmp_path / "routing-scores.json").write_text("{ not json", encoding="utf-8")
    result = RoutingFeedbackLayer().compute(_ctx(DEV_PROMPT))
    assert result.content == ""


def test_fail_open_on_internal_exception(tmp_path, monkeypatch):
    """The contract this layer sells: NO exception reaches the prompt path."""
    _write_scores(tmp_path, [_risky("dev")])
    layer = RoutingFeedbackLayer()
    monkeypatch.setattr(
        layer, "_warn_if_risky",
        lambda ctx: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    result = layer.compute(_ctx(DEV_PROMPT))  # must not raise
    assert result.content == ""
    assert result.tokens_est == 0


def test_non_dict_config_defaults_flag_on(tmp_path):
    """Malformed-but-valid JSON (a list) keeps the documented default: ON."""
    cfg = tmp_path / ".arkaos" / "config.json"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(json.dumps(["not", "a", "dict"]), encoding="utf-8")
    _write_scores(tmp_path, [_risky("dev")])
    result = RoutingFeedbackLayer().compute(_ctx(DEV_PROMPT))
    assert "[arka:redo-risk]" in result.content  # flag ON despite junk config


def test_detect_department_swallows_layer_errors(monkeypatch):
    """Best-effort detection: a DepartmentLayer crash yields '' silently."""
    from core.synapse import routing_feedback_layer as rfl

    class _Boom:
        def compute(self, ctx):
            raise RuntimeError("boom")

    monkeypatch.setattr(
        "core.synapse.layers.DepartmentLayer", lambda: _Boom()
    )
    assert rfl._detect_department(_ctx(DEV_PROMPT)) == ""


def test_registered_in_default_engine():
    from core.synapse.engine import create_default_engine

    engine = create_default_engine()
    ids = [layer.id for layer in engine._layers]
    assert "L5.5" in ids

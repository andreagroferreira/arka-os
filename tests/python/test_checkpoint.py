"""Tests for core.orchestration.checkpoint (PR15 v2.37.0)."""

from __future__ import annotations

import pytest

from core.orchestration.checkpoint import (
    CHECKPOINT_TRIGGER_S,
    SUB_DISPATCH_MAX_S,
    SUB_DISPATCH_MIN_S,
    SUB_DISPATCH_TARGET_S,
    CheckpointPlan,
    UserInjection,
    build_checkpoint_message,
    parse_user_injection,
    plan_fragmented_dispatches,
    should_checkpoint,
)


# ─── build_checkpoint_message ──────────────────────────────────────────


class TestBuildCheckpointMessage:
    def test_canonical_format(self):
        msg = build_checkpoint_message("francisca-tech-review", 180, 2, 4)
        assert msg.startswith("[arka:checkpoint]")
        assert "Step 2/4" in msg
        assert "francisca-tech-review" in msg
        assert "~180s" in msg
        assert "Silêncio = procedo" in msg

    def test_includes_carry_forward_when_present(self):
        msg = build_checkpoint_message(
            "marta-qg", 240, 3, 5,
            context_carried_forward="focus on KISS + DRY",
        )
        assert "Carry-forward" in msg
        assert "focus on KISS + DRY" in msg

    def test_omits_carry_forward_block_when_empty(self):
        msg = build_checkpoint_message("x", 10, 1, 1, context_carried_forward="")
        assert "Carry-forward" not in msg

    def test_clamps_step_and_total(self):
        msg = build_checkpoint_message("x", 60, 0, 0)
        assert "Step 1/1" in msg  # both clamped to >=1

    def test_total_below_step_is_raised(self):
        msg = build_checkpoint_message("x", 60, 5, 2)
        assert "Step 5/5" in msg  # total raised to step

    def test_empty_dispatch_name_defaults(self):
        msg = build_checkpoint_message("", 60, 1, 1)
        assert "next sub-task" in msg

    def test_negative_seconds_clamped_to_zero(self):
        msg = build_checkpoint_message("x", -5, 1, 1)
        assert "~0s" in msg


# ─── parse_user_injection ──────────────────────────────────────────────


class TestParseUserInjectionAbort:
    @pytest.mark.parametrize("text", [
        "stop",
        "para",
        "parar agora",
        "abort",
        "cancela isso",
        "wait, redirect",
        "muda direção",
        "altera o plano",
        "change direction please",
    ])
    def test_abort_cues_classified_as_abort(self, text: str):
        injection = parse_user_injection(text)
        assert injection.kind == "abort"
        assert injection.matched_cues


class TestParseUserInjectionContextAdd:
    @pytest.mark.parametrize("text", [
        "adiciona que o cliente precisa de WCAG AAA",
        "considera também o budget de €5k",
        "esquecia-me de mencionar que há deadline 14 junho",
        "antes de avançar, há restrição de licença AGPL",
        "ainda tens que considerar o tamanho da tabela",
        "Also, the feature flag must be off by default.",
        "btw the user is Linux-only",
        "+ user is on M1 Mac with 8GB RAM",
        "FYI: production already uses Stripe v2 API",
    ])
    def test_injection_cues_classified_as_context(self, text: str):
        injection = parse_user_injection(text)
        assert injection.kind == "context-injection", f"failed for {text!r}"

    def test_abort_wins_over_injection(self):
        # When user message has both an abort cue AND an injection cue,
        # safety wins: classified as abort.
        text = "stop, also consider the budget"
        injection = parse_user_injection(text)
        assert injection.kind == "abort"


class TestParseUserInjectionNewTurn:
    @pytest.mark.parametrize("text", [
        "Hello",
        "What is the status?",
        "Show me the report",
        "Can you generate a new feature?",
        "Boa tarde, podes ajudar com X?",
    ])
    def test_neutral_messages_classified_as_new_turn(self, text: str):
        injection = parse_user_injection(text)
        assert injection.kind == "new-turn"

    def test_empty_message_is_new_turn(self):
        assert parse_user_injection("").kind == "new-turn"
        assert parse_user_injection("   ").kind == "new-turn"


# ─── plan_fragmented_dispatches ────────────────────────────────────────


class TestPlanFragmentedDispatches:
    def test_returns_cleaned_sub_dispatch_list(self):
        plan = plan_fragmented_dispatches(
            "qg-review", ["  eduardo  ", "francisca", "  ", "marta-synthesis"]
        )
        assert plan.sub_dispatches == ["eduardo", "francisca", "marta-synthesis"]

    def test_total_seconds_uses_target_by_default(self):
        plan = plan_fragmented_dispatches("x", ["a", "b", "c"])
        assert plan.estimated_total_seconds == 3 * SUB_DISPATCH_TARGET_S

    def test_per_task_seconds_clamped_to_min(self):
        plan = plan_fragmented_dispatches("x", ["a"], per_task_seconds=5)
        assert plan.estimated_total_seconds == SUB_DISPATCH_MIN_S

    def test_per_task_seconds_clamped_to_max(self):
        plan = plan_fragmented_dispatches("x", ["a"], per_task_seconds=99_999)
        assert plan.estimated_total_seconds == SUB_DISPATCH_MAX_S

    def test_empty_task_name_defaults(self):
        plan = plan_fragmented_dispatches("", ["a"])
        assert plan.task_name == "unnamed-task"


# ─── should_checkpoint ─────────────────────────────────────────────────


class TestShouldCheckpoint:
    def test_above_trigger_true(self):
        assert should_checkpoint(CHECKPOINT_TRIGGER_S + 1) is True

    def test_at_trigger_false(self):
        # Strictly greater than → at trigger boundary is False
        assert should_checkpoint(CHECKPOINT_TRIGGER_S) is False

    def test_zero_false(self):
        assert should_checkpoint(0) is False

    def test_long_true(self):
        assert should_checkpoint(600) is True


# ─── Dataclass serialization ───────────────────────────────────────────


class TestDataclassSerialization:
    def test_checkpoint_plan_serializes(self):
        plan = CheckpointPlan(
            task_name="x", sub_dispatches=["a", "b"], estimated_total_seconds=360
        )
        d = plan.to_dict()
        assert d == {
            "task_name": "x",
            "sub_dispatches": ["a", "b"],
            "estimated_total_seconds": 360,
        }

    def test_user_injection_serializes(self):
        inj = UserInjection(kind="context-injection", matched_cues=["x"], raw_text="hi")
        d = inj.to_dict()
        assert d["kind"] == "context-injection"
        assert d["matched_cues"] == ["x"]

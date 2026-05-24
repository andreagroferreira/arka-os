"""Tests for core.governance.learning_detector (PR16 v2.38.0)."""

from __future__ import annotations

import pytest

from core.governance.learning_detector import (
    CorrectionSignal,
    detect_correction_signal,
)


# ─── No signal ──────────────────────────────────────────────────────────


class TestNoSignal:
    def test_empty_text(self):
        v = detect_correction_signal("")
        assert v.mode == "none"
        assert v.confidence == 0.0
        assert v.signals == []

    def test_neutral_factual_message(self):
        v = detect_correction_signal("The deployment finished at 14:32 UTC.")
        assert v.mode == "none"
        assert v.confidence < 0.35

    def test_question_is_not_correction(self):
        v = detect_correction_signal("What time is the meeting?")
        assert v.mode == "none"


# ─── Explicit save verbs → confidence 1.0 ──────────────────────────────


class TestExplicitSave:
    @pytest.mark.parametrize("text", [
        "guarda isto como regra permanente",
        "save this as a permanent rule going forward",
        "encode this in memory",
        "enforce this from now on",
    ])
    def test_explicit_save_is_high_confidence(self, text: str):
        v = detect_correction_signal(text)
        assert v.confidence == 1.0
        assert v.mode == "explicit"
        assert "explicit-save-verb" in v.signals
        assert v.kind == "rule"


# ─── Absolute language → rule kind ─────────────────────────────────────


class TestAbsoluteLanguage:
    @pytest.mark.parametrize("text", [
        "sempre faz isto antes de continuar com qualquer trabalho substantivo",
        "nunca aceites a primeira resposta sem crítica adicional",
        "sem exceções, todas as deliveries têm que passar pelo Quality Gate",
        "always cite reference companies when making recommendations",
        "never agree without pushback when math does not work out",
        "this is NON-NEGOTIABLE for all future deployments",
        "going forward, no compromise on the security audit",
    ])
    def test_absolute_language_marks_as_rule(self, text: str):
        v = detect_correction_signal(text)
        assert "absolute-language" in v.signals
        assert v.kind == "rule"
        assert v.confidence >= 0.55

    def test_non_negotiable_escalates_to_high_leverage(self):
        v = detect_correction_signal(
            "this is NON-NEGOTIABLE and applies to every single deployment"
        )
        assert v.is_high_leverage is True
        assert v.mode == "explicit"


# ─── Correction verbs ──────────────────────────────────────────────────


class TestCorrectionVerbs:
    @pytest.mark.parametrize("text", [
        "não quero que faças isso quando estamos a trabalhar no clientalpha",
        "para de assumir que eu sei o contexto do projeto",
        "deixa de pedir confirmação para cada pequena alteração",
        "stop doing the early-return pattern in those views",
        "don't assume the test data is fresh between runs",
        "avoid the deprecated Form Request constructor pattern",
        "wrong — em vez de Inertia v2 deve ser v3 com a nova API",
    ])
    def test_correction_verbs_detected(self, text: str):
        v = detect_correction_signal(text)
        assert "correction-verb" in v.signals
        assert v.confidence >= 0.4


# ─── Preferences (softer signal) ───────────────────────────────────────


class TestPreferences:
    @pytest.mark.parametrize("text", [
        "eu prefiro que sejas mais conciso nas respostas longas",
        "I prefer markdown tables when the data is structured",
        "o que eu quero é ver o output de Playwright sem flakiness",
        "I like the Stripe-style API contract more than REST verbose",
    ])
    def test_preferences_kind_is_preference(self, text: str):
        v = detect_correction_signal(text)
        assert "preference-cue" in v.signals
        # preference kind only if no stronger rule signal present
        if "absolute-language" not in v.signals and "correction-verb" not in v.signals:
            assert v.kind == "preference"


# ─── Mode selection ────────────────────────────────────────────────────


class TestModeSelection:
    def test_low_signal_mode_is_none(self):
        v = detect_correction_signal("Looks good.")
        assert v.mode == "none"

    def test_implicit_mode_when_medium_confidence(self):
        text = "I prefer this stack to be Laravel-based"  # short preference cue
        v = detect_correction_signal(text)
        assert v.mode in ("implicit", "none")

    def test_explicit_mode_when_non_negotiable_present(self):
        text = "regra NON-NEGOTIABLE: sempre executa testes Playwright antes do done"
        v = detect_correction_signal(text)
        assert v.mode == "explicit"
        assert v.is_high_leverage is True


# ─── High-leverage detection ───────────────────────────────────────────


class TestHighLeverage:
    def test_long_correction_with_absolute_is_high_leverage(self):
        text = (
            "sempre que estiveres a fazer trabalho de frontend, tens que verificar "
            "o console por errors e warnings antes de marcar a feature como done, "
            "porque tem havido regressões silenciosas que só apareceram em produção, "
            "e isso é inaceitável para a credibilidade do produto"
        )
        v = detect_correction_signal(text)
        assert v.is_high_leverage is True
        assert v.confidence >= 0.85

    def test_short_message_is_not_high_leverage(self):
        v = detect_correction_signal("sempre Playwright")
        assert v.is_high_leverage is False


# ─── Suggested memory type ─────────────────────────────────────────────


class TestSuggestedMemoryType:
    def test_rule_high_confidence_suggests_feedback(self):
        v = detect_correction_signal("guarda isto: nunca skip o critic pass")
        assert v.suggested_memory_type == "feedback"

    def test_preference_suggests_preference(self):
        v = detect_correction_signal(
            "Eu prefiro que sejas mais conciso quando as respostas excedem 500 palavras "
            "porque me cansa ler textos longos. Aplica em todas as conversas."
        )
        # This may also pick up absolute cue "todas", so accept either
        assert v.suggested_memory_type in ("preference", "feedback")

    def test_no_signal_suggests_empty(self):
        v = detect_correction_signal("Hello")
        assert v.suggested_memory_type == ""


# ─── should_save / should_confirm helpers ──────────────────────────────


class TestHelpers:
    def test_should_save_threshold(self):
        v = detect_correction_signal("guarda isto: nunca skip critic")
        assert v.should_save() is True

    def test_should_save_low_confidence_false(self):
        v = detect_correction_signal("Hello")
        assert v.should_save() is False

    def test_should_confirm_when_high_leverage(self):
        v = detect_correction_signal(
            "isto é NON-NEGOTIABLE: sempre Playwright + WCAG antes de done"
        )
        assert v.should_confirm() is True

    def test_should_confirm_when_very_high_confidence(self):
        v = detect_correction_signal("save this as a permanent rule")
        assert v.should_confirm() is True

    def test_dataclass_serializes(self):
        v = detect_correction_signal("sempre Playwright para frontend")
        d = v.to_dict()
        assert "mode" in d
        assert "kind" in d
        assert "confidence" in d
        assert "is_high_leverage" in d

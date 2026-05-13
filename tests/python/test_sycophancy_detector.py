"""Tests for core.governance.sycophancy_detector (PR13 v2.35.0)."""

from __future__ import annotations

import pytest

from core.governance.sycophancy_detector import (
    SycophancyVerdict,
    detect_sycophancy,
)


# ─── Pure-agreement standalone (highest confidence) ─────────────────────


class TestPureAgreementStandalone:
    @pytest.mark.parametrize("text", [
        "Sim.",
        "Claro!",
        "Perfeito",
        "OK",
        "Tudo certo.",
        "Yes",
        "Certo!",
    ])
    def test_short_agreement_is_sycophantic(self, text: str):
        verdict = detect_sycophancy(text)
        assert verdict.is_sycophantic is True
        assert verdict.confidence == 1.0
        assert "pure-agreement-standalone" in verdict.signals


# ─── Agreement opener without critique ──────────────────────────────────


class TestAgreementWithoutCritique:
    def test_tens_razao_alone_is_sycophantic(self):
        text = "Tens razão. Vou implementar como pediste."
        verdict = detect_sycophancy(text)
        assert verdict.is_sycophantic is True
        assert "agreement-opener" in verdict.signals
        assert "missing-critique-connector" in verdict.signals
        assert verdict.confidence >= 0.9

    def test_youre_right_alone_is_sycophantic(self):
        text = "You're right. Here is the implementation as you described."
        verdict = detect_sycophancy(text)
        assert verdict.is_sycophantic is True
        assert "agreement-opener" in verdict.signals

    def test_boa_ideia_alone_is_sycophantic(self):
        text = "Boa ideia. Vou fazer isso já."
        verdict = detect_sycophancy(text)
        assert verdict.is_sycophantic is True


# ─── Agreement WITH critique connector (not sycophantic) ────────────────


class TestAgreementWithCritique:
    def test_tens_razao_with_mas_is_acceptable(self):
        text = "Tens razão sobre o pattern. Mas há um problema estrutural — Stripe usa X em vez de Y porque escala melhor."
        verdict = detect_sycophancy(text)
        # Has agreement-opener signal but also critique connector
        # → not classified as sycophantic
        assert verdict.is_sycophantic is False
        assert "agreement-opener" in verdict.signals
        assert "missing-critique-connector" not in verdict.signals

    def test_agreement_with_however_is_acceptable(self):
        text = "Absolutely. However, before we proceed, there's a problem with the approach."
        verdict = detect_sycophancy(text)
        assert verdict.is_sycophantic is False

    def test_agreement_with_reference_company_passes(self):
        # Mentioning a reference company counts as critique-grade evidence
        text = "Tens razão. Linear handles this with a different pattern that scales better."
        verdict = detect_sycophancy(text)
        assert verdict.is_sycophantic is False


# ─── Recommendation without reference company citation ─────────────────


class TestRecommendationWithoutReference:
    def test_proponho_without_reference_company_is_flagged(self):
        text = (
            "Proponho que uses Redis para cache. Vai resolver o problema de "
            "latência que tens nas queries actuais. Implementa com TTL de 5 minutos."
        )
        verdict = detect_sycophancy(text)
        assert "recommendation-without-reference-company" in verdict.signals
        assert verdict.confidence >= 0.6

    def test_recommend_with_reference_company_passes(self):
        text = (
            "Proponho que uses Redis para cache — é o pattern que Stripe usa "
            "para latência de queries. Implementa com TTL de 5 minutos."
        )
        verdict = detect_sycophancy(text)
        assert "recommendation-without-reference-company" not in verdict.signals


# ─── Missing critic verdict in long responses ──────────────────────────


class TestMissingCriticVerdict:
    def test_long_response_without_critic_tag_is_flagged(self):
        text = "A" * 250  # long-ish response, no critic tag, no other signals
        verdict = detect_sycophancy(text)
        # critic absence alone is medium confidence
        assert "missing-critic-verdict" in verdict.signals

    def test_long_response_with_critic_passed_is_ok(self):
        text = "A" * 250 + " critic=passed"
        verdict = detect_sycophancy(text)
        assert "missing-critic-verdict" not in verdict.signals

    def test_short_response_does_not_require_critic(self):
        text = "Vou verificar isso e volto."
        verdict = detect_sycophancy(text)
        # Short response — critic verdict not required
        assert "missing-critic-verdict" not in verdict.signals


# ─── Clean responses (no signals) ───────────────────────────────────────


class TestCleanResponses:
    def test_empty_string_is_not_sycophantic(self):
        verdict = detect_sycophancy("")
        assert verdict.is_sycophantic is False
        assert verdict.signals == []

    def test_whitespace_only_is_not_sycophantic(self):
        verdict = detect_sycophancy("   \n  \t ")
        assert verdict.is_sycophantic is False

    def test_neutral_factual_response_is_clean(self):
        text = "O ficheiro foi modificado em 2026-05-13 às 14:32 UTC."
        verdict = detect_sycophancy(text)
        assert verdict.is_sycophantic is False
        assert verdict.confidence == 0.0

    def test_critique_first_response_is_clean(self):
        text = (
            "Há um problema estrutural na tua hipótese — Stripe handles "
            "pricing tiers com X pattern. critic=passed"
        )
        verdict = detect_sycophancy(text)
        assert verdict.is_sycophantic is False


# ─── Verdict dataclass ──────────────────────────────────────────────────


class TestVerdictDataclass:
    def test_verdict_is_serializable(self):
        v = SycophancyVerdict(
            is_sycophantic=True, signals=["a", "b"], confidence=0.9, response_length=100
        )
        d = v.to_dict()
        assert d["is_sycophantic"] is True
        assert d["signals"] == ["a", "b"]
        assert d["confidence"] == 0.9
        assert d["response_length"] == 100

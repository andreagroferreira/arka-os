"""Tests for core.governance.dod_gate (PR14 v2.36.0)."""

from __future__ import annotations

import pytest

from core.governance.dod_gate import (
    DODItem,
    DODVerdict,
    evaluate_dod,
    list_supported_domains,
    load_definition_of_done,
)


# ─── Domain enumeration ─────────────────────────────────────────────────


class TestDomainEnumeration:
    def test_lists_three_domains(self):
        domains = list_supported_domains()
        assert set(domains) == {"frontend", "backend", "content"}


# ─── Loading DOD items ─────────────────────────────────────────────────


class TestLoadDOD:
    def test_loads_frontend_with_universal(self):
        items = load_definition_of_done("frontend")
        ids = {item.id for item in items}
        # Universal items
        assert "acceptance-criteria-met" in ids
        assert "quality-gate-approved" in ids
        # Frontend-specific items
        assert "tests-pass" in ids
        assert "console-clean" in ids
        assert "wcag-pass" in ids

    def test_loads_backend_with_universal(self):
        items = load_definition_of_done("backend")
        ids = {item.id for item in items}
        assert "acceptance-criteria-met" in ids  # universal
        assert "tests-meaningful" in ids
        assert "kiss-no-premature-abstraction" in ids
        assert "dry-no-duplication" in ids

    def test_loads_content_with_universal(self):
        items = load_definition_of_done("content")
        ids = {item.id for item in items}
        assert "acceptance-criteria-met" in ids  # universal
        assert "voice-tone-match" in ids
        assert "no-ai-cliches" in ids

    def test_universal_items_are_hard(self):
        items = load_definition_of_done("frontend")
        universal_ids = {
            "acceptance-criteria-met", "self-critic-above-standard",
            "quality-gate-approved", "kb-research-cited",
        }
        for item in items:
            if item.id in universal_ids:
                assert item.hard is True, f"{item.id} should be hard"

    def test_frontend_wcag_is_soft_with_conditional(self):
        items = load_definition_of_done("frontend")
        wcag = next(i for i in items if i.id == "wcag-pass")
        assert wcag.hard is False
        assert wcag.conditional is not None
        assert "landing" in wcag.conditional.lower()

    def test_unknown_domain_raises(self):
        with pytest.raises(ValueError, match="unknown DOD domain"):
            load_definition_of_done("nonexistent")

    def test_universal_alone_is_not_a_domain(self):
        with pytest.raises(ValueError):
            load_definition_of_done("universal")


# ─── Evaluation: APPROVED paths ─────────────────────────────────────────


class TestEvaluateApproved:
    def test_all_hard_items_passed_approves(self):
        items = load_definition_of_done("backend")
        statuses = {item.id: "passed" for item in items}
        verdict = evaluate_dod("backend", statuses)
        assert verdict.approved is True
        assert verdict.failed_hard_items == []
        assert verdict.unreported_hard_items == []

    def test_soft_items_skipped_still_approves(self):
        items = load_definition_of_done("backend")
        statuses = {}
        for item in items:
            if item.hard:
                statuses[item.id] = "passed"
            else:
                statuses[item.id] = "skipped"
        verdict = evaluate_dod("backend", statuses)
        assert verdict.approved is True
        assert "tdd-when-critical" in verdict.skipped_soft_items

    def test_not_applicable_counts_as_passing_for_hard(self):
        # Some hard items become not-applicable in specific contexts;
        # the gate records them but does not block.
        items = load_definition_of_done("backend")
        statuses = {item.id: "passed" for item in items}
        statuses["security-scan-clean"] = "not-applicable"
        verdict = evaluate_dod("backend", statuses)
        assert verdict.approved is True
        assert "security-scan-clean" in verdict.not_applicable


# ─── Evaluation: REJECTED paths ─────────────────────────────────────────


class TestEvaluateRejected:
    def test_one_failed_hard_item_rejects(self):
        items = load_definition_of_done("frontend")
        statuses = {item.id: "passed" for item in items}
        statuses["console-clean"] = "failed"
        verdict = evaluate_dod("frontend", statuses)
        assert verdict.approved is False
        assert "console-clean" in verdict.failed_hard_items

    def test_skipped_hard_item_rejects(self):
        items = load_definition_of_done("backend")
        statuses = {item.id: "passed" for item in items}
        statuses["security-scan-clean"] = "skipped"
        verdict = evaluate_dod("backend", statuses)
        assert verdict.approved is False
        assert "security-scan-clean" in verdict.skipped_hard_items

    def test_unreported_hard_item_rejects(self):
        items = load_definition_of_done("content")
        statuses = {
            item.id: "passed" for item in items
            if item.id != "no-ai-cliches"
        }
        verdict = evaluate_dod("content", statuses)
        assert verdict.approved is False
        assert "no-ai-cliches" in verdict.unreported_hard_items

    def test_multiple_failures_collected_not_just_first(self):
        items = load_definition_of_done("backend")
        statuses = {item.id: "passed" for item in items}
        statuses["lint-clean"] = "failed"
        statuses["security-scan-clean"] = "failed"
        statuses["dry-no-duplication"] = "failed"
        verdict = evaluate_dod("backend", statuses)
        assert verdict.approved is False
        assert len(verdict.failed_hard_items) == 3
        for item_id in ("lint-clean", "security-scan-clean", "dry-no-duplication"):
            assert item_id in verdict.failed_hard_items


# ─── Soft items behaviour ───────────────────────────────────────────────


class TestSoftItems:
    def test_failed_soft_item_does_not_reject(self):
        items = load_definition_of_done("frontend")
        statuses = {item.id: "passed" for item in items}
        statuses["wcag-pass"] = "failed"  # soft for internal tools
        verdict = evaluate_dod("frontend", statuses)
        assert verdict.approved is True
        assert "wcag-pass" in verdict.failed_soft_items


# ─── Verdict serialization + summary ────────────────────────────────────


class TestVerdictHelpers:
    def test_verdict_to_dict_round_trip(self):
        v = DODVerdict(
            domain="frontend", approved=False,
            failed_hard_items=["console-clean"],
        )
        d = v.to_dict()
        assert d["domain"] == "frontend"
        assert d["approved"] is False
        assert d["failed_hard_items"] == ["console-clean"]

    def test_verdict_summary_approved(self):
        items = load_definition_of_done("backend")
        statuses = {item.id: "passed" for item in items}
        verdict = evaluate_dod("backend", statuses)
        assert verdict.summary().startswith("APPROVED")

    def test_verdict_summary_rejected_shows_blockers(self):
        items = load_definition_of_done("frontend")
        statuses = {item.id: "passed" for item in items}
        statuses["console-clean"] = "failed"
        statuses["tests-pass"] = "failed"
        summary = evaluate_dod("frontend", statuses).summary()
        assert "REJECTED" in summary
        assert "console-clean" in summary
        assert "tests-pass" in summary


# ─── Input validation ──────────────────────────────────────────────────


class TestInputValidation:
    def test_invalid_status_raises(self):
        with pytest.raises(ValueError, match="invalid status"):
            evaluate_dod("backend", {"acceptance-criteria-met": "maybe"})

    def test_extra_keys_in_statuses_are_tolerated(self):
        """Keys in statuses that aren't DOD items are silently ignored."""
        items = load_definition_of_done("backend")
        statuses = {item.id: "passed" for item in items}
        statuses["bogus-item-not-in-dod"] = "passed"
        verdict = evaluate_dod("backend", statuses)
        assert verdict.approved is True

"""Tests for the Constitution governance system."""

import pytest
from pathlib import Path

from core.governance.constitution import Constitution, load_constitution, Rule


class TestConstitutionLoader:
    def test_load_constitution_yaml(self):
        path = Path(__file__).parent.parent.parent / "config" / "constitution.yaml"
        c = load_constitution(path)
        assert c.version == "2.0.0"
        assert c.name == "ArkaOS Constitution"

    def test_nonexistent_raises(self):
        with pytest.raises(FileNotFoundError):
            load_constitution("/nonexistent/constitution.yaml")


class TestConstitutionRules:
    @pytest.fixture
    def constitution(self) -> Constitution:
        path = Path(__file__).parent.parent.parent / "config" / "constitution.yaml"
        return load_constitution(path)

    def test_has_14_non_negotiable_rules(self, constitution):
        rules = constitution.get_non_negotiable_rules()
        assert len(rules) == 14

    def test_non_negotiable_rule_ids(self, constitution):
        rule_ids = [r.id for r in constitution.get_non_negotiable_rules()]
        expected = [
            "branch-isolation", "obsidian-output", "authority-boundaries",
            "security-gate", "context-first", "solid-clean-code",
            "spec-driven", "human-writing", "squad-routing",
            "full-visibility", "sequential-validation", "mandatory-qa",
            "arka-supremacy", "context-verification",
        ]
        assert rule_ids == expected

    def test_has_6_must_rules(self, constitution):
        rules = constitution.get_must_rules()
        assert len(rules) == 6

    def test_must_rule_ids(self, constitution):
        rule_ids = [r.id for r in constitution.get_must_rules()]
        assert "conventional-commits" in rule_ids
        assert "test-coverage" in rule_ids
        assert "memory-persistence" in rule_ids

    def test_has_5_should_rules(self, constitution):
        rules = constitution.get_should_rules()
        assert len(rules) == 5

    def test_is_rule_non_negotiable(self, constitution):
        assert constitution.is_rule_non_negotiable("branch-isolation")
        assert constitution.is_rule_non_negotiable("arka-supremacy")
        assert not constitution.is_rule_non_negotiable("conventional-commits")
        assert not constitution.is_rule_non_negotiable("nonexistent")

    def test_get_all_rule_ids(self, constitution):
        all_ids = constitution.get_rule_ids()
        assert len(all_ids) == 25  # 14 + 6 + 5


class TestConstitutionQualityGate:
    @pytest.fixture
    def constitution(self) -> Constitution:
        path = Path(__file__).parent.parent.parent / "config" / "constitution.yaml"
        return load_constitution(path)

    def test_quality_gate_has_orchestrator(self, constitution):
        qg = constitution.enforcement_levels["quality_gate"]
        assert qg["agents"]["orchestrator"]["id"] == "cqo-marta"

    def test_quality_gate_has_two_reviewers(self, constitution):
        qg = constitution.enforcement_levels["quality_gate"]
        reviewers = qg["agents"]["reviewers"]
        assert len(reviewers) == 2
        reviewer_ids = [r["id"] for r in reviewers]
        assert "copy-director-eduardo" in reviewer_ids
        assert "tech-director-francisca" in reviewer_ids

    def test_quality_gate_process_steps(self, constitution):
        qg = constitution.enforcement_levels["quality_gate"]
        assert len(qg["process"]) == 6
        assert "APPROVED" in qg["process"][-1]


class TestConstitutionCompression:
    @pytest.fixture
    def constitution(self) -> Constitution:
        path = Path(__file__).parent.parent.parent / "config" / "constitution.yaml"
        return load_constitution(path)

    def test_compress_for_context(self, constitution):
        compressed = constitution.compress_for_context()
        assert "[Constitution]" in compressed
        assert "NON-NEGOTIABLE:" in compressed
        assert "branch-isolation" in compressed
        assert "arka-supremacy" in compressed
        assert "QUALITY-GATE:" in compressed
        assert "cqo-marta" in compressed
        assert "MUST:" in compressed
        assert "conventional-commits" in compressed

    def test_compressed_is_compact(self, constitution):
        compressed = constitution.compress_for_context()
        # Should be a single line, under 500 chars
        assert "\n" not in compressed
        assert len(compressed) < 500


class TestConstitutionTiers:
    @pytest.fixture
    def constitution(self) -> Constitution:
        path = Path(__file__).parent.parent.parent / "config" / "constitution.yaml"
        return load_constitution(path)

    def test_has_4_tiers(self, constitution):
        tiers = constitution.tier_hierarchy.get("tiers", {})
        assert len(tiers) == 4

    def test_tier_0_has_veto(self, constitution):
        tier_0 = constitution.tier_hierarchy["tiers"][0]
        assert "veto" in tier_0["authorities"]


class TestConstitutionConflict:
    @pytest.fixture
    def constitution(self) -> Constitution:
        path = Path(__file__).parent.parent.parent / "config" / "constitution.yaml"
        return load_constitution(path)

    def test_has_conflict_rules(self, constitution):
        assert len(constitution.conflict_resolution.rules) == 4

    def test_escalation_paths(self, constitution):
        esc = constitution.conflict_resolution.escalation
        assert "same_department" in esc
        assert "cross_department" in esc

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

    def test_has_16_non_negotiable_rules(self, constitution):
        rules = constitution.get_non_negotiable_rules()
        # PR10 v2.32.0 added 7 NON-NEGOTIABLE rules: 16 → 23.
        # PR44 v2.63.0 added mandatory-skill-evaluation: 23 → 24.
        # PR1 Squad Intelligence (v3.73.0) added dispatch-must-be-announced: 24 → 25.
        # Excellence Reform (v4.2.0) added excellence-mandate: 25 → 26.
        assert len(rules) == 26

    def test_non_negotiable_rule_ids(self, constitution):
        rule_ids = [r.id for r in constitution.get_non_negotiable_rules()]
        expected = [
            "branch-isolation", "obsidian-output", "authority-boundaries",
            "security-gate", "context-first", "solid-clean-code",
            "spec-driven", "human-writing", "squad-routing",
            "full-visibility", "sequential-validation", "mandatory-qa",
            "arka-supremacy", "context-verification", "forge-governance",
            "mandatory-skill-evaluation",
            # v4.1.0 evidence flow (replaced mandatory-flow; ADR 2026-07-04)
            "evidence-flow",
            # PR10 v2.32.0 Conclave Phase 5 additions
            "quality-over-speed", "always-research",
            "project-design-system-prerequisite",
            "definition-of-done-per-domain", "arkaos-not-yes-man",
            "inter-agent-checkpoints", "hybrid-learning",
            # PR1 Squad Intelligence Upgrade (v3.73.0)
            "dispatch-must-be-announced",
            # Excellence Reform (v4.2.0, operator mandate 2026-07-05)
            "excellence-mandate",
        ]
        assert rule_ids == expected

    def test_has_6_must_rules(self, constitution):
        rules = constitution.get_must_rules()
        # PR5 v2.27.0 added sub-squad-hierarchy: 9 → 10
        # PR3 Squad Intelligence (v3.74.0) added agent-experience-persistence: 10 → 11.
        # PR-4 prompt-surface (2026-07-08) added persona-vs-artifact: 11 → 12.
        assert len(rules) == 12

    def test_must_rule_ids(self, constitution):
        rule_ids = [r.id for r in constitution.get_must_rules()]
        assert "conventional-commits" in rule_ids
        assert "test-coverage" in rule_ids
        assert "memory-persistence" in rule_ids

    def test_has_5_should_rules(self, constitution):
        rules = constitution.get_should_rules()
        # PR4 v3.75.0 added pattern-library-first: 5 -> 6.
        # PR5 v3.76.0 added dna-fidelity-warn: 6 -> 7.
        # PR6 v3.77.0 added design-system-locked: 7 -> 8.
        assert len(rules) == 8

    def test_excellence_mandate_content(self, constitution):
        """The Excellence Reform rule must keep its executable criteria:
        anti-theatre question, cost-never-an-argument, frontend skill duty."""
        rule = next(
            r for r in constitution.get_non_negotiable_rules()
            if r.id == "excellence-mandate"
        )
        assert "excellence, not acceptance" in rule.rule
        assert "NEVER arguments against quality" in rule.rule
        assert "what is unfinished, what is default" in rule.rule
        assert "frontend-design" in rule.rule
        assert "maximum effort" in rule.rule

    def test_model_routing_is_quality_first(self, constitution):
        """Excellence Reform inverted the cost-optimised tier table."""
        rule = next(
            r for r in constitution.get_must_rules() if r.id == "model-routing"
        )
        assert "Quality-first" in rule.rule
        assert "BEST model available" in rule.rule
        assert "models.yaml" in rule.rule
        assert "mechanical" in rule.rule

    def test_subagent_discipline_exempts_quality_dispatches(self, constitution):
        rule = next(
            r for r in constitution.get_must_rules()
            if r.id == "subagent-discipline"
        )
        assert "EXEMPT" in rule.rule
        assert "Quality Gate reviewers" in rule.rule

    def test_is_rule_non_negotiable(self, constitution):
        assert constitution.is_rule_non_negotiable("branch-isolation")
        assert constitution.is_rule_non_negotiable("arka-supremacy")
        assert constitution.is_rule_non_negotiable("excellence-mandate")
        assert not constitution.is_rule_non_negotiable("conventional-commits")
        assert not constitution.is_rule_non_negotiable("nonexistent")

    def test_get_all_rule_ids(self, constitution):
        all_ids = constitution.get_rule_ids()
        # PR10 v2.32.0 added 7 NON-NEGOTIABLE: 31 → 38. PR44 mandatory-skill-evaluation: 38 → 39.
        # PR1 Squad Intelligence (v3.73.0) added dispatch-must-be-announced: 39 → 40.
        # PR3 Squad Intelligence (v3.74.0) added agent-experience-persistence: 40 → 41.
        # PR4 Squad Intelligence (v3.75.0) added pattern-library-first: 41 → 42.
        # PR5 Squad Intelligence (v3.76.0) added dna-fidelity-warn: 42 → 43.
        # PR6 Squad Intelligence (v3.77.0) added design-system-locked: 43 → 44.
        # Excellence Reform (v4.2.0) added excellence-mandate: 44 → 45.
        # PR-4 prompt-surface (2026-07-08) added persona-vs-artifact: 45 → 46.
        assert len(all_ids) == 46  # 26 + 12 + 8


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
        # v4.1.0: evidence engine prepended as step 1 (7 steps).
        # v4.2.0 Excellence Reform: redo-loop cap step added (8 steps).
        assert len(qg["process"]) == 8
        assert "evidence" in qg["process"][0].lower()
        assert "APPROVED" in qg["process"][-1]

    def test_quality_gate_reviewers_are_independent_and_cite_benchmark(self, constitution):
        """Excellence Reform: reviewers run in clean subagent context and
        every verdict names the benchmark it judged against."""
        qg = constitution.enforcement_levels["quality_gate"]
        process_text = " ".join(qg["process"])
        assert "INDEPENDENT" in process_text
        assert "benchmark" in process_text.lower()
        assert "reference_companies" in process_text

    def test_quality_gate_redo_loop_capped(self, constitution):
        qg = constitution.enforcement_levels["quality_gate"]
        process_text = " ".join(qg["process"])
        assert "capped at 2" in process_text
        assert "escalates to the operator" in process_text

    def test_quality_gate_model_policy_is_best_available(self, constitution):
        """Excellence Reform inverted the sonnet-default cost posture."""
        qg = constitution.enforcement_levels["quality_gate"]
        assert qg["model_policy"]["default"] == "best-available"


class TestConclavePhase5Sections:
    """PR10 v2.32.0 added 3 new top-level sections to the constitution.
    These tests pin the structure so future edits do not silently drop them."""

    @pytest.fixture
    def raw(self):
        import yaml
        path = Path(__file__).parent.parent.parent / "config" / "constitution.yaml"
        with open(path) as fh:
            return yaml.safe_load(fh)

    def test_definition_of_done_section_exists(self, raw):
        assert "definition_of_done" in raw
        dod = raw["definition_of_done"]
        assert "universal" in dod
        assert "frontend" in dod
        assert "backend" in dod
        assert "content" in dod

    def test_definition_of_done_universal_items_are_hard(self, raw):
        items = raw["definition_of_done"]["universal"]["items"]
        for item in items:
            assert item.get("hard") is True, f"{item['id']} must be hard for universal"
        ids = {i["id"] for i in items}
        assert "acceptance-criteria-met" in ids
        assert "quality-gate-approved" in ids
        assert "kb-research-cited" in ids

    def test_definition_of_done_frontend_wcag_is_conditional(self, raw):
        items = raw["definition_of_done"]["frontend"]["items"]
        wcag = next(i for i in items if i["id"] == "wcag-pass")
        assert wcag["hard"] is False
        assert "landing" in wcag.get("conditional", "").lower()
        assert "internal" in wcag.get("conditional", "").lower() or "dashboard" in wcag.get("conditional", "").lower()

    def test_definition_of_done_backend_anti_vanity_rule(self, raw):
        items = raw["definition_of_done"]["backend"]["items"]
        tests = next(i for i in items if i["id"] == "tests-meaningful")
        # The rule body must explicitly reject vanity-coverage tests
        assert "MEANINGFUL" in tests["rule"] or "meaningful" in tests["rule"].lower()
        assert "vanity" in tests["rule"].lower() or "REJECTED" in tests["rule"]

    def test_reference_companies_section_exists(self, raw):
        assert "reference_companies" in raw
        companies = raw["reference_companies"]["primary"]
        names = {c["name"] for c in companies}
        # The 6 locked by Andre 2026-05-13
        assert names == {"Google", "Stripe", "SpaceX", "Tesla", "Anthropic", "OpenAI"}

    def test_reference_companies_have_strengths(self, raw):
        companies = raw["reference_companies"]["primary"]
        for c in companies:
            assert "strength" in c
            assert len(c["strength"]) > 5  # non-trivial description

    def test_reference_companies_application_map_exists(self, raw):
        app = raw["reference_companies"]["application"]
        assert "code_backend" in app
        assert "frontend_ux" in app
        assert "content_copy" in app

    def test_tone_guide_primary_voice_is_hormozi(self, raw):
        assert "tone_guide" in raw
        assert raw["tone_guide"]["primary_voice"] == "Hormozi-direct"

    def test_tone_guide_pushback_protocol_has_escalation(self, raw):
        protocol = raw["tone_guide"]["pushback_protocol"]
        assert "escalation_levels" in protocol
        levels = protocol["escalation_levels"]
        assert len(levels) >= 5  # at least 5 escalation stages

    def test_tone_guide_anti_patterns_forbidden(self, raw):
        anti = raw["tone_guide"]["anti_patterns_forbidden"]
        # Must include the bedtime / time-of-day rule
        assert any("bedtime" in a.lower() or "dorme bem" in a.lower() or "ate amanha" in a.lower() for a in anti)
        # Must include the "tens razao when flawed" rule
        assert any("tens razao" in a.lower() or "structurally flawed" in a.lower() for a in anti)

    def test_pr10_amendment_logged(self, raw):
        history = raw["amendments"]["history"]
        v232 = next((h for h in history if h.get("version") == "2.32.0"), None)
        assert v232 is not None
        assert "Conclave Phase 5" in v232["changes"]


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
        # Single line. PR10 v2.32.0 grew the rule set (16→23 NON-NEGOTIABLE),
        # bumping the compressed size; keep under 900 chars (still <1KB).
        assert "\n" not in compressed
        assert len(compressed) < 900


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

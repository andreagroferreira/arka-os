"""Tests for core/agents/behavioral_compiler.py (PR-4 prompt-surface plan)."""

from __future__ import annotations

from pathlib import Path

import pytest

import re

from core.agents.behavioral_compiler import (
    _HAND_WRITTEN,
    build_escalation_index,
    check,
    compile_agent,
    load_agent_yaml,
    pilot_targets,
    write,
)

_ROOT = Path(__file__).resolve().parents[2]

_SAMPLE = {
    "id": "demo-eng-zara",
    "name": "Zara",
    "role": "Demo Engineer",
    "department": "dev",
    "tier": 2,
    "model": "sonnet",
    "behavioral_dna": {
        "disc": {
            "communication_style": "Direct, code-first",
            "under_pressure": "Slows down and writes more tests",
        },
        "enneagram": {
            "core_motivation": "Provably correct systems",
            "core_fear": "Silent data corruption",
        },
        "big_five": {"openness": 70},
        "mbti": {"type": "INTJ"},
    },
    "communication": {
        "tone": "concise, technical",
        "preferred_format": "diffs with rationale",
        "avoid": ["hand-waving"],
    },
    "signature_markers": {
        "avoid_patterns": ["you're absolutely right", "great question"],
    },
    "expertise": {
        "domains": ["demo systems"],
        "frameworks": ["TDD", "DDD"],
    },
    "authority": {"escalates_to": "tech-lead-paulo"},
}


class TestCompileAgent:
    def _out(self) -> str:
        return compile_agent(_SAMPLE, "demo-eng", "departments/dev/agents/demo-eng.yaml")

    def test_frontmatter_and_generated_marker(self):
        out = self._out()
        assert out.startswith("---\nname: demo-eng\n")
        assert "model: sonnet" in out
        assert "DO NOT EDIT; edit the YAML and re-run" in out
        assert "departments/dev/agents/demo-eng.yaml" in out

    def test_behavioral_translation_not_psychometrics(self):
        out = self._out()
        # Conditional rules reach the model...
        assert "Under pressure: slows down and writes more tests." in out
        assert "The failure you exist to prevent: Silent data corruption." in out
        # ...psychometric labels and scores do not.
        assert "INTJ" not in out
        assert "openness" not in out.lower()
        assert "big five" not in out.lower()
        assert "enneagram" not in out.lower()

    def test_lexical_blacklist_verbatim(self):
        out = self._out()
        assert '"you\'re absolutely right"' in out
        assert '"great question"' in out

    def test_disagreement_block_with_escalation_exit(self):
        out = compile_agent(
            _SAMPLE, "demo-eng", "departments/dev/agents/demo-eng.yaml",
            {"tech-lead-paulo": "`paulo-tech-lead`"},
        )
        assert "Insistence is not new evidence." in out
        assert "executing under objection" in out
        assert "escalate to `paulo-tech-lead`" in out

    def test_unresolved_escalation_renders_plain_id_no_backticks(self):
        out = self._out()  # no index provided
        assert "escalate to tech-lead-paulo." in out
        assert "`tech-lead-paulo`" not in out

    # QG B1/B2 regression pack: label form, never imperative-glued.
    def test_grammar_label_form_not_imperative_glue(self):
        out = self._out()
        assert "- Communication: Direct, code-first." in out
        assert "- Avoid hand-waving." in out
        assert "Communicate " not in out
        assert "Never use " not in out

    def test_persona_vs_artifact_and_no_meta_reference(self):
        out = self._out()
        assert "persona lives in the conversation, never in the deliverable" in out
        assert "Never meta-reference your own persona" in out

    def test_deterministic(self):
        assert self._out() == self._out()

    def test_missing_optional_fields_do_not_crash(self):
        minimal = {"name": "X", "role": "Y", "department": "z", "tier": 3}
        out = compile_agent(minimal, "x", "departments/z/agents/x.yaml")
        assert "You are X, Y of the z squad (Tier 3)." in out
        assert "## Never write" not in out
        assert "## Grounding" not in out
        assert "## How you work" not in out  # QG M1: no empty headers

    def test_bad_yaml_raises(self, tmp_path: Path):
        bad = tmp_path / "bad.yaml"
        bad.write_text("- just\n- a list\n", encoding="utf-8")
        with pytest.raises(ValueError):
            load_agent_yaml(bad)


class TestPilotLock:
    def test_hand_written_prompts_are_never_targets(self):
        outs = {out.stem for _, out in pilot_targets(_ROOT)}
        assert outs.isdisjoint(_HAND_WRITTEN)

    def test_committed_output_matches_compiler(self):
        # The YAML is the single source: any drift fails CI.
        assert check(_ROOT) == []

    def test_write_is_idempotent_on_clean_tree(self):
        before = {
            out: out.read_text(encoding="utf-8")
            for _, out in pilot_targets(_ROOT)
        }
        write(_ROOT)
        for out, text in before.items():
            assert out.read_text(encoding="utf-8") == text

    def test_no_dangling_escalation_handles_in_generated_files(self):
        # QG B3: a backticked escalation handle must resolve to a
        # DEPLOYED subagent (pilot output or hand-written prompt).
        deployed = {out.stem for _, out in pilot_targets(_ROOT)} | _HAND_WRITTEN
        handle_re = re.compile(r"escalate to `([^`]+)`")
        for _, out_path in pilot_targets(_ROOT):
            for handle in handle_re.findall(
                out_path.read_text(encoding="utf-8")
            ):
                assert handle in deployed, f"{out_path.name}: `{handle}` dangling"

    def test_generated_grammar_regressions_absent(self):
        # QG B1/B2/B4 sweep over the real generated pilot files.
        for _, out_path in pilot_targets(_ROOT):
            text = out_path.read_text(encoding="utf-8")
            assert "Communicate " not in text, out_path.name
            assert "Never use " not in text, out_path.name
            assert "he should have caught" not in text, out_path.name

    def test_escalation_index_maps_ids_to_deployed_or_role(self):
        index = build_escalation_index(_ROOT)
        assert index.get("tech-lead-paulo") == "`paulo-tech-lead`"
        assert index.get("architect-gabriel") == "`architect`"
        cto = index.get("cto-marco", "")
        assert "`" not in cto and "Chief Technology Officer" in cto

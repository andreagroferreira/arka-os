"""Tests for core.governance.dna_fidelity (PR5 Squad Intelligence).

DNA fidelity checker: compares an agent's output text against the
agent's `signature_markers` block declared in its YAML. Detects
forbidden patterns (avoid_patterns) and records violations to
telemetry. Soft-warn mode for v1 (PR5 v3.76.0); hard-block mode lands
later once telemetry shows the marker set is stable.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml


dna_fidelity = pytest.importorskip(
    "core.governance.dna_fidelity",
    reason="dna_fidelity not yet implemented (TDD red phase)",
)
SignatureMarkers = dna_fidelity.SignatureMarkers
FidelityViolation = dna_fidelity.FidelityViolation
check_fidelity = dna_fidelity.check_fidelity
record_fidelity = dna_fidelity.record_fidelity


@pytest.fixture
def tmp_setup(tmp_path, monkeypatch):
    """Isolate agent YAML search dir + telemetry path."""
    yaml_dir = tmp_path / "agents"
    yaml_dir.mkdir()
    monkeypatch.setattr(
        dna_fidelity, "AGENT_YAML_SEARCH_DIRS", [yaml_dir]
    )
    monkeypatch.setattr(
        dna_fidelity,
        "TELEMETRY_PATH",
        tmp_path / "telemetry" / "dna-fidelity.jsonl",
    )
    # Clear LRU cache so each test loads fresh
    if hasattr(dna_fidelity, "_load_markers"):
        dna_fidelity._load_markers.cache_clear()
    return {
        "yaml_dir": yaml_dir,
        "telemetry": tmp_path / "telemetry" / "dna-fidelity.jsonl",
    }


def _write_agent_yaml(
    yaml_dir: Path, agent_id: str, markers: dict | None = None
) -> Path:
    content: dict = {"id": agent_id, "name": agent_id}
    if markers is not None:
        content["signature_markers"] = markers
    path = yaml_dir / f"{agent_id}.yaml"
    path.write_text(yaml.safe_dump(content), encoding="utf-8")
    if hasattr(dna_fidelity, "_load_markers"):
        dna_fidelity._load_markers.cache_clear()
    return path


# ─── SignatureMarkers shape ────────────────────────────────────────────


def test_signature_markers_fields():
    markers = SignatureMarkers(
        opening_phrases=["[ARKA"],
        typical_patterns=["Decision"],
        closing_style="Final:",
        avoid_patterns=["sycophant", "you're absolutely right"],
    )
    assert markers.opening_phrases == ["[ARKA"]
    assert markers.typical_patterns == ["Decision"]
    assert markers.closing_style == "Final:"
    assert "sycophant" in markers.avoid_patterns


# ─── check_fidelity — no markers loaded ───────────────────────────────


def test_check_fidelity_unknown_agent_returns_empty(tmp_setup):
    violations = check_fidelity("no-such-agent", "any output")
    assert violations == []


def test_check_fidelity_agent_without_markers_returns_empty(tmp_setup):
    _write_agent_yaml(tmp_setup["yaml_dir"], "test-agent")  # no markers block
    violations = check_fidelity("test-agent", "any output")
    assert violations == []


# ─── check_fidelity — avoid_patterns ───────────────────────────────────


def test_check_fidelity_detects_forbidden_pattern(tmp_setup):
    _write_agent_yaml(
        tmp_setup["yaml_dir"],
        "cqo-marta",
        {"avoid_patterns": ["you're absolutely right", "sycophant"]},
    )
    output = "You're absolutely right about the verdict."
    violations = check_fidelity("cqo-marta", output)
    assert len(violations) == 1
    assert violations[0].kind == "forbidden_pattern"
    assert "absolutely right" in violations[0].pattern.lower()


def test_check_fidelity_multiple_violations(tmp_setup):
    _write_agent_yaml(
        tmp_setup["yaml_dir"],
        "cqo-marta",
        {"avoid_patterns": ["sycophant", "absolutely right", "I appreciate"]},
    )
    output = (
        "You're absolutely right. I appreciate your patience. "
        "This is great sycophant material."
    )
    violations = check_fidelity("cqo-marta", output)
    assert len(violations) == 3
    kinds = {v.kind for v in violations}
    assert kinds == {"forbidden_pattern"}


def test_check_fidelity_case_insensitive_patterns(tmp_setup):
    _write_agent_yaml(
        tmp_setup["yaml_dir"],
        "cqo-marta",
        {"avoid_patterns": ["sycophant"]},
    )
    violations = check_fidelity("cqo-marta", "Some SYCOPHANT text")
    assert len(violations) == 1


def test_check_fidelity_no_violations(tmp_setup):
    _write_agent_yaml(
        tmp_setup["yaml_dir"],
        "cqo-marta",
        {"avoid_patterns": ["softening"]},
    )
    output = "Quality Gate Verdict: REJECTED. Blockers below."
    violations = check_fidelity("cqo-marta", output)
    assert violations == []


def test_check_fidelity_empty_output(tmp_setup):
    _write_agent_yaml(
        tmp_setup["yaml_dir"],
        "cqo-marta",
        {"avoid_patterns": ["sycophant"]},
    )
    assert check_fidelity("cqo-marta", "") == []


# ─── check_fidelity — opening detection ────────────────────────────────


def test_check_fidelity_missing_opening_phrase(tmp_setup):
    _write_agent_yaml(
        tmp_setup["yaml_dir"],
        "cqo-marta",
        {
            "opening_phrases": ["Quality Gate Verdict:", "[ARKA"],
            "avoid_patterns": [],
        },
    )
    output = "Sure, looks great to me!"
    violations = check_fidelity("cqo-marta", output)
    assert any(v.kind == "missing_opening" for v in violations)


def test_check_fidelity_opening_phrase_present(tmp_setup):
    _write_agent_yaml(
        tmp_setup["yaml_dir"],
        "cqo-marta",
        {"opening_phrases": ["Quality Gate Verdict:"], "avoid_patterns": []},
    )
    output = "Quality Gate Verdict: APPROVED. Proceed."
    violations = check_fidelity("cqo-marta", output)
    assert all(v.kind != "missing_opening" for v in violations)


def test_check_fidelity_no_opening_phrases_defined_no_check(tmp_setup):
    """If opening_phrases is absent or empty, do not generate missing_opening violations."""
    _write_agent_yaml(
        tmp_setup["yaml_dir"],
        "cqo-marta",
        {"avoid_patterns": ["sycophant"]},
    )
    violations = check_fidelity("cqo-marta", "Sure, looks great!")
    assert all(v.kind != "missing_opening" for v in violations)


# ─── record_fidelity — telemetry ───────────────────────────────────────


def test_record_fidelity_writes_jsonl(tmp_setup):
    _write_agent_yaml(
        tmp_setup["yaml_dir"],
        "cqo-marta",
        {"avoid_patterns": ["sycophant"]},
    )
    output = "Great sycophant work!"
    violations = check_fidelity("cqo-marta", output)
    record_fidelity("cqo-marta", "sess-1", violations)
    assert tmp_setup["telemetry"].exists()
    last_line = (
        tmp_setup["telemetry"]
        .read_text(encoding="utf-8")
        .strip()
        .splitlines()[-1]
    )
    entry = json.loads(last_line)
    assert entry["agent_id"] == "cqo-marta"
    assert entry["violation_count"] == 1


def test_record_fidelity_records_clean_runs(tmp_setup):
    """Clean runs (no violations) are still recorded for tracking signal density."""
    _write_agent_yaml(
        tmp_setup["yaml_dir"],
        "cqo-marta",
        {"avoid_patterns": ["sycophant"]},
    )
    record_fidelity("cqo-marta", "sess-1", [])
    entry = json.loads(
        tmp_setup["telemetry"].read_text(encoding="utf-8").strip().splitlines()[-1]
    )
    assert entry["agent_id"] == "cqo-marta"
    assert entry["violation_count"] == 0


def test_record_fidelity_rejects_unsafe_agent_id(tmp_setup):
    record_fidelity("../../evil", "sess-1", [])
    assert not (tmp_setup["telemetry"].parent.parent / "evil").exists()


# ─── FidelityViolation shape ───────────────────────────────────────────


def test_fidelity_violation_has_kind_and_pattern():
    v = FidelityViolation(
        kind="forbidden_pattern",
        pattern="you're absolutely right",
        span="You're absolutely right about it.",
    )
    assert v.kind == "forbidden_pattern"
    assert v.pattern == "you're absolutely right"
    assert "absolutely right" in v.span


# ─── B2 integration tests — real departments/ tree resolution ──────────
#
# Marta's QG-B1 caught that _yaml_path_for("paulo") returned None because
# it literally searched for "paulo.yaml" while the file is "tech-lead.yaml"
# with `id: tech-lead-paulo`. The tests above all pass because the fixture
# wrote `<agent_id>.yaml` directly — masking the bug. These tests use the
# REAL departments/ tree (no monkeypatch) so the loader's name/id/suffix
# resolution is exercised end-to-end.


def _fresh_module():
    """Reload dna_fidelity so the lru_cache state is clean for integration."""
    import importlib
    import core.governance.dna_fidelity as mod
    importlib.reload(mod)
    return mod


def test_integration_paulo_routing_finds_tech_lead_yaml(tmp_path, monkeypatch):
    """Marta QG-B2: [arka:routing] dev -> Paulo → persona=paulo →
    must resolve to departments/dev/agents/tech-lead.yaml (id tech-lead-paulo)."""
    mod = _fresh_module()
    monkeypatch.setattr(
        mod, "TELEMETRY_PATH", tmp_path / "dna-fidelity.jsonl"
    )
    violations = mod.check_fidelity("paulo", "I appreciate your patience.")
    # Paulo's signature_markers seed avoids `I appreciate your patience`.
    assert any(
        v.kind == "forbidden_pattern" and "appreciate" in v.pattern.lower()
        for v in violations
    ), (
        "expected `I appreciate` violation against Paulo; got "
        f"{[(v.kind, v.pattern) for v in violations]}"
    )


def test_integration_marta_routing_finds_cqo_yaml(tmp_path, monkeypatch):
    """[arka:routing] quality -> Marta → persona=marta → cqo.yaml."""
    mod = _fresh_module()
    monkeypatch.setattr(
        mod, "TELEMETRY_PATH", tmp_path / "dna-fidelity.jsonl"
    )
    violations = mod.check_fidelity(
        "marta", "Great question! You're absolutely right, happy to help."
    )
    # Marta's seed avoids `you're absolutely right`, `great question`, `happy to help`
    patterns = {v.pattern.lower() for v in violations if v.kind == "forbidden_pattern"}
    assert any("absolutely right" in p for p in patterns)
    assert any("great question" in p for p in patterns)


def test_integration_eduardo_routing_finds_copy_director_yaml(tmp_path, monkeypatch):
    mod = _fresh_module()
    monkeypatch.setattr(
        mod, "TELEMETRY_PATH", tmp_path / "dna-fidelity.jsonl"
    )
    violations = mod.check_fidelity(
        "eduardo", "Let me delve into this tapestry and leverage utilize cutting-edge."
    )
    patterns = {v.pattern.lower() for v in violations if v.kind == "forbidden_pattern"}
    assert any("delve" in p for p in patterns)
    assert any("tapestry" in p for p in patterns)


def test_integration_francisca_routing_finds_tech_director_yaml(tmp_path, monkeypatch):
    mod = _fresh_module()
    monkeypatch.setattr(
        mod, "TELEMETRY_PATH", tmp_path / "dna-fidelity.jsonl"
    )
    violations = mod.check_fidelity(
        "francisca", "I think this might be a problem, perhaps."
    )
    patterns = {v.pattern.lower() for v in violations if v.kind == "forbidden_pattern"}
    assert any("i think" in p for p in patterns)


def test_integration_unknown_persona_returns_empty(tmp_path, monkeypatch):
    """Defensive: unknown persona must still return [], not raise."""
    mod = _fresh_module()
    monkeypatch.setattr(
        mod, "TELEMETRY_PATH", tmp_path / "dna-fidelity.jsonl"
    )
    assert mod.check_fidelity("nonexistent-persona-xyz", "any text") == []

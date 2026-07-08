"""Prompt-surface consistency lock (PR-2 of the prompt-surface plan).

Runs scripts/tools/prompt_lint.py against the real repo — the CI teeth
that keep the PR-1 (#255) coherence fixes from regressing — plus
synthetic fixtures proving each rule actually fires.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_LINT_PATH = _ROOT / "scripts" / "tools" / "prompt_lint.py"

_spec = importlib.util.spec_from_file_location("prompt_lint_lock", _LINT_PATH)
_lint = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_lint)

canonical_cliche_list = _lint.canonical_cliche_list
check_cliche_list_sync = _lint.check_cliche_list_sync
check_evidence_flow_restatements = _lint.check_evidence_flow_restatements
check_model_policy_single_source = _lint.check_model_policy_single_source
check_non_negotiable_ratchet = _lint.check_non_negotiable_ratchet
check_retired_counts = _lint.check_retired_counts
check_time_tag_absence = _lint.check_time_tag_absence
check_trivial_bypass_wording = _lint.check_trivial_bypass_wording
run_all = _lint.run_all


# --- The lock: the real repo must stay clean -----------------------------


def test_repo_prompt_surface_is_clean():
    violations = run_all(_ROOT)
    assert violations == [], "\n".join(violations)


def test_canonical_cliche_list_parses_from_constitution():
    items = canonical_cliche_list(_ROOT)
    assert len(items) >= 10
    assert "delve into" in items
    assert "in today's fast-paced" in items


# --- Synthetic fixtures: each rule fires on a violation ------------------


@pytest.fixture()
def fake_root(tmp_path: Path) -> Path:
    """Minimal governed tree that passes every check."""
    (tmp_path / "arka" / "skills" / "flow").mkdir(parents=True)
    (tmp_path / "departments" / "quality" / "agents").mkdir(parents=True)
    (tmp_path / "config" / "claude-agents").mkdir(parents=True)
    (tmp_path / "config" / "hooks").mkdir(parents=True)
    (tmp_path / "core" / "hooks").mkdir(parents=True)
    (tmp_path / "core" / "synapse").mkdir(parents=True)
    (tmp_path / "CLAUDE.md").write_text("# clean\n", encoding="utf-8")
    (tmp_path / "arka" / "SKILL.md").write_text("# clean\n", encoding="utf-8")
    (tmp_path / "config" / "constitution.yaml").write_text(
        'rule: "Zero AI cliches: \'delve into\', \'leverage\', \'utilize\','
        " 'robust', 'comprehensive', 'streamline', 'unlock', 'tapestry',"
        " 'dive deep', 'navigate', 'realm of', 'cutting-edge'\"\n",
        encoding="utf-8",
    )
    (tmp_path / "config" / "claude-agents" / "eduardo-copy.md").write_text(
        'flag "delve into", "leverage", "utilize", "robust", '
        '"comprehensive", "streamline", "unlock", "tapestry", '
        '"dive deep", "navigate", "realm of", "cutting-edge"\n',
        encoding="utf-8",
    )
    (
        tmp_path / "departments" / "quality" / "agents" / "copy-director.yaml"
    ).write_text(
        "avoid_patterns:\n"
        + "".join(
            f'    - "{i}"\n'
            for i in (
                "delve into", "leverage", "utilize", "robust",
                "comprehensive", "streamline", "unlock", "tapestry",
                "dive deep", "navigate", "realm of", "cutting-edge",
            )
        ),
        encoding="utf-8",
    )
    return tmp_path


def test_fake_root_baseline_is_clean(fake_root: Path):
    assert run_all(fake_root) == []


def test_model_policy_restatement_fires(fake_root: Path):
    # QG B1 regression pack: realistic drift forms, not just the
    # calibration string.
    for drift in (
        "Quality Gate ALWAYS `model: opus` — rule\n",
        "reviewers ALWAYS run on model: opus\n",
        "ALWAYS use model: opus for the gate\n",
        "Marta/Eduardo/Francisca ALWAYS dispatch with model: opus\n",
    ):
        (fake_root / "CLAUDE.md").write_text(drift, encoding="utf-8")
        assert check_model_policy_single_source(fake_root), drift


def test_cliche_desync_fires(fake_root: Path):
    eduardo = fake_root / "config" / "claude-agents" / "eduardo-copy.md"
    eduardo.write_text('flag "delve into", "leverage"\n', encoding="utf-8")
    violations = check_cliche_list_sync(fake_root)
    assert any("missing canonical cliche" in v for v in violations)


def test_cliche_yaml_desync_fires(fake_root: Path):
    yaml_path = (
        fake_root / "departments" / "quality" / "agents" / "copy-director.yaml"
    )
    yaml_path.write_text(
        'avoid_patterns:\n    - "delve into"\n', encoding="utf-8"
    )
    violations = check_cliche_list_sync(fake_root)
    assert any("avoid_patterns missing" in v for v in violations)


def test_unparseable_canonical_list_fires(fake_root: Path):
    (fake_root / "config" / "constitution.yaml").write_text(
        'rule: "no cliches allowed"\n', encoding="utf-8"
    )
    violations = check_cliche_list_sync(fake_root)
    assert any("unparseable" in v for v in violations)


def test_trivial_bypass_drift_fires(fake_root: Path):
    (fake_root / "arka" / "SKILL.md").write_text(
        "[arka:trivial] needs an imperative verb\n", encoding="utf-8"
    )
    assert check_trivial_bypass_wording(fake_root)


def test_retired_count_fires(fake_root: Path):
    (fake_root / "config" / "hooks" / "session-start.sh").write_text(
        'MSG+="ArkaOS | 65 agents"\n', encoding="utf-8"
    )
    assert check_retired_counts(fake_root)


def test_legitimate_larger_counts_do_not_fire(fake_root: Path):
    # QG B3 regression pack: growth counts contain retired substrings.
    (fake_root / "config" / "hooks" / "session-start.sh").write_text(
        'MSG+="ArkaOS | 165 agents | 265 agents | 156 agents | 1190 skills"\n',
        encoding="utf-8",
    )
    assert check_retired_counts(fake_root) == []


def test_gate_block_restatement_fires(fake_root: Path):
    (fake_root / "departments" / "quality" / "SKILL.md").parent.mkdir(
        exist_ok=True
    )
    (fake_root / "departments" / "quality" / "SKILL.md").write_text(
        "G1 CONTEXT — route\nG2 PLAN — approve\nG3 EXECUTE — run\n"
        "G4 REVIEW — check\n",
        encoding="utf-8",
    )
    assert check_evidence_flow_restatements(fake_root)


def test_gate_block_signature_phrase_fires(fake_root: Path):
    (fake_root / "CLAUDE.md").write_text(
        "G2 requires approval; silence is not approval.\n", encoding="utf-8"
    )
    assert check_evidence_flow_restatements(fake_root)


def test_inline_pointer_summary_does_not_fire(fake_root: Path):
    (fake_root / "CLAUDE.md").write_text(
        "Flow: G1 CONTEXT -> G2 PLAN -> G3 EXECUTE -> G4 REVIEW; spec in "
        "arka/skills/flow/SKILL.md.\n",
        encoding="utf-8",
    )
    # One inline summary line is a pointer, not a block restatement.
    assert check_evidence_flow_restatements(fake_root) == []


def test_time_tag_fires_value_independent(fake_root: Path):
    # QG B2 regression pack: the cache-buster defect is value-independent.
    for tag in ("[time:evening]", "[time:night]", "[time:noon]", "[time:dawn]"):
        (fake_root / "core" / "hooks" / "user_prompt_submit.py").write_text(
            f'TAG = "{tag}"\n', encoding="utf-8"
        )
        assert check_time_tag_absence(fake_root), tag


def test_non_negotiable_ratchet_fires_case_insensitive(fake_root: Path):
    # QG M5: lowercase prose markers count toward the inflation ratchet.
    (fake_root / "CLAUDE.md").write_text(
        "this is non-negotiable\n" * 48, encoding="utf-8"
    )
    assert check_non_negotiable_ratchet(fake_root)

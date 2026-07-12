"""Skill-budget gate (F2-7c) — the curated default stays small, in CI.

Runs the real auditor over the committed repo (no install needed).
A FAIL finding here means the default install surface grew past the
budget the curated cut exists to protect — fix the cut (or the
offending description), never the thresholds first.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
TOOLS_DIR = REPO_ROOT / "scripts" / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import skill_budget  # noqa: E402


@pytest.fixture(scope="module")
def report() -> dict:
    return skill_budget.audit()


def test_no_fail_findings_on_the_committed_cut(report):
    fails = [f for f in report["findings"] if f["level"] == "FAIL"]
    assert fails == [], (
        "skill budget breached — the curated default must stay inside "
        f"the caps: {fails}"
    )


def test_default_surface_within_the_60_80_band(report):
    assert 60 <= report["summary"]["skills"] <= skill_budget.MAX_SKILLS_FAIL


def test_total_always_on_chars_under_cap(report):
    assert (report["summary"]["total_description_chars"]
            <= skill_budget.TOTAL_CHARS_FAIL)


def test_structural_nonnegotiables_in_default(report):
    manifest = json.loads(
        (REPO_ROOT / "knowledge" / "skills-manifest.json")
        .read_text(encoding="utf-8"))
    meta = set(manifest["structural"]["meta"])
    assert {"arka-flow", "arka-forge", "arka-fusion"} <= meta


def test_folded_description_blocks_are_measured():
    """description: > folded values must count their full text, not 1 char."""
    fixture = REPO_ROOT / "departments" / "brand" / "skills" / \
        "design-review" / "SKILL.md"
    if not fixture.is_file():
        pytest.skip("fixture skill moved")
    text = skill_budget.frontmatter_description(fixture)
    body = fixture.read_text(encoding="utf-8")
    if "description: >" in body or "description: |" in body:
        assert len(text) > 40, "folded description collapsed to nothing"
    else:
        assert text, "plain description must be non-empty"


def test_cli_exit_codes(tmp_path, monkeypatch, capsys):
    """Exit 0 on the committed cut; exit 1 when a FAIL is injected."""
    assert skill_budget.main([]) == 0
    capsys.readouterr()

    broken = dict(json.loads(
        (REPO_ROOT / "knowledge" / "skills-manifest.json")
        .read_text(encoding="utf-8")))
    broken["structural"] = dict(broken["structural"])
    broken["structural"]["meta"] = [
        m for m in broken["structural"]["meta"] if m != "arka-flow"
    ]
    bad = tmp_path / "manifest.json"
    bad.write_text(json.dumps(broken), encoding="utf-8")
    monkeypatch.setattr(skill_budget, "MANIFEST_PATH", bad)
    assert skill_budget.main([]) == 1, (
        "dropping arka-flow from the structural default must FAIL the audit"
    )
